"""
Tests for the retry-with-jitter resilience pattern applied to sync_data().

Simulates HTTP 429 Too Many Requests transient failures followed by a
successful response, verifying that the decorated function retries and
eventually returns the correct data.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock

# Import the module under test
import importlib, sys, types

# We import the fixed module directly
from fixed_code import sync_data, API_URL


def make_429_response():
    """Create a mock response object that represents an HTTP 429 error."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=mock_resp
    )
    return mock_resp


def make_200_response(data):
    """Create a mock response object that represents a successful HTTP 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = data
    return mock_resp


@patch("fixed_code.requests.get")
def test_sync_data_retries_on_429_then_succeeds(mock_get):
    """
    Verify that sync_data() retries after receiving HTTP 429 responses
    and eventually returns data when a successful response is received.
    """
    expected_data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    # First two calls raise 429, third call succeeds
    mock_get.side_effect = [
        make_429_response(),
        make_429_response(),
        make_200_response(expected_data),
    ]

    result = sync_data()

    assert result == expected_data
    assert mock_get.call_count == 3
    mock_get.assert_called_with(API_URL, timeout=10)


@patch("fixed_code.requests.get")
def test_sync_data_succeeds_on_first_attempt(mock_get):
    """
    Verify that sync_data() returns data immediately when no 429 is raised.
    """
    expected_data = [{"id": 42, "name": "Charlie"}]
    mock_get.return_value = make_200_response(expected_data)

    result = sync_data()

    assert result == expected_data
    assert mock_get.call_count == 1


@patch("fixed_code.requests.get")
def test_sync_data_raises_after_max_attempts(mock_get):
    """
    Verify that sync_data() raises HTTPError after exhausting all retry attempts
    when every call returns HTTP 429.
    """
    # Always return 429
    mock_get.return_value = make_429_response()

    with pytest.raises(requests.exceptions.HTTPError) as exc_info:
        sync_data()

    assert exc_info.value.response.status_code == 429
    # Should have tried 7 times (stop_after_attempt=7)
    assert mock_get.call_count == 7


@patch("fixed_code.requests.get")
def test_sync_data_does_not_retry_on_non_429_error(mock_get):
    """
    Verify that sync_data() does NOT retry on non-429 HTTP errors (e.g., 500).
    """
    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500
    http_error = requests.exceptions.HTTPError(response=mock_resp_500)
    mock_resp_500.raise_for_status.side_effect = http_error
    mock_get.return_value = mock_resp_500

    with pytest.raises(requests.exceptions.HTTPError):
        sync_data()

    # Should only be called once — no retry for 500
    assert mock_get.call_count == 1


@patch("fixed_code.requests.get")
def test_sync_data_one_429_then_success(mock_get):
    """
    Verify that a single 429 followed by success works correctly.
    """
    expected_data = [{"id": 7, "name": "Dave"}]
    mock_get.side_effect = [
        make_429_response(),
        make_200_response(expected_data),
    ]

    result = sync_data()

    assert result == expected_data
    assert mock_get.call_count == 2
