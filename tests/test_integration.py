"""
Pytest test suite for the Data Sync Worker resilience logic.

Verifies that the exponential backoff retry decorator correctly handles
HTTP 429 Too Many Requests responses from the Partner API.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from requests.exceptions import HTTPError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_http_error(status_code: int) -> HTTPError:
    """Build a requests.HTTPError with a mocked response attached."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = HTTPError(response=mock_response)
    return error


def _make_ok_response(data: list) -> MagicMock:
    """Build a successful requests.Response mock."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = data
    mock_response.raise_for_status.return_value = None
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSyncDataRetryOn429:

    @patch("requests.get")
    def test_succeeds_on_first_attempt_no_retry(self, mock_get):
        """When the API responds 200 immediately, no retry should occur."""
        expected_data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        mock_get.return_value = _make_ok_response(expected_data)

        # Re-import to pick up the patched requests.get
        from fixed_code import sync_data

        result = sync_data()

        assert result == expected_data
        assert mock_get.call_count == 1

    @patch("requests.get")
    def test_retries_once_on_429_then_succeeds(self, mock_get):
        """
        When the API returns 429 on the first call and 200 on the second,
        the function should retry and ultimately return the data.
        """
        expected_data = [{"id": 10, "name": "Carol"}]

        # First call raises 429, second call succeeds
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_error = HTTPError(response=rate_limit_response)

        ok_response = _make_ok_response(expected_data)

        mock_get.side_effect = [
            MagicMock(**{
                "raise_for_status.side_effect": rate_limit_error,
                "status_code": 429,
            }),
            ok_response,
        ]

        # Patch raise_for_status on the first mock to raise the error
        first_response = MagicMock()
        first_response.status_code = 429
        first_response.raise_for_status.side_effect = rate_limit_error

        mock_get.side_effect = [first_response, ok_response]

        from fixed_code import sync_data

        result = sync_data()

        assert result == expected_data
        assert mock_get.call_count == 2

    @patch("requests.get")
    def test_retries_multiple_times_on_429_then_succeeds(self, mock_get):
        """
        When the API returns 429 three times in a row before succeeding,
        the function should retry up to the configured limit and return data.
        """
        expected_data = [{"id": 99}]

        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_error = HTTPError(response=rate_limit_response)

        def make_429_mock():
            m = MagicMock()
            m.status_code = 429
            m.raise_for_status.side_effect = rate_limit_error
            return m

        ok_response = _make_ok_response(expected_data)

        mock_get.side_effect = [
            make_429_mock(),
            make_429_mock(),
            make_429_mock(),
            ok_response,
        ]

        from fixed_code import sync_data

        result = sync_data()

        assert result == expected_data
        assert mock_get.call_count == 4

    @patch("requests.get")
    def test_raises_after_max_attempts_exceeded(self, mock_get):
        """
        When the API keeps returning 429 beyond the maximum retry attempts,
        the function should eventually re-raise the HTTPError.
        """
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_error = HTTPError(response=rate_limit_response)

        def make_429_mock():
            m = MagicMock()
            m.status_code = 429
            m.raise_for_status.side_effect = rate_limit_error
            return m

        # Always return 429 — more than the 6-attempt limit
        mock_get.side_effect = [make_429_mock() for _ in range(10)]

        from fixed_code import sync_data

        with pytest.raises(HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 429
        # Should have tried exactly 6 times (stop_after_attempt=6)
        assert mock_get.call_count == 6

    @patch("requests.get")
    def test_does_not_retry_on_non_429_http_error(self, mock_get):
        """
        Non-429 HTTP errors (e.g. 500 Internal Server Error) should NOT
        trigger a retry — they should propagate immediately.
        """
        server_error_response = MagicMock()
        server_error_response.status_code = 500
        server_error = HTTPError(response=server_error_response)

        error_mock = MagicMock()
        error_mock.status_code = 500
        error_mock.raise_for_status.side_effect = server_error

        mock_get.return_value = error_mock

        from fixed_code import sync_data

        with pytest.raises(HTTPError) as exc_info:
            sync_data()

        assert exc_info.value.response.status_code == 500
        # Must NOT retry on 500 — only one attempt
        assert mock_get.call_count == 1

    @patch("requests.get")
    def test_returns_correct_data_after_retry(self, mock_get):
        """
        Verify the exact payload returned after a successful retry
        matches what the API responded with.
        """
        expected_data = [
            {"id": 1, "value": "alpha"},
            {"id": 2, "value": "beta"},
            {"id": 3, "value": "gamma"},
        ]

        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_error = HTTPError(response=rate_limit_response)

        first_response = MagicMock()
        first_response.status_code = 429
        first_response.raise_for_status.side_effect = rate_limit_error

        ok_response = _make_ok_response(expected_data)

        mock_get.side_effect = [first_response, ok_response]

        from fixed_code import sync_data

        result = sync_data()

        assert result == expected_data
        assert len(result) == 3
        assert result[0]["value"] == "alpha"
