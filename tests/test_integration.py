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

def _make_429_response():
    """Build a mock response that looks like an HTTP 429."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    http_error = HTTPError(response=mock_resp)
    mock_resp.raise_for_status.side_effect = http_error
    return mock_resp


def _make_200_response(payload):
    """Build a mock response that looks like a successful HTTP 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = payload
    return mock_resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch("time.sleep", return_value=None)  # suppress real sleeping
@patch("requests.get")
def test_sync_data_succeeds_after_one_429(mock_get, mock_sleep):
    """sync_data should retry once after a 429 and return data on success."""
    payload = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    mock_get.side_effect = [
        _make_429_response(),   # first call → 429
        _make_200_response(payload),  # second call → 200
    ]

    from worker import sync_data
    result = sync_data()

    assert result == payload
    assert mock_get.call_count == 2


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_succeeds_after_multiple_429s(mock_get, mock_sleep):
    """sync_data should retry multiple times on consecutive 429s."""
    payload = [{"id": 3, "name": "Charlie"}]
    mock_get.side_effect = [
        _make_429_response(),
        _make_429_response(),
        _make_429_response(),
        _make_200_response(payload),
    ]

    from worker import sync_data
    result = sync_data()

    assert result == payload
    assert mock_get.call_count == 4


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_raises_after_max_attempts(mock_get, mock_sleep):
    """sync_data should raise HTTPError after exhausting all retry attempts."""
    # Return 429 more times than the max retry attempts (6)
    mock_get.side_effect = [_make_429_response() for _ in range(7)]

    from worker import sync_data
    from requests.exceptions import HTTPError

    with pytest.raises(HTTPError):
        sync_data()

    assert mock_get.call_count == 6  # stop_after_attempt(6)


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_does_not_retry_on_non_429_error(mock_get, mock_sleep):
    """sync_data should NOT retry on non-429 HTTP errors (e.g. 500)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    http_error = HTTPError(response=mock_resp)
    mock_resp.raise_for_status.side_effect = http_error
    mock_get.return_value = mock_resp

    from worker import sync_data
    from requests.exceptions import HTTPError

    with pytest.raises(HTTPError):
        sync_data()

    # Should only be called once — no retry for 500
    assert mock_get.call_count == 1


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_succeeds_on_first_try(mock_get, mock_sleep):
    """sync_data should return data immediately when no 429 occurs."""
    payload = [{"id": 10, "name": "Dave"}]
    mock_get.return_value = _make_200_response(payload)

    from worker import sync_data
    result = sync_data()

    assert result == payload
    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()
