"""
Tests for the Data Sync Worker resilience logic.

Verifies that the sync_data function correctly retries on HTTP 429
responses using exponential backoff, and eventually succeeds when
the rate limit clears.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock, call


def make_http_error(status_code):
    """Helper to create a requests.exceptions.HTTPError with a given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = requests.exceptions.HTTPError(
        f"{status_code} Error", response=mock_response
    )
    return error


class TestSyncDataRetryOn429:

    @patch("requests.get")
    def test_succeeds_on_first_attempt(self, mock_get):
        """sync_data should return data immediately when no rate limit occurs."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Re-import to get the decorated version
        from fixed_code import sync_data

        result = sync_data()

        assert result == [{"id": 1}, {"id": 2}]
        assert mock_get.call_count == 1

    @patch("requests.get")
    def test_retries_on_429_then_succeeds(self, mock_get):
        """sync_data should retry after a 429 and succeed on a subsequent attempt."""
        rate_limit_error = make_http_error(429)

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = [{"id": 10}, {"id": 20}, {"id": 30}]
        success_response.raise_for_status = MagicMock()

        # First two calls raise 429, third call succeeds
        mock_get.side_effect = [
            MagicMock(**{
                "status_code": 429,
                "raise_for_status.side_effect": rate_limit_error,
            }),
            MagicMock(**{
                "status_code": 429,
                "raise_for_status.side_effect": make_http_error(429),
            }),
            success_response,
        ]

        from fixed_code import sync_data
        from tenacity import wait_none

        # Patch wait to avoid sleeping in tests
        sync_data.retry.wait = wait_none()

        result = sync_data()

        assert result == [{"id": 10}, {"id": 20}, {"id": 30}]
        assert mock_get.call_count == 3

    @patch("requests.get")
    def test_raises_after_exhausting_retries(self, mock_get):
        """sync_data should raise after exhausting all retry attempts."""
        from fixed_code import sync_data
        from tenacity import wait_none

        sync_data.retry.wait = wait_none()

        # Always return 429
        mock_get.side_effect = [
            MagicMock(**{
                "status_code": 429,
                "raise_for_status.side_effect": make_http_error(429),
            })
            for _ in range(10)
        ]

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 429
        # Should have retried up to stop_after_attempt(6) times
        assert mock_get.call_count == 6

    @patch("requests.get")
    def test_does_not_retry_on_non_429_http_error(self, mock_get):
        """sync_data should NOT retry on non-429 HTTP errors (e.g., 500)."""
        from fixed_code import sync_data
        from tenacity import wait_none

        sync_data.retry.wait = wait_none()

        server_error = make_http_error(500)
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = server_error
        mock_get.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 500
        # Should NOT retry — only one attempt
        assert mock_get.call_count == 1

    @patch("requests.get")
    def test_single_429_then_success_call_count(self, mock_get):
        """Verify exactly 2 total calls when first attempt is 429 and second succeeds."""
        from fixed_code import sync_data
        from tenacity import wait_none

        sync_data.retry.wait = wait_none()

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = ["record_a", "record_b"]
        success_response.raise_for_status = MagicMock()

        mock_get.side_effect = [
            MagicMock(**{
                "status_code": 429,
                "raise_for_status.side_effect": make_http_error(429),
            }),
            success_response,
        ]

        result = sync_data()

        assert result == ["record_a", "record_b"]
        assert mock_get.call_count == 2
