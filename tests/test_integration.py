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


def make_429_response():
    """Create a mock response object that simulates HTTP 429."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    http_error = HTTPError(response=mock_resp)
    http_error.response = mock_resp
    return mock_resp, http_error


def make_200_response(data):
    """Create a mock response object that simulates HTTP 200 with JSON data."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = data
    mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestIsRateLimitError:
    """Unit tests for the is_rate_limit_error predicate."""

    def test_returns_true_for_429_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        exc = HTTPError(response=mock_resp)
        exc.response = mock_resp
        assert is_rate_limit_error(exc) is True

    def test_returns_false_for_500_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = HTTPError(response=mock_resp)
        exc.response = mock_resp
        assert is_rate_limit_error(exc) is False

    def test_returns_false_for_non_http_error(self):
        assert is_rate_limit_error(ValueError("not an http error")) is False

    def test_returns_false_for_http_error_without_response(self):
        exc = HTTPError()
        exc.response = None
        assert is_rate_limit_error(exc) is False


class TestSyncDataRetryLogic:
    """Integration-style tests for sync_data() retry behaviour."""

    @patch("fixed_code.requests.get")
    def test_succeeds_on_first_attempt(self, mock_get):
        """sync_data() returns data immediately when the API responds 200."""
        expected = [{"id": 1, "name": "Alice"}]
        mock_get.return_value = make_200_response(expected)

        result = sync_data()

        assert result == expected
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_retries_once_on_429_then_succeeds(self, mock_get):
        """sync_data() retries after a 429 and returns data on the second call."""
        expected = [{"id": 2, "name": "Bob"}]
        mock_resp_429, http_error_429 = make_429_response()
        mock_resp_429.raise_for_status.side_effect = http_error_429

        mock_resp_200 = make_200_response(expected)

        mock_get.side_effect = [mock_resp_429, mock_resp_200]

        # Patch wait to avoid sleeping in tests
        with patch("fixed_code.sync_data.retry.wait", return_value=0):
            result = sync_data()

        assert result == expected
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_retries_multiple_times_on_429_then_succeeds(self, mock_get):
        """sync_data() retries multiple times on consecutive 429s then succeeds."""
        expected = [{"id": 3, "name": "Carol"}]

        def make_raising_429():
            mock_resp_429, http_error_429 = make_429_response()
            mock_resp_429.raise_for_status.side_effect = http_error_429
            return mock_resp_429

        mock_resp_200 = make_200_response(expected)
        mock_get.side_effect = [
            make_raising_429(),
            make_raising_429(),
            make_raising_429(),
            mock_resp_200,
        ]

        with patch("fixed_code.sync_data.retry.wait", return_value=0):
            result = sync_data()

        assert result == expected
        assert mock_get.call_count == 4

    @patch("fixed_code.requests.get")
    def test_raises_after_max_attempts_exceeded(self, mock_get):
        """sync_data() raises HTTPError after exhausting all retry attempts."""
        mock_resp_429, http_error_429 = make_429_response()
        mock_resp_429.raise_for_status.side_effect = http_error_429

        # Always return 429
        mock_get.return_value = mock_resp_429

        with patch("fixed_code.sync_data.retry.wait", return_value=0):
            with pytest.raises(HTTPError):
                sync_data()

        # 6 attempts maximum (stop_after_attempt=6)
        assert mock_get.call_count == 6

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_500_error(self, mock_get):
        """sync_data() does NOT retry on non-429 HTTP errors (e.g. 500)."""
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        http_error_500 = HTTPError(response=mock_resp_500)
        http_error_500.response = mock_resp_500
        mock_resp_500.raise_for_status.side_effect = http_error_500

        mock_get.return_value = mock_resp_500

        with pytest.raises(HTTPError):
            sync_data()

        # Should only be called once — no retry for 500
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_returns_correct_data_structure(self, mock_get):
        """sync_data() correctly returns the parsed JSON payload."""
        expected = [
            {"id": 10, "name": "Dave", "active": True},
            {"id": 11, "name": "Eve", "active": False},
        ]
        mock_get.return_value = make_200_response(expected)

        result = sync_data()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "Dave"
        assert result[1]["name"] == "Eve"
