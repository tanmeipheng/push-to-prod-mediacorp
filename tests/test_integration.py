"""
Tests for the Data Sync Worker resilience logic.

Verifies that sync_data() correctly retries on HTTP 429 responses
and eventually succeeds when the rate limit clears.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from requests.exceptions import HTTPError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_429_error() -> HTTPError:
    """Build a realistic HTTPError that looks like a 429 response."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    error = HTTPError("429 Too Many Requests", response=mock_response)
    return error


def _make_200_response(payload):
    """Build a mock requests.Response that returns *payload* from .json()."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = payload
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSyncDataRetryOnRateLimit:
    """Suite covering the retry-with-jitter behaviour of sync_data()."""

    @patch("requests.get")
    def test_succeeds_immediately_when_no_rate_limit(self, mock_get):
        """sync_data() returns data straight away when the API responds 200."""
        from worker import sync_data  # import after patching

        payload = [{"id": 1}, {"id": 2}]
        mock_get.return_value = _make_200_response(payload)

        result = sync_data()

        assert result == payload
        assert mock_get.call_count == 1

    @patch("worker.sync_data.retry.sleep")   # suppress real sleeping
    @patch("requests.get")
    def test_retries_once_on_429_then_succeeds(self, mock_get, mock_sleep):
        """sync_data() retries after a single 429 and returns data on the second attempt."""
        from worker import sync_data

        payload = [{"id": 10}]
        mock_get.side_effect = [
            _make_429_error(),          # first call  → 429
            _make_200_response(payload), # second call → 200
        ]

        result = sync_data()

        assert result == payload
        assert mock_get.call_count == 2

    @patch("worker.sync_data.retry.sleep")
    @patch("requests.get")
    def test_retries_multiple_times_on_429_then_succeeds(self, mock_get, mock_sleep):
        """sync_data() retries up to N times on consecutive 429s before succeeding."""
        from worker import sync_data

        payload = [{"id": 99}]
        mock_get.side_effect = [
            _make_429_error(),
            _make_429_error(),
            _make_429_error(),
            _make_200_response(payload),
        ]

        result = sync_data()

        assert result == payload
        assert mock_get.call_count == 4

    @patch("worker.sync_data.retry.sleep")
    @patch("requests.get")
    def test_raises_after_max_attempts_exceeded(self, mock_get, mock_sleep):
        """sync_data() re-raises HTTPError once all retry attempts are exhausted."""
        from worker import sync_data
        from tenacity import RetryError

        # Always return 429 — exhaust all 7 attempts
        mock_get.side_effect = _make_429_error

        with pytest.raises((HTTPError, RetryError)):
            sync_data()

        assert mock_get.call_count == 7

    @patch("requests.get")
    def test_does_not_retry_on_non_429_http_error(self, mock_get):
        """sync_data() does NOT retry on non-429 HTTP errors (e.g. 500)."""
        from worker import sync_data

        mock_response = MagicMock()
        mock_response.status_code = 500
        error_500 = HTTPError("500 Internal Server Error", response=mock_response)
        mock_get.side_effect = error_500

        with pytest.raises(HTTPError):
            sync_data()

        # Must NOT retry — only one attempt should be made
        assert mock_get.call_count == 1

    @patch("worker.sync_data.retry.sleep")
    @patch("requests.get")
    def test_sleep_is_called_between_retries(self, mock_get, mock_sleep):
        """A sleep/wait occurs between retry attempts (jitter is applied)."""
        from worker import sync_data

        payload = [{}]
        mock_get.side_effect = [
            _make_429_error(),
            _make_429_error(),
            _make_200_response(payload),
        ]

        sync_data()

        # Two failures → two sleeps before the successful third attempt
        assert mock_sleep.call_count == 2
