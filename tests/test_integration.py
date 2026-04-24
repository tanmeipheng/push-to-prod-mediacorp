"""\nTests for the exponential backoff resilience pattern applied to reconcile_payments().\n"""

import pytest
import requests
from unittest.mock import patch, MagicMock, call
from tenacity import RetryError

# Import the module under test
import importlib, sys, types

# We import the fixed module directly
from fixed_code import reconcile_payments, is_gateway_timeout


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Build a requests.HTTPError with a fake response attached."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    error = requests.exceptions.HTTPError(response=mock_response)
    return error


# ---------------------------------------------------------------------------
# Unit tests for is_gateway_timeout predicate
# ---------------------------------------------------------------------------

class TestIsGatewayTimeout:
    def test_returns_true_for_504_http_error(self):
        assert is_gateway_timeout(make_http_error(504)) is True

    def test_returns_false_for_500_http_error(self):
        assert is_gateway_timeout(make_http_error(500)) is False

    def test_returns_false_for_404_http_error(self):
        assert is_gateway_timeout(make_http_error(404)) is False

    def test_returns_true_for_requests_timeout(self):
        assert is_gateway_timeout(requests.exceptions.Timeout()) is True

    def test_returns_true_for_connection_error(self):
        assert is_gateway_timeout(requests.exceptions.ConnectionError()) is True

    def test_returns_false_for_generic_exception(self):
        assert is_gateway_timeout(ValueError("oops")) is False

    def test_returns_false_for_http_error_without_response(self):
        error = requests.exceptions.HTTPError()
        error.response = None
        assert is_gateway_timeout(error) is False


# ---------------------------------------------------------------------------
# Integration-style tests for reconcile_payments with mocked requests.get
# ---------------------------------------------------------------------------

class TestReconcilePaymentsRetry:

    @patch("fixed_code.requests.get")
    def test_succeeds_on_first_attempt(self, mock_get):
        """No errors — should return data immediately without retrying."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "status": "settled"}]
        mock_get.return_value = mock_response

        result = reconcile_payments()

        assert result == [{"id": 1, "status": "settled"}]
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_retries_once_on_504_then_succeeds(self, mock_get):
        """First call raises 504, second call succeeds."""
        mock_response_ok = MagicMock()
        mock_response_ok.json.return_value = [{"id": 2, "status": "settled"}]

        mock_get.side_effect = [
            make_http_error(504),
            mock_response_ok,
        ]

        result = reconcile_payments()

        assert result == [{"id": 2, "status": "settled"}]
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_retries_multiple_times_on_504_then_succeeds(self, mock_get):
        """Three consecutive 504s, then success on the fourth attempt."""
        mock_response_ok = MagicMock()
        mock_response_ok.json.return_value = [{"id": 3, "status": "pending"}]

        mock_get.side_effect = [
            make_http_error(504),
            make_http_error(504),
            make_http_error(504),
            mock_response_ok,
        ]

        result = reconcile_payments()

        assert result == [{"id": 3, "status": "pending"}]
        assert mock_get.call_count == 4

    @patch("fixed_code.requests.get")
    def test_raises_after_max_attempts_exceeded(self, mock_get):
        """All 5 attempts fail with 504 — should re-raise the last HTTPError."""
        mock_get.side_effect = make_http_error(504)

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            reconcile_payments()

        assert exc_info.value.response.status_code == 504
        assert mock_get.call_count == 5  # stop_after_attempt(5)

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_non_504_http_error(self, mock_get):
        """A 500 Internal Server Error should NOT be retried."""
        mock_get.side_effect = make_http_error(500)

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            reconcile_payments()

        assert exc_info.value.response.status_code == 500
        # Should fail immediately without retrying
        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_does_not_retry_on_404(self, mock_get):
        """A 404 Not Found should NOT be retried."""
        mock_get.side_effect = make_http_error(404)

        with pytest.raises(requests.exceptions.HTTPError):
            reconcile_payments()

        assert mock_get.call_count == 1

    @patch("fixed_code.requests.get")
    def test_retries_on_connection_timeout(self, mock_get):
        """requests.exceptions.Timeout should also trigger retry."""
        mock_response_ok = MagicMock()
        mock_response_ok.json.return_value = [{"id": 5, "status": "settled"}]

        mock_get.side_effect = [
            requests.exceptions.Timeout("timed out"),
            mock_response_ok,
        ]

        result = reconcile_payments()

        assert result == [{"id": 5, "status": "settled"}]
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_retries_on_connection_error(self, mock_get):
        """requests.exceptions.ConnectionError should also trigger retry."""
        mock_response_ok = MagicMock()
        mock_response_ok.json.return_value = []

        mock_get.side_effect = [
            requests.exceptions.ConnectionError("connection refused"),
            mock_response_ok,
        ]

        result = reconcile_payments()

        assert result == []
        assert mock_get.call_count == 2

    @patch("fixed_code.requests.get")
    def test_returns_empty_list_when_no_transactions(self, mock_get):
        """Gateway returns an empty list — should handle gracefully."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = reconcile_payments()

        assert result == []
        assert mock_get.call_count == 1
