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


def make_http_error(status_code):
    """Helper to create a requests.exceptions.HTTPError with a given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = requests.exceptions.HTTPError(
        f"{status_code} Error", response=mock_response
    )
    return error


def make_success_response(data):
    """Helper to create a successful mock response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = data
    mock_response.raise_for_status.return_value = None
    return mock_response


class TestIsRateLimitError:
    """Unit tests for the is_rate_limit_error predicate."""

    def test_returns_true_for_429_http_error(self):
        error = make_http_error(429)
        assert is_rate_limit_error(error) is True

    def test_returns_false_for_500_http_error(self):
        error = make_http_error(500)
        assert is_rate_limit_error(error) is False

    def test_returns_false_for_404_http_error(self):
        error = make_http_error(404)
        assert is_rate_limit_error(error) is False

    def test_returns_false_for_non_http_error(self):
        error = requests.exceptions.ConnectionError("connection refused")
        assert is_rate_limit_error(error) is False

    def test_returns_false_for_generic_exception(self):
        error = ValueError("not an http error")
        assert is_rate_limit_error(error) is False

    def test_returns_false_for_http_error_without_response(self):
        error = requests.exceptions.HTTPError("error")
        error.response = None
        assert is_rate_limit_error(error) is False


class TestSyncDataRetryLogic:
    """Integration-style tests for sync_data() retry behaviour."""

    @patch("fixed_code.requests.get")
    def test_succeeds_on_first_attempt_no_retry(self, mock_get):
        """sync_data() returns data immediately when no error occurs."""
        expected_data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        mock_get.return_value = make_success_response(expected_data)

        result = sync_data()

        assert result == expected_data
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_retries_once_on_429_then_succeeds(self, mock_get):
        """sync_data() retries after a single 429 and returns data on second attempt."""
        expected_data = [{"id": 3, "name": "Carol"}]
        rate_limit_error = make_http_error(429)
        success_response = make_success_response(expected_data)

        # First call raises 429, second call succeeds
        mock_get.side_effect = [
            MagicMock(
                **{
                    "raise_for_status.side_effect": rate_limit_error,
                    "status_code": 429,
                }
            ),
            success_response,
        ]

        result = sync_data()

        assert result == expected_data
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_retries_multiple_times_on_429_then_succeeds(self, mock_get):
        """sync_data() retries multiple times on repeated 429s and eventually succeeds."""
        expected_data = [{"id": 99}]
        rate_limit_error = make_http_error(429)
        success_response = make_success_response(expected_data)

        def raise_for_status_429():
            raise rate_limit_error

        def make_429_response():
            r = MagicMock()
            r.status_code = 429
            r.raise_for_status.side_effect = rate_limit_error
            return r

        # Fail three times, then succeed
        mock_get.side_effect = [
            make_429_response(),
            make_429_response(),
            make_429_response(),
            success_response,
        ]

        result = sync_data()

        assert result == expected_data
        assert mock_get.call_count == 4

    @patch("fixed_code.requests.get")
    def test_raises_after_max_attempts_exceeded(self, mock_get):
        """sync_data() raises HTTPError after exhausting all retry attempts."""
        rate_limit_error = make_http_error(429)

        def make_429_response():
            r = MagicMock()
            r.status_code = 429
            r.raise_for_status.side_effect = rate_limit_error
            return r

        # Always return 429 — should exhaust 6 attempts
        mock_get.side_effect = [make_429_response() for _ in range(6)]

        with pytest.raises(requests.exceptions.HTTPError):
            sync_data()

        assert mock_get.call_count == 6

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_500_error(self, mock_get):
        """sync_data() does NOT retry on non-429 HTTP errors (e.g. 500)."""
        server_error = make_http_error(500)

        r = MagicMock()
        r.status_code = 500
        r.raise_for_status.side_effect = server_error
        mock_get.return_value = r

        with pytest.raises(requests.exceptions.HTTPError):
            sync_data()

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
    def test_correct_api_url_is_called(self, mock_get):
        """sync_data() calls the correct API endpoint."""
        expected_data = []
        mock_get.return_value = make_success_response(expected_data)

        sync_data()

        mock_get.assert_called_with("http://localhost:8429/api/data", timeout=10)

    @patch("fixed_code.requests.get")
    def test_returns_empty_list_when_api_returns_no_records(self, mock_get):
        """sync_data() handles an empty list response gracefully."""
        mock_get.return_value = make_success_response([])

        result = sync_data()

        assert result == []
        assert mock_get.call_count == 1
