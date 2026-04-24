"""
Tests for the Inventory Sync Worker resilience logic.

Verifies that sync_inventory retries on HTTP 503 errors using
exponential backoff and eventually succeeds when the service recovers.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock, call

# Import the module under test
import importlib, sys, types

# We import the fixed module directly
from fixed_code import sync_inventory


def make_503_response():
    """Create a mock response that simulates HTTP 503."""
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=mock_resp
    )
    return mock_resp


def make_200_response(data):
    """Create a mock response that simulates HTTP 200 with JSON data."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = data
    return mock_resp


@patch("fixed_code.requests.get")
def test_sync_inventory_succeeds_after_retries(mock_get):
    """
    sync_inventory should retry on 503 and succeed when the service recovers.
    Simulates two 503 failures followed by a successful 200 response.
    """
    inventory_data = [{"id": 1, "name": "Widget", "qty": 100}]

    mock_get.side_effect = [
        make_503_response(),
        make_503_response(),
        make_200_response(inventory_data),
    ]

    result = sync_inventory()

    assert result == inventory_data
    assert mock_get.call_count == 3


@patch("fixed_code.requests.get")
def test_sync_inventory_succeeds_on_first_try(mock_get):
    """
    sync_inventory should return data immediately when no errors occur.
    """
    inventory_data = [{"id": 2, "name": "Gadget", "qty": 50}]
    mock_get.return_value = make_200_response(inventory_data)

    result = sync_inventory()

    assert result == inventory_data
    assert mock_get.call_count == 1


@patch("fixed_code.requests.get")
def test_sync_inventory_raises_after_max_attempts(mock_get):
    """
    sync_inventory should raise HTTPError after exhausting all retry attempts.
    """
    mock_get.return_value = make_503_response()

    with pytest.raises(requests.exceptions.HTTPError):
        sync_inventory()

    # Should have tried exactly 5 times (stop_after_attempt=5)
    assert mock_get.call_count == 5


@patch("fixed_code.requests.get")
def test_sync_inventory_single_503_then_success(mock_get):
    """
    sync_inventory should handle a single 503 and succeed on the next attempt.
    """
    inventory_data = [{"id": 3, "name": "Doohickey", "qty": 200}]

    mock_get.side_effect = [
        make_503_response(),
        make_200_response(inventory_data),
    ]

    result = sync_inventory()

    assert result == inventory_data
    assert mock_get.call_count == 2


@patch("fixed_code.requests.get")
def test_sync_inventory_returns_correct_data_structure(mock_get):
    """
    sync_inventory should correctly return the full JSON payload from the service.
    """
    inventory_data = [
        {"id": 10, "name": "Alpha", "qty": 10},
        {"id": 11, "name": "Beta", "qty": 20},
        {"id": 12, "name": "Gamma", "qty": 30},
    ]
    mock_get.return_value = make_200_response(inventory_data)

    result = sync_inventory()

    assert len(result) == 3
    assert result[0]["name"] == "Alpha"
    assert result[2]["qty"] == 30
