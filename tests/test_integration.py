"""
Tests for the retry-with-jitter resilience pattern applied to sync_data().

Verifies that:
- A single HTTP 429 response causes a retry and eventual success.
- Multiple consecutive 429 responses are all retried until success.
- Non-429 HTTP errors (e.g. 500) are NOT retried and propagate immediately.
- Exceeding the maximum retry attempts re-raises the last exception.
"""

import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import HTTPError


def _make_http_error(status_code: int) -> HTTPError:
    """Helper: build an HTTPError with a fake response attached."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = HTTPError(f"HTTP {status_code}", response=mock_response)
    return error


def _make_ok_response(data: list) -> MagicMock:
    """Helper: build a successful requests.Response mock."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = data
    return mock_response


# ---------------------------------------------------------------------------
# Patch tenacity's wait so tests run instantly (no real sleeping).
# ---------------------------------------------------------------------------

@patch("worker.sync_data.retry.sleep", return_value=None)  # silence tenacity sleep
@patch("requests.get")
def test_retries_once_on_429_then_succeeds(mock_get, _mock_sleep):
    """One 429 followed by a 200 — function should succeed after one retry."""
    import worker  # noqa: import inside test to pick up patched module

    records = [{"id": 1}, {"id": 2}]
    mock_get.side_effect = [
        _make_http_error(429),   # first call → 429
        _make_ok_response(records),  # second call → 200
    ]

    result = worker.sync_data()

    assert result == records
    assert mock_get.call_count == 2


@patch("requests.get")
def test_retries_multiple_429s_then_succeeds(mock_get):
    """Three 429 responses followed by a 200 — all retries should be attempted."""
    import worker  # noqa

    # Patch wait to avoid sleeping during tests
    import tenacity
    original_wait = worker.sync_data.retry.wait
    worker.sync_data.retry.wait = tenacity.wait_none()

    records = [{"id": 42}]
    mock_get.side_effect = [
        _make_http_error(429),
        _make_http_error(429),
        _make_http_error(429),
        _make_ok_response(records),
    ]

    try:
        result = worker.sync_data()
    finally:
        worker.sync_data.retry.wait = original_wait

    assert result == records
    assert mock_get.call_count == 4


@patch("requests.get")
def test_non_429_error_not_retried(mock_get):
    """A 500 Internal Server Error must NOT trigger a retry."""
    import worker  # noqa

    import tenacity
    original_wait = worker.sync_data.retry.wait
    worker.sync_data.retry.wait = tenacity.wait_none()

    mock_get.side_effect = _make_http_error(500)

    try:
        with pytest.raises(HTTPError) as exc_info:
            worker.sync_data()
    finally:
        worker.sync_data.retry.wait = original_wait

    assert exc_info.value.response.status_code == 500
    # Should have been called exactly once — no retries for 500
    assert mock_get.call_count == 1


@patch("requests.get")
def test_exceeds_max_attempts_raises(mock_get):
    """If every attempt returns 429 and max retries are exhausted, re-raise."""
    import worker  # noqa

    import tenacity
    original_wait = worker.sync_data.retry.wait
    worker.sync_data.retry.wait = tenacity.wait_none()

    # Always return 429 — more than the 7-attempt limit
    mock_get.side_effect = _make_http_error(429)

    try:
        with pytest.raises(HTTPError) as exc_info:
            worker.sync_data()
    finally:
        worker.sync_data.retry.wait = original_wait

    assert exc_info.value.response.status_code == 429
    # tenacity stops after 7 attempts
    assert mock_get.call_count == 7


@patch("requests.get")
def test_success_on_first_attempt(mock_get):
    """No errors — function should succeed on the very first call."""
    import worker  # noqa

    records = [{"id": 10}, {"id": 20}, {"id": 30}]
    mock_get.return_value = _make_ok_response(records)

    result = worker.sync_data()

    assert result == records
    assert mock_get.call_count == 1
