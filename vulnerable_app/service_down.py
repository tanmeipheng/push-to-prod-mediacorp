"""
Inventory Sync Worker — Pulls inventory from the Catalog Service.

This integration runs hourly to synchronize product inventory
from the internal catalog service into the warehouse system.
"""

import requests

API_URL = "http://localhost:8429/api/service"


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
