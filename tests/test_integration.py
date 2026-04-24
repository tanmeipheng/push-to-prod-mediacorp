"""
Tests for the Data Sync Worker resilience logic.

Verifies that the sync_data() function correctly retries on HTTP 429
Too Many Requests responses using exponential backoff, and eventually
succeeds when the rate limit clears.
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
    error = HTTPError(f"{status_code} Error", response=mock_response)
    return error


def _make_ok_response(data: list) -> MagicMock:
    """Build a successful requests.Response mock."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = data
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSyncDataRetryOn429:

    @patch("time.sleep", return_value=None)  # suppress actual sleeping
    @patch("requests.get")
    def test_retries_on_429_then_succeeds(self, mock_get, mock_sleep):
        """
        sync_data() should retry when it receives a 429 and ultimately
        return the data once the API responds with 200.
        """
        from worker import sync_data  # import after patching

        expected_data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

        # First two calls raise 429; third call succeeds.
        rate_limit_error = _make_http_error(429)
        ok_response = _make_ok_response(expected_data)

        mock_get.return_value = MagicMock()
        # Simulate raise_for_status raising on 429 responses
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.raise_for_status.side_effect = rate_limit_error

        ok_resp = _make_ok_response(expected_data)

        mock_get.side_effect = [
            rate_limit_response,  # 1st attempt → 429
            rate_limit_response,  # 2nd attempt → 429
            ok_resp,              # 3rd attempt → 200
        ]

        result = sync_data()

        assert result == expected_data
        assert mock_get.call_count == 3

    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_succeeds_on_first_attempt(self, mock_get, mock_sleep):
        """
        sync_data() should return immediately when the first call succeeds
        without any retries.
        """
        from worker import sync_data

        expected_data = [{"id": 99}]
        mock_get.return_value = _make_ok_response(expected_data)

        result = sync_data()

        assert result == expected_data
        assert mock_get.call_count == 1

    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_raises_after_max_attempts(self, mock_get, mock_sleep):
        """
        sync_data() should re-raise the HTTPError after exhausting all
        retry attempts (6 attempts configured).
        """
        from worker import sync_data
        from requests.exceptions import HTTPError

        rate_limit_error = _make_http_error(429)
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.raise_for_status.side_effect = rate_limit_error

        mock_get.return_value = rate_limit_response

        with pytest.raises(HTTPError):
            sync_data()

        # Should have tried exactly 6 times (stop_after_attempt=6)
        assert mock_get.call_count == 6

    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_does_not_retry_on_non_429_http_error(self, mock_get, mock_sleep):
        """
        sync_data() should NOT retry on non-429 HTTP errors (e.g. 500).
        The error should propagate immediately.
        """
        from worker import sync_data
        from requests.exceptions import HTTPError

        server_error = _make_http_error(500)
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = server_error

        mock_get.return_value = error_response

        with pytest.raises(HTTPError):
            sync_data()

        # Should have tried only once — no retry for 500
        assert mock_get.call_count == 1

    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_single_429_then_success_returns_correct_data(self, mock_get, mock_sleep):
        """
        Verify the exact data returned after a single 429 retry.
        """
        from worker import sync_data

        expected_data = [{"record": "x"}, {"record": "y"}, {"record": "z"}]

        rate_limit_error = _make_http_error(429)
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.raise_for_status.side_effect = rate_limit_error

        ok_resp = _make_ok_response(expected_data)

        mock_get.side_effect = [rate_limit_response, ok_resp]

        result = sync_data()

        assert result == expected_data
        assert mock_get.call_count == 2
