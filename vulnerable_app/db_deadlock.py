"""
Report Generator — Aggregates daily stats into a summary table.

This worker runs nightly to compute report aggregates. It performs
concurrent reads and writes to a shared SQLite database, which can
trigger "database is locked" errors under contention.
"""

import sqlite3
import threading
import tempfile
import os
import time

# Use a unique temp file per run to avoid stale lock issues
_tmpfile = tempfile.NamedTemporaryFile(suffix=".db", prefix="tfah_reports_", delete=False)
DB_PATH = _tmpfile.name
_tmpfile.close()


def _setup_db():
    """Create the demo table."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR IGNORE INTO reports (id, value) VALUES (1, 'seed')")
    conn.commit()
    conn.close()


def _concurrent_writer():
    """Holds an exclusive write lock to cause contention."""
    conn = sqlite3.connect(DB_PATH, timeout=0.05)
    conn.execute("BEGIN EXCLUSIVE")
    conn.execute("UPDATE reports SET value = 'writer_lock' WHERE id = 1")
    time.sleep(3)  # Hold the lock long enough
    conn.commit()
    conn.close()


def generate_report():
    """Attempt to write to the database while another thread holds the lock."""
    print("[worker] Starting nightly report generation...")
    _setup_db()

    # Start a competing writer that grabs an exclusive lock
    writer = threading.Thread(target=_concurrent_writer, daemon=True)
    writer.start()

    time.sleep(0.5)  # Ensure the writer has the lock

    # Now try to write — this will fail with "database is locked"
    conn = sqlite3.connect(DB_PATH, timeout=0.05)
    try:
        conn.execute("UPDATE reports SET value = 'report_data' WHERE id = 1")
        conn.commit()
    finally:
        conn.close()
        # Cleanup temp file
        try:
            os.unlink(DB_PATH)
        except OSError:
            pass

    print("[worker] Report generated successfully.")


if __name__ == "__main__":
    generate_report()
