"""
Payment Gateway Worker — Processes pending payment callbacks.

This integration polls the payment gateway every 5 minutes
to reconcile transaction statuses with our billing system.
"""

import requests

API_URL = "http://localhost:8429/api/gateway"


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
