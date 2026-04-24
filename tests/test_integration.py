"""
Tests for the Data Sync Worker resilience logic.

Verifies that the sync_data() function correctly retries on HTTP 429
responses using exponential backoff, and eventually succeeds when the
rate limit clears.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from requests.exceptions import HTTPError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_429_response():
    """Build a mock requests.Response that looks like a 429."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = HTTPError(
        "429 Too Many Requests", response=mock_resp
    )
    return mock_resp


def _make_200_response(data):
    """Build a mock requests.Response that looks like a successful 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = data
    return mock_resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch("time.sleep", return_value=None)  # suppress actual sleeping
@patch("requests.get")
def test_sync_data_succeeds_after_rate_limit_retries(mock_get, mock_sleep):
    """
    sync_data() should retry on 429 responses and return data on success.
    Simulates two 429 responses followed by a successful 200.
    """
    expected_data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    mock_get.side_effect = [
        _make_429_response(),   # attempt 1 → 429
        _make_429_response(),   # attempt 2 → 429
        _make_200_response(expected_data),  # attempt 3 → 200
    ]

    # Import here so tenacity decorators are applied after patching sleep
    from fixed_code import sync_data

    result = sync_data()

    assert result == expected_data
    assert mock_get.call_count == 3


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_succeeds_on_first_attempt(mock_get, mock_sleep):
    """
    sync_data() should return data immediately when no rate limit occurs.
    """
    expected_data = [{"id": 10, "name": "Charlie"}]

    mock_get.return_value = _make_200_response(expected_data)

    from fixed_code import sync_data

    result = sync_data()

    assert result == expected_data
    assert mock_get.call_count == 1


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_raises_after_max_retries(mock_get, mock_sleep):
    """
    sync_data() should raise HTTPError after exhausting all retry attempts
    (configured as 6 attempts).
    """
    mock_get.return_value = _make_429_response()

    from fixed_code import sync_data

    with pytest.raises(HTTPError):
        sync_data()

    # 6 attempts total (1 initial + 5 retries)
    assert mock_get.call_count == 6


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_does_not_retry_on_non_429_errors(mock_get, mock_sleep):
    """
    sync_data() should NOT retry on non-429 HTTP errors (e.g., 500).
    The error should propagate immediately.
    """
    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500
    mock_resp_500.raise_for_status.side_effect = HTTPError(
        "500 Internal Server Error", response=mock_resp_500
    )
    mock_get.return_value = mock_resp_500

    from fixed_code import sync_data

    with pytest.raises(HTTPError):
        sync_data()

    # Should only be called once — no retries for 500
    assert mock_get.call_count == 1


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_single_retry_then_success(mock_get, mock_sleep):
    """
    sync_data() should succeed after exactly one 429 retry.
    """
    expected_data = [{"id": 99, "name": "Dana"}]

    mock_get.side_effect = [
        _make_429_response(),              # attempt 1 → 429
        _make_200_response(expected_data), # attempt 2 → 200
    ]

    from fixed_code import sync_data

    result = sync_data()

    assert result == expected_data
    assert mock_get.call_count == 2
