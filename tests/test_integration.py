"""
Tests for the Data Sync Worker resilience logic.

Verifies that sync_data() correctly retries on HTTP 429 responses
using exponential backoff and eventually succeeds.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from requests.exceptions import HTTPError

# Import the module under test
import importlib, sys, types

# We import the fixed module
from fixed_code import sync_data, is_rate_limit_error


def make_http_error(status_code):
    """Helper to create an HTTPError with a given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = HTTPError(response=mock_response)
    return error


class TestIsRateLimitError:
    """Unit tests for the is_rate_limit_error predicate."""

    def test_returns_true_for_429(self):
        error = make_http_error(429)
        assert is_rate_limit_error(error) is True

    def test_returns_false_for_500(self):
        error = make_http_error(500)
        assert is_rate_limit_error(error) is False

    def test_returns_false_for_404(self):
        error = make_http_error(404)
        assert is_rate_limit_error(error) is False

    def test_returns_false_for_non_http_error(self):
        assert is_rate_limit_error(ValueError("not an http error")) is False

    def test_returns_false_when_response_is_none(self):
        error = HTTPError(response=None)
        assert is_rate_limit_error(error) is False


class TestSyncDataRetryLogic:
    """Integration-style tests for sync_data() retry behaviour."""

    @patch("fixed_code.requests.get")
    def test_succeeds_on_first_attempt(self, mock_get):
        """Should return data immediately when no rate limit is encountered."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_get.return_value = mock_response

        result = sync_data()

        assert result == [{"id": 1}, {"id": 2}]
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_retries_once_on_429_then_succeeds(self, mock_get):
        """Should retry after a 429 and succeed on the second attempt."""
        rate_limit_error = make_http_error(429)

        success_response = MagicMock()
        success_response.json.return_value = [{"id": 10}]

        # First call raises 429, second call succeeds
        mock_get.side_effect = [
            _raise_on_raise_for_status(rate_limit_error),
            success_response,
        ]

        with patch("fixed_code.wait_exponential", wraps=_instant_wait):
            result = sync_data()

        assert result == [{"id": 10}]
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_retries_multiple_times_on_429_then_succeeds(self, mock_get):
        """Should retry multiple times on repeated 429s and succeed eventually."""
        rate_limit_error = make_http_error(429)

        success_response = MagicMock()
        success_response.json.return_value = [{"id": 99}]

        mock_get.side_effect = [
            _raise_on_raise_for_status(rate_limit_error),
            _raise_on_raise_for_status(rate_limit_error),
            _raise_on_raise_for_status(rate_limit_error),
            success_response,
        ]

        result = sync_data()
        assert result == [{"id": 99}]
        assert mock_get.call_count == 4

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_500(self, mock_get):
        """Should NOT retry on a 500 error — only 429 triggers retry."""
        server_error = make_http_error(500)
        mock_get.side_effect = _raise_on_raise_for_status(server_error)

        with pytest.raises(HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 500
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_raises_after_max_attempts_exceeded(self, mock_get):
        """Should raise HTTPError after exhausting all retry attempts."""
        rate_limit_error = make_http_error(429)
        # Always raise 429
        mock_get.side_effect = _raise_on_raise_for_status(rate_limit_error)

        with pytest.raises(HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 429
        # 6 attempts total (stop_after_attempt=6)
        assert mock_get.call_count == 6

    @patch("fixed_code.requests.get")
    def test_returns_correct_data_after_retry(self, mock_get):
        """Returned data should be exactly what the API returns after retry."""
        rate_limit_error = make_http_error(429)
        expected_records = [{"id": i, "name": f"record_{i}"} for i in range(5)]

        success_response = MagicMock()
        success_response.json.return_value = expected_records

        mock_get.side_effect = [
            _raise_on_raise_for_status(rate_limit_error),
            success_response,
        ]

        result = sync_data()
        assert result == expected_records
        assert len(result) == 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _raise_on_raise_for_status:
    """
    A callable that, when used as a mock side_effect entry, returns a
    MagicMock whose raise_for_status() raises the given exception.
    This simulates requests.get() returning a response that raises on
    raise_for_status().
    """

    def __init__(self, error):
        self._error = error

    def __call__(self, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = self._error
        return mock_resp

    # Allow use as a single side_effect value (not just in a list)
    def __iter__(self):
        return iter([self])


def _instant_wait(*args, **kwargs):
    """Zero-delay wait strategy for tests — avoids slow exponential sleeps."""
    return 0
