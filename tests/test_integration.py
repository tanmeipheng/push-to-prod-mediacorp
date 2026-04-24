"""
Tests for the Data Sync Worker resilience logic.

Verifies that the sync_data function correctly retries on HTTP 429
Too Many Requests responses using exponential backoff, and eventually
succeeds when the API becomes available.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock, call
from tenacity import RetryError

# Import the module under test
import importlib, sys, types

# We import sync_data from the fixed module
from fixed_code import sync_data, is_rate_limit_error


def make_429_response():
    """Create a mock response object that simulates HTTP 429."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=mock_resp
    )
    return mock_resp


def make_200_response(data):
    """Create a mock response object that simulates a successful HTTP 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = data
    return mock_resp


class TestIsRateLimitError:
    """Unit tests for the is_rate_limit_error predicate."""

    def test_returns_true_for_429_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        exc = requests.exceptions.HTTPError(response=mock_resp)
        assert is_rate_limit_error(exc) is True

    def test_returns_false_for_500_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = requests.exceptions.HTTPError(response=mock_resp)
        assert is_rate_limit_error(exc) is False

    def test_returns_false_for_non_http_error(self):
        exc = requests.exceptions.ConnectionError("connection refused")
        assert is_rate_limit_error(exc) is False

    def test_returns_false_for_generic_exception(self):
        exc = ValueError("unexpected")
        assert is_rate_limit_error(exc) is False

    def test_returns_false_for_http_error_without_response(self):
        exc = requests.exceptions.HTTPError(response=None)
        assert is_rate_limit_error(exc) is False


class TestSyncDataRetryLogic:
    """Integration-style tests for sync_data retry behaviour."""

    @patch("fixed_code.requests.get")
    def test_succeeds_on_first_attempt(self, mock_get):
        """Should return data immediately when the API responds 200 on first call."""
        expected = [{"id": 1, "name": "Alice"}]
        mock_get.return_value = make_200_response(expected)

        result = sync_data()

        assert result == expected
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_retries_once_on_429_then_succeeds(self, mock_get):
        """Should retry after a 429 and succeed on the second attempt."""
        expected = [{"id": 2, "name": "Bob"}]
        mock_get.side_effect = [
            make_429_response(),   # first call → 429
            make_200_response(expected),  # second call → 200
        ]

        result = sync_data()

        assert result == expected
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_retries_multiple_times_on_429_then_succeeds(self, mock_get):
        """Should retry several times on consecutive 429s and succeed eventually."""
        expected = [{"id": 3, "name": "Carol"}]
        mock_get.side_effect = [
            make_429_response(),   # attempt 1 → 429
            make_429_response(),   # attempt 2 → 429
            make_429_response(),   # attempt 3 → 429
            make_200_response(expected),  # attempt 4 → 200
        ]

        result = sync_data()

        assert result == expected
        assert mock_get.call_count == 4

    @patch("fixed_code.requests.get")
    def test_raises_after_exhausting_all_retries(self, mock_get):
        """Should raise HTTPError (reraised) after all 6 attempts are exhausted."""
        mock_get.side_effect = make_429_response  # always returns a new 429 mock

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 429
        # 6 attempts total (1 initial + 5 retries)
        assert mock_get.call_count == 6

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_500_error(self, mock_get):
        """Should NOT retry on non-429 HTTP errors (e.g. 500 Internal Server Error)."""
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        mock_resp_500.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp_500
        )
        mock_get.return_value = mock_resp_500

        with pytest.raises(requests.exceptions.HTTPError):
            sync_data()

        # Only one attempt — no retry for 500
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_connection_error(self, mock_get):
        """Should NOT retry on ConnectionError — only 429 triggers backoff."""
        mock_get.side_effect = requests.exceptions.ConnectionError("refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            sync_data()

        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_returns_correct_data_after_retry(self, mock_get):
        """Returned data should exactly match the API payload after a retry."""
        expected = [{"id": i, "value": i * 10} for i in range(50)]
        mock_get.side_effect = [
            make_429_response(),
            make_200_response(expected),
        ]

        result = sync_data()

        assert len(result) == 50
        assert result == expected
