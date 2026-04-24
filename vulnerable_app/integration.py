"""
Data Sync Worker — Pulls records from the Partner Data API.

This integration runs every 15 minutes via cron to synchronize
customer records from the external partner API into our data lake.
"""

import requests
from requests.exceptions import HTTPError

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8429/api/data"


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Return True if the exception represents an HTTP 429 Too Many Requests."""
    return isinstance(exc, HTTPError) and exc.response is not None and exc.response.status_code == 429


@retry(
    retry=retry_if_exception(_is_rate_limit_error),
    wait=wait_random_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(7),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def sync_data():
    """Fetch latest records from the partner API and persist them."""
    print("[worker] Starting data sync from Partner API...")
    response = requests.get(API_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    print(f"[worker] Synced {len(data)} records successfully.")
    return data


if __name__ == "__main__":
    sync_data()
