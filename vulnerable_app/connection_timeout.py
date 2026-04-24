"""
Metrics Collector — Scrapes metrics from the monitoring endpoint.

This integration runs every minute to collect system metrics
from the internal monitoring API and forward them to the data lake.
"""

import requests

API_URL = "http://localhost:8429/api/slow"


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
