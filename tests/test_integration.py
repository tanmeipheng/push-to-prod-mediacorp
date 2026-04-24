"""
Tests for the Data Sync Worker resilience logic.

Verifies that sync_data() correctly retries on HTTP 429 responses
using exponential backoff and eventually succeeds.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock, call

# Import the module under test
import importlib, sys, types

# We import the fixed module directly
from fixed_code import sync_data, is_rate_limit_error


def make_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Helper to create an HTTPError with a mocked response."""
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
        """sync_data() returns data immediately when no error occurs."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_get.return_value = mock_response

        result = sync_data()

        assert result == [{"id": 1}, {"id": 2}]
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_retries_once_on_429_then_succeeds(self, mock_get):
        """sync_data() retries after a single 429 and returns data on success."""
        rate_limit_error = make_http_error(429)

        success_response = MagicMock()
        success_response.json.return_value = [{"id": 10}]

        mock_get.side_effect = [
            rate_limit_error,   # first call → 429
            success_response,   # second call → success
        ]

        result = sync_data()

        assert result == [{"id": 10}]
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_retries_multiple_times_on_429_then_succeeds(self, mock_get):
        """sync_data() retries several times on repeated 429s before succeeding."""
        rate_limit_error = make_http_error(429)

        success_response = MagicMock()
        success_response.json.return_value = [{"id": 99}]

        mock_get.side_effect = [
            rate_limit_error,   # attempt 1
            rate_limit_error,   # attempt 2
            rate_limit_error,   # attempt 3
            success_response,   # attempt 4 → success
        ]

        result = sync_data()

        assert result == [{"id": 99}]
        assert mock_get.call_count == 4

    @patch("fixed_code.requests.get")
    def test_raises_after_max_attempts_exceeded(self, mock_get):
        """sync_data() raises HTTPError after exhausting all retry attempts."""
        rate_limit_error = make_http_error(429)
        # Always return 429 — more than the max 6 attempts
        mock_get.side_effect = rate_limit_error

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 429
        assert mock_get.call_count == 6  # stop_after_attempt(6)

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_non_429_http_error(self, mock_get):
        """sync_data() does NOT retry on non-429 HTTP errors (e.g. 500)."""
        server_error = make_http_error(500)
        mock_get.side_effect = server_error

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 500
        # Should only be called once — no retry for 500
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_connection_error(self, mock_get):
        """sync_data() does NOT retry on ConnectionError (not a 429)."""
        mock_get.side_effect = requests.exceptions.ConnectionError("refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            sync_data()

        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_returns_empty_list_when_api_returns_no_records(self, mock_get):
        """sync_data() handles an empty list response gracefully."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = sync_data()

        assert result == []
        assert mock_get.call_count == 1
