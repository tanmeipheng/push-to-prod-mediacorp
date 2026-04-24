"""\nPayment Gateway Worker — Processes pending payment callbacks.\n\nThis integration polls the payment gateway every 5 minutes\nto reconcile transaction statuses with our billing system.\n"""

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
    after_log,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8429/api/gateway"


def is_gateway_timeout(exc: BaseException) -> bool:
    """Return True if the exception represents an HTTP 504 Gateway Timeout."""
    if isinstance(exc, requests.exceptions.HTTPError):
        return exc.response is not None and exc.response.status_code == 504
    # Also retry on connection-level timeouts and connection errors
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    return False


@retry(
    retry=retry_if_exception(is_gateway_timeout),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO),
    reraise=True,
)
def reconcile_payments():
    """Fetch pending payment statuses from the gateway."""
    print("[worker] Starting payment reconciliation from Gateway...")
    response = requests.get(API_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    print(f"[worker] Reconciled {len(data)} transactions successfully.")
    return data


if __name__ == "__main__":
    reconcile_payments()
