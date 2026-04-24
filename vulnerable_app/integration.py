"""
Data Sync Worker — Pulls records from the Partner Data API.

This integration runs every 15 minutes via cron to synchronize
customer records from the external partner API into our data lake.
"""

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8429/api/data"


@retry(
    retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.HTTPError, requests.exceptions.Timeout)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
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
