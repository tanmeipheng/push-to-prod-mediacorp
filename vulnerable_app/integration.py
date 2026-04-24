"""
Data Sync Worker — Pulls records from the Partner Data API.

This integration runs every 15 minutes via cron to synchronize
customer records from the external partner API into our data lake.
"""

import requests

API_URL = "http://localhost:8429/api/data"


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
