"""
Tests for the Data Sync Worker resilience logic.

Verifies that sync_data() correctly retries on HTTP 429 responses
using exponential backoff and eventually succeeds.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from requests.exceptions import HTTPError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_429_error() -> HTTPError:
    """Build a realistic HTTPError that looks like a 429 response."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    error = HTTPError("429 Too Many Requests", response=mock_response)
    return error


def _make_ok_response(data: list) -> MagicMock:
    """Build a mock response that returns HTTP 200 with JSON data."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = data
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch("worker.requests.get")
def test_sync_data_succeeds_on_first_try(mock_get):
    """When the API returns 200 immediately, sync_data returns the records."""
    expected = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    mock_get.return_value = _make_ok_response(expected)

    from worker import sync_data
    result = sync_data()

    assert result == expected
    assert mock_get.call_count == 1


@patch("worker.requests.get")
def test_sync_data_retries_on_429_then_succeeds(mock_get):
    """
    When the API returns 429 twice and then 200, sync_data should retry
    and ultimately return the records.
    """
    expected = [{"id": 3, "name": "Carol"}]

    # First two calls raise 429, third call succeeds
    ok_response = _make_ok_response(expected)

    def side_effect(*args, **kwargs):
        if mock_get.call_count <= 2:
            raise _make_429_error()
        return ok_response

    mock_get.side_effect = side_effect

    from worker import sync_data
    # Patch wait to avoid sleeping during tests
    with patch("worker.sync_data.retry.sleep", return_value=None):
        result = sync_data()

    assert result == expected
    assert mock_get.call_count == 3


@patch("worker.requests.get")
def test_sync_data_retries_on_single_429_then_succeeds(mock_get):
    """
    When the API returns 429 once and then 200, sync_data should retry
    exactly once and return the records.
    """
    expected = [{"id": 10, "name": "Dave"}]
    ok_response = _make_ok_response(expected)

    mock_get.side_effect = [
        _make_429_error(),
        ok_response,
    ]

    from worker import sync_data
    with patch("tenacity.nap.time") as mock_sleep:
        result = sync_data()

    assert result == expected
    assert mock_get.call_count == 2


@patch("worker.requests.get")
def test_sync_data_raises_after_max_attempts(mock_get):
    """
    When the API keeps returning 429 beyond the retry limit,
    sync_data should eventually raise HTTPError.
    """
    mock_get.side_effect = _make_429_error

    from worker import sync_data
    from tenacity import RetryError

    with patch("tenacity.nap.time"):
        with pytest.raises((HTTPError, RetryError)):
            sync_data()

    # Should have attempted exactly 6 times (stop_after_attempt=6)
    assert mock_get.call_count == 6


@patch("worker.requests.get")
def test_sync_data_does_not_retry_on_500(mock_get):
    """
    A non-429 HTTP error (e.g. 500) should NOT be retried — it should
    propagate immediately.
    """
    mock_response = MagicMock()
    mock_response.status_code = 500
    http_error = HTTPError("500 Internal Server Error", response=mock_response)
    mock_get.return_value.raise_for_status.side_effect = http_error

    from worker import sync_data
    with pytest.raises(HTTPError):
        sync_data()

    # Should only have been called once — no retries for 500
    assert mock_get.call_count == 1


@patch("worker.requests.get")
def test_sync_data_returns_correct_record_count(mock_get):
    """Verify that the returned list length matches the mocked payload."""
    records = [{"id": i} for i in range(50)]
    mock_get.return_value = _make_ok_response(records)

    from worker import sync_data
    result = sync_data()

    assert len(result) == 50
