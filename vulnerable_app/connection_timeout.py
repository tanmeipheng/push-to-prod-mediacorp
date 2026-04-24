"""
Metrics Collector — Scrapes metrics from the monitoring endpoint.

This integration runs every minute to collect system metrics
from the internal monitoring API and forward them to the data lake.
"""

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8429/api/slow"


@retry(
    retry=retry_if_exception_type(
        (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError)
    ),
    wait=wait_random_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def collect_metrics():
    """Scrape metrics from the monitoring endpoint."""
    print("[worker] Collecting metrics from Monitoring API...")
    response = requests.get(API_URL, timeout=3)
    response.raise_for_status()
    data = response.json()
    print(f"[worker] Collected {len(data)} metric points successfully.")
    return data


if __name__ == "__main__":
    collect_metrics()
