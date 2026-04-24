"""
Tests for the Data Sync Worker resilience logic.

Verifies that the sync_data() function correctly retries on HTTP 429
responses using exponential backoff, and eventually succeeds when the
partner API becomes available.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock, call
from tenacity import RetryError

# Import the module under test
import importlib, sys, types

# We import sync_data from the fixed module
from fixed_code import sync_data, is_rate_limit_error


def make_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Helper to create an HTTPError with a given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = requests.exceptions.HTTPError(
        f"{status_code} Error", response=mock_response
    )
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
        error = ConnectionError("connection refused")
        assert is_rate_limit_error(error) is False

    def test_returns_false_for_http_error_without_response(self):
        error = requests.exceptions.HTTPError("no response")
        error.response = None
        assert is_rate_limit_error(error) is False


class TestSyncDataRetryLogic:
    """Integration-style tests for sync_data() retry behaviour."""

    @patch("fixed_code.requests.get")
    def test_succeeds_on_first_attempt(self, mock_get):
        """Should return data immediately when the API responds 200 on first call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_get.return_value = mock_response

        result = sync_data()

        assert result == [{"id": 1}, {"id": 2}]
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_retries_once_on_429_then_succeeds(self, mock_get):
        """Should retry after a single 429 and return data on the second attempt."""
        rate_limit_error = make_http_error(429)

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = [{"id": 10}]

        # First call raises 429, second call succeeds
        mock_get.side_effect = [
            MagicMock(**{
                "raise_for_status.side_effect": rate_limit_error,
                "status_code": 429,
            }),
            success_response,
        ]

        result = sync_data()

        assert result == [{"id": 10}]
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_retries_multiple_times_on_429_then_succeeds(self, mock_get):
        """Should retry up to N times on repeated 429s and succeed eventually."""
        rate_limit_error = make_http_error(429)

        def make_429_mock():
            m = MagicMock()
            m.raise_for_status.side_effect = rate_limit_error
            return m

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = [{"id": 99}]

        # Fail three times, then succeed
        mock_get.side_effect = [
            make_429_mock(),
            make_429_mock(),
            make_429_mock(),
            success_response,
        ]

        result = sync_data()

        assert result == [{"id": 99}]
        assert mock_get.call_count == 4

    @patch("fixed_code.requests.get")
    def test_raises_after_max_attempts_exceeded(self, mock_get):
        """Should raise HTTPError (reraise=True) after exhausting all retry attempts."""
        rate_limit_error = make_http_error(429)

        def make_429_mock():
            m = MagicMock()
            m.raise_for_status.side_effect = rate_limit_error
            return m

        # Always return 429 — more than the max 6 attempts
        mock_get.side_effect = [make_429_mock() for _ in range(10)]

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 429
        # Should have tried exactly 6 times (stop_after_attempt=6)
        assert mock_get.call_count == 6

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_500_error(self, mock_get):
        """Should NOT retry on non-429 HTTP errors (e.g. 500 Internal Server Error)."""
        server_error = make_http_error(500)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = server_error
        mock_get.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 500
        # Must NOT retry — only one attempt
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_connection_error(self, mock_get):
        """Should NOT retry on non-rate-limit network errors."""
        mock_get.side_effect = requests.exceptions.ConnectionError("refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            sync_data()

        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_returns_correct_data_structure(self, mock_get):
        """Returned data should match exactly what the API JSON response contains."""
        payload = [{"id": i, "name": f"record_{i}"} for i in range(50)]
        mock_response = MagicMock()
        mock_response.json.return_value = payload
        mock_get.return_value = mock_response

        result = sync_data()

        assert len(result) == 50
        assert result[0] == {"id": 0, "name": "record_0"}
        assert result[-1] == {"id": 49, "name": "record_49"}
