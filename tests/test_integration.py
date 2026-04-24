"""
Tests for the exponential backoff resilience pattern applied to sync_data().

Verifies that:
- HTTP 429 responses trigger retries with exponential backoff.
- The function eventually succeeds after transient 429 errors.
- Non-429 HTTP errors are NOT retried (fail fast).
- A successful first response returns data immediately without retrying.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from requests.exceptions import HTTPError


def _make_http_error(status_code: int) -> HTTPError:
    """Helper to create an HTTPError with a given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = HTTPError(response=mock_response)
    return error


def _make_success_response(data: list) -> MagicMock:
    """Helper to create a successful mock response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = data
    return mock_response


def _make_429_response() -> MagicMock:
    """Helper to create a mock response that raises HTTP 429 on raise_for_status."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.raise_for_status.side_effect = _make_http_error(429)
    return mock_response


@patch("time.sleep", return_value=None)  # Prevent actual sleeping during tests
@patch("requests.get")
def test_sync_data_succeeds_on_first_attempt(mock_get, mock_sleep):
    """sync_data() returns data immediately when the API responds successfully."""
    from worker import sync_data

    expected_data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    mock_get.return_value = _make_success_response(expected_data)

    result = sync_data()

    assert result == expected_data
    assert mock_get.call_count == 1


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_retries_on_429_then_succeeds(mock_get, mock_sleep):
    """sync_data() retries after a 429 and succeeds on the next attempt."""
    from worker import sync_data

    expected_data = [{"id": 3, "name": "Charlie"}]
    mock_get.side_effect = [
        _make_429_response(),   # First call: 429 Too Many Requests
        _make_success_response(expected_data),  # Second call: success
    ]

    result = sync_data()

    assert result == expected_data
    assert mock_get.call_count == 2


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_retries_multiple_429s_then_succeeds(mock_get, mock_sleep):
    """sync_data() retries through multiple 429 responses before succeeding."""
    from worker import sync_data

    expected_data = [{"id": 4, "name": "Diana"}]
    mock_get.side_effect = [
        _make_429_response(),  # Attempt 1: 429
        _make_429_response(),  # Attempt 2: 429
        _make_429_response(),  # Attempt 3: 429
        _make_success_response(expected_data),  # Attempt 4: success
    ]

    result = sync_data()

    assert result == expected_data
    assert mock_get.call_count == 4


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_raises_after_max_retries(mock_get, mock_sleep):
    """sync_data() raises HTTPError after exhausting all retry attempts (6 total)."""
    from worker import sync_data
    from tenacity import RetryError

    # Always return 429 — exhaust all 6 attempts
    mock_get.side_effect = _make_429_response

    with pytest.raises(HTTPError):
        sync_data()

    assert mock_get.call_count == 6


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_does_not_retry_on_500(mock_get, mock_sleep):
    """sync_data() does NOT retry on HTTP 500 — only 429 triggers backoff."""
    from worker import sync_data

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = _make_http_error(500)
    mock_get.return_value = mock_response

    with pytest.raises(HTTPError):
        sync_data()

    # Should only be called once — no retries for 500
    assert mock_get.call_count == 1


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_does_not_retry_on_404(mock_get, mock_sleep):
    """sync_data() does NOT retry on HTTP 404 — only 429 triggers backoff."""
    from worker import sync_data

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = _make_http_error(404)
    mock_get.return_value = mock_response

    with pytest.raises(HTTPError):
        sync_data()

    assert mock_get.call_count == 1


@patch("time.sleep", return_value=None)
@patch("requests.get")
def test_sync_data_returns_correct_record_count(mock_get, mock_sleep):
    """sync_data() returns the full list of records from the API response."""
    from worker import sync_data

    records = [{"id": i} for i in range(50)]
    mock_get.return_value = _make_success_response(records)

    result = sync_data()

    assert len(result) == 50
    assert result == records
