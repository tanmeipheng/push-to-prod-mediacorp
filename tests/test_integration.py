"""
Tests for the resilience logic in the Metrics Collector module.

Verifies that collect_metrics retries on ReadTimeout and eventually
succeeds when the underlying request recovers.
"""

import pytest
from unittest.mock import patch, MagicMock
import requests

# Import the function under test
from fixed_code import collect_metrics


class TestCollectMetricsRetry:

    @patch("fixed_code.requests.get")
    def test_succeeds_on_first_attempt(self, mock_get):
        """Should return data immediately when no error occurs."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"metric": "cpu", "value": 42}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = collect_metrics()

        assert result == [{"metric": "cpu", "value": 42}]
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_retries_on_read_timeout_then_succeeds(self, mock_get):
        """Should retry after ReadTimeout and succeed on a subsequent attempt."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"metric": "memory", "value": 75}]
        mock_response.raise_for_status.return_value = None

        # Fail twice with ReadTimeout, then succeed
        mock_get.side_effect = [
            requests.exceptions.ReadTimeout("Read timed out."),
            requests.exceptions.ReadTimeout("Read timed out."),
            mock_response,
        ]

        result = collect_metrics()

        assert result == [{"metric": "memory", "value": 75}]
        assert mock_get.call_count == 3

    @patch("fixed_code.requests.get")
    def test_retries_on_connection_error_then_succeeds(self, mock_get):
        """Should retry after ConnectionError and succeed on a subsequent attempt."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"metric": "disk", "value": 55}]
        mock_response.raise_for_status.return_value = None

        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Connection refused."),
            mock_response,
        ]

        result = collect_metrics()

        assert result == [{"metric": "disk", "value": 55}]
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_raises_after_max_attempts_exceeded(self, mock_get):
        """Should raise ReadTimeout after exhausting all retry attempts."""
        mock_get.side_effect = requests.exceptions.ReadTimeout("Read timed out.")

        with pytest.raises(requests.exceptions.ReadTimeout):
            collect_metrics()

        # 5 attempts total (stop_after_attempt=5)
        assert mock_get.call_count == 5

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_http_error(self, mock_get):
        """Should NOT retry on non-transient HTTP errors (e.g., 404)."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Client Error"
        )
        mock_get.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            collect_metrics()

        # Should only be called once — HTTPError is not retried
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_returns_correct_data_after_retry(self, mock_get):
        """Verify the returned data is from the successful response, not a failed one."""
        expected_data = [
            {"metric": "cpu", "value": 10},
            {"metric": "memory", "value": 20},
            {"metric": "disk", "value": 30},
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = expected_data
        mock_response.raise_for_status.return_value = None

        mock_get.side_effect = [
            requests.exceptions.ReadTimeout("Timeout"),
            mock_response,
        ]

        result = collect_metrics()

        assert len(result) == 3
        assert result == expected_data
        assert mock_get.call_count == 2
