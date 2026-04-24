"""
Inventory Sync Worker — Pulls inventory from the Catalog Service.

This integration runs hourly to synchronize product inventory
from the internal catalog service into the warehouse system.
"""

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8429/api/service"


class ServiceUnavailableError(Exception):
    """Raised when the Catalog Service returns HTTP 503."""
    pass


def _is_503_error(exc: BaseException) -> bool:
    """Return True if the exception is an HTTP 503 Service Unavailable error."""
    return (
        isinstance(exc, requests.exceptions.HTTPError)
        and exc.response is not None
        and exc.response.status_code == 503
    )


@retry(
    retry=retry_if_exception_type(requests.exceptions.HTTPError),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO),
    reraise=True,
)
def sync_inventory():
    """Fetch latest inventory from the catalog service."""
    print("[worker] Starting inventory sync from Catalog Service...")
    response = requests.get(API_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    print(f"[worker] Synced {len(data)} inventory items successfully.")
    return data


if __name__ == "__main__":
    sync_inventory()
