"""
Tests for the Data Sync Worker resilience logic.

Verifies that sync_data() correctly retries on HTTP 429 responses
and eventually succeeds when the rate limit clears.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock, call

# Import the module under test
import importlib, sys, types

# We import the fixed module
from fixed_code import sync_data, is_rate_limit_error


def make_http_error(status_code):
    """Helper to create a requests.exceptions.HTTPError with a given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = requests.exceptions.HTTPError(
        f"{status_code} Error", response=mock_response
    )
    return error


class TestIsRateLimitError:
    def test_returns_true_for_429(self):
        error = make_http_error(429)
        assert is_rate_limit_error(error) is True

    def test_returns_false_for_500(self):
        error = make_http_error(500)
        assert is_rate_limit_error(error) is False

    def test_returns_false_for_non_http_error(self):
        error = ConnectionError("connection refused")
        assert is_rate_limit_error(error) is False

    def test_returns_false_when_response_is_none(self):
        error = requests.exceptions.HTTPError("no response")
        error.response = None
        assert is_rate_limit_error(error) is False


class TestSyncDataRetryOnRateLimit:
    @patch("fixed_code.requests.get")
    def test_succeeds_on_first_attempt(self, mock_get):
        """Should return data immediately when no rate limit is hit."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = sync_data()

        assert result == [{"id": 1}, {"id": 2}]
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_retries_once_on_429_then_succeeds(self, mock_get):
        """Should retry after a 429 and succeed on the second attempt."""
        rate_limit_error = make_http_error(429)

        mock_success_response = MagicMock()
        mock_success_response.json.return_value = [{"id": 10}]
        mock_success_response.raise_for_status.return_value = None

        # First call raises 429, second call succeeds
        mock_get.side_effect = [
            MagicMock(**{
                "raise_for_status.side_effect": rate_limit_error,
            }),
            mock_success_response,
        ]

        result = sync_data()

        assert result == [{"id": 10}]
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_retries_multiple_times_on_429_then_succeeds(self, mock_get):
        """Should retry multiple times on repeated 429s and succeed eventually."""
        rate_limit_error_1 = make_http_error(429)
        rate_limit_error_2 = make_http_error(429)
        rate_limit_error_3 = make_http_error(429)

        mock_success_response = MagicMock()
        mock_success_response.json.return_value = [{"id": 99}]
        mock_success_response.raise_for_status.return_value = None

        mock_get.side_effect = [
            MagicMock(**{"raise_for_status.side_effect": rate_limit_error_1}),
            MagicMock(**{"raise_for_status.side_effect": rate_limit_error_2}),
            MagicMock(**{"raise_for_status.side_effect": rate_limit_error_3}),
            mock_success_response,
        ]

        result = sync_data()

        assert result == [{"id": 99}]
        assert mock_get.call_count == 4

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_500_error(self, mock_get):
        """Should NOT retry on non-429 HTTP errors (e.g., 500)."""
        server_error = make_http_error(500)

        mock_get.return_value = MagicMock(
            **{"raise_for_status.side_effect": server_error}
        )

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 500
        # Should only be called once — no retry for 500
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_raises_after_max_attempts_exceeded(self, mock_get):
        """Should raise HTTPError after exhausting all retry attempts."""
        def always_429(*args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = make_http_error(429)
            return mock_resp

        mock_get.side_effect = always_429

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 429
        # tenacity stop_after_attempt(6) means 6 total attempts
        assert mock_get.call_count == 6

    @patch("fixed_code.requests.get")
    def test_returns_correct_data_after_retry(self, mock_get):
        """Verify the actual data payload is correctly returned after retry."""
        records = [{"id": i, "name": f"record_{i}"} for i in range(5)]

        rate_limit_error = make_http_error(429)
        mock_success_response = MagicMock()
        mock_success_response.json.return_value = records
        mock_success_response.raise_for_status.return_value = None

        mock_get.side_effect = [
            MagicMock(**{"raise_for_status.side_effect": rate_limit_error}),
            mock_success_response,
        ]

        result = sync_data()

        assert len(result) == 5
        assert result[0]["name"] == "record_0"
        assert result[4]["name"] == "record_4"
