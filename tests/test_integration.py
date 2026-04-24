"""
Tests for the Data Sync Worker resilience logic.

Verifies that sync_data() correctly retries on HTTP 429 responses
using exponential backoff and eventually succeeds.
"""

import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import HTTPError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_http_error(status_code: int) -> HTTPError:
    """Build a requests.HTTPError with a fake response attached."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = HTTPError(response=mock_response)
    return error


def _make_ok_response(payload):
    """Build a successful mock response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch("requests.get")
def test_sync_data_succeeds_on_first_try(mock_get):
    """sync_data() returns data immediately when the API responds 200 OK."""
    payload = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    mock_get.return_value = _make_ok_response(payload)

    # Import here so the module-level decorator picks up the patched requests
    from fixed_code import sync_data

    result = sync_data()

    assert result == payload
    assert mock_get.call_count == 1


@patch("requests.get")
def test_sync_data_retries_on_429_then_succeeds(mock_get):
    """sync_data() retries after a 429 and returns data on the next attempt."""
    payload = [{"id": 3, "name": "Carol"}]

    rate_limit_error = _make_http_error(429)

    # First call raises 429; second call succeeds
    mock_get.side_effect = [
        rate_limit_error,
        _make_ok_response(payload),
    ]

    from fixed_code import sync_data

    # Patch tenacity's wait so the test doesn't actually sleep
    with patch("tenacity.nap.time"):
        result = sync_data()

    assert result == payload
    assert mock_get.call_count == 2


@patch("requests.get")
def test_sync_data_retries_multiple_times_before_success(mock_get):
    """sync_data() retries several times on repeated 429s before succeeding."""
    payload = [{"id": 99}]

    rate_limit_error = _make_http_error(429)

    # Three 429s followed by a success
    mock_get.side_effect = [
        rate_limit_error,
        rate_limit_error,
        rate_limit_error,
        _make_ok_response(payload),
    ]

    from fixed_code import sync_data

    with patch("tenacity.nap.time"):
        result = sync_data()

    assert result == payload
    assert mock_get.call_count == 4


@patch("requests.get")
def test_sync_data_raises_after_max_attempts(mock_get):
    """sync_data() raises HTTPError after exhausting all retry attempts."""
    rate_limit_error = _make_http_error(429)

    # Always return 429 — should exhaust the 6 configured attempts
    mock_get.side_effect = rate_limit_error

    from fixed_code import sync_data
    from requests.exceptions import HTTPError

    with patch("tenacity.nap.time"):
        with pytest.raises(HTTPError):
            sync_data()

    assert mock_get.call_count == 6


@patch("requests.get")
def test_sync_data_does_not_retry_on_non_429_http_error(mock_get):
    """sync_data() does NOT retry on non-429 HTTP errors (e.g. 500)."""
    server_error = _make_http_error(500)
    mock_get.side_effect = server_error

    from fixed_code import sync_data
    from requests.exceptions import HTTPError

    with pytest.raises(HTTPError):
        sync_data()

    # Should fail immediately without retrying
    assert mock_get.call_count == 1


@patch("requests.get")
def test_sync_data_does_not_retry_on_404(mock_get):
    """sync_data() does NOT retry on 404 Not Found."""
    not_found_error = _make_http_error(404)
    mock_get.side_effect = not_found_error

    from fixed_code import sync_data
    from requests.exceptions import HTTPError

    with pytest.raises(HTTPError):
        sync_data()

    assert mock_get.call_count == 1
