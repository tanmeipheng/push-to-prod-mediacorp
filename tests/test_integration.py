"""
Tests for the Data Sync Worker resilience logic.

Verifies that sync_data() retries on transient 503/connection errors
and eventually succeeds when the service becomes available.
"""

import pytest
from unittest.mock import patch, MagicMock
import requests

# Import the function under test
from fixed_code import sync_data


class TestSyncDataRetryOnConnectionError:
    """Tests retry behavior on ConnectionError (service not running)."""

    @patch("fixed_code.requests.get")
    def test_retries_on_connection_error_then_succeeds(self, mock_get):
        """Should retry after ConnectionError and succeed on the third attempt."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]

        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Connection refused"),
            requests.exceptions.ConnectionError("Connection refused"),
            mock_response,
        ]

        result = sync_data()

        assert result == [{"id": 1}, {"id": 2}]
        assert mock_get.call_count == 3

    @patch("fixed_code.requests.get")
    def test_retries_on_503_then_succeeds(self, mock_get):
        """Should retry after HTTP 503 and succeed on the second attempt."""
        error_response = MagicMock()
        error_response.status_code = 503
        error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "503 Service Unavailable", response=error_response
        )

        success_response = MagicMock()
        success_response.raise_for_status.return_value = None
        success_response.json.return_value = [{"id": 10}, {"id": 20}, {"id": 30}]

        mock_get.side_effect = [error_response, success_response]

        result = sync_data()

        assert result == [{"id": 10}, {"id": 20}, {"id": 30}]
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_retries_on_timeout_then_succeeds(self, mock_get):
        """Should retry after Timeout and succeed on the second attempt."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = ["record_a", "record_b"]

        mock_get.side_effect = [
            requests.exceptions.Timeout("Request timed out"),
            mock_response,
        ]

        result = sync_data()

        assert result == ["record_a", "record_b"]
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_raises_after_all_retries_exhausted(self, mock_get):
        """Should raise ConnectionError after all 5 retry attempts are exhausted."""
        mock_get.side_effect = requests.exceptions.ConnectionError(
            "Connection refused to localhost:8429"
        )

        with pytest.raises(requests.exceptions.ConnectionError):
            sync_data()

        assert mock_get.call_count == 5

    @patch("fixed_code.requests.get")
    def test_succeeds_on_first_attempt_no_retry(self, mock_get):
        """Should succeed immediately without any retries when service is available."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [{"id": 99}]

        mock_get.return_value = mock_response

        result = sync_data()

        assert result == [{"id": 99}]
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_returns_correct_record_count(self, mock_get):
        """Should return the correct number of records from the API response."""
        records = [{"id": i} for i in range(50)]
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = records

        mock_get.return_value = mock_response

        result = sync_data()

        assert len(result) == 50
        assert result == records
