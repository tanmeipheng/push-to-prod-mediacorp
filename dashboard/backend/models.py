"""
SQLite models for TFAH Dashboard — incident storage and pipeline run tracking.
"""

import sqlite3
import os
import json
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "tfah_dashboard.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL DEFAULT 'running',  -- running | completed | skipped | error
            crash_log TEXT,
            source_code TEXT,
            source_file_path TEXT DEFAULT 'vulnerable_app/integration.py',

            -- classification
            fault_type TEXT,
            http_status INTEGER,
            action TEXT,
            confidence REAL,
            summary TEXT,

            -- codegen
            fixed_code TEXT,
            test_code TEXT,
            changes_summary TEXT,
            incident_report TEXT,

            -- PR
            branch_name TEXT,
            pr_url TEXT,

            -- notification
            notified INTEGER DEFAULT 0,

            -- errors
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS pipeline_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            node TEXT NOT NULL,
            event_type TEXT NOT NULL,  -- start | done | error | skip
            data TEXT,  -- JSON payload
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );
    """)
    conn.commit()
    conn.close()


def create_incident(crash_log: str, source_code: str, source_file_path: str = "vulnerable_app/integration.py") -> int:
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO incidents (crash_log, source_code, source_file_path) VALUES (?, ?, ?)",
        (crash_log, source_code, source_file_path),
    )
    incident_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return incident_id


def update_incident(incident_id: int, **fields):
    conn = get_db()
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [incident_id]
    conn.execute(f"UPDATE incidents SET {sets} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_incident(incident_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_incidents(limit: int = 50, offset: int = 0, status: str | None = None, fault_type: str | None = None) -> list[dict]:
    conn = get_db()
    query = "SELECT * FROM incidents"
    params = []
    conditions = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if fault_type:
        conditions.append("fault_type = ?")
        params.append(fault_type)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_incident_stats() -> dict:
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    fixed = conn.execute("SELECT COUNT(*) FROM incidents WHERE status = 'completed'").fetchone()[0]
    skipped = conn.execute("SELECT COUNT(*) FROM incidents WHERE status = 'skipped'").fetchone()[0]
    errored = conn.execute("SELECT COUNT(*) FROM incidents WHERE status = 'error'").fetchone()[0]
    running = conn.execute("SELECT COUNT(*) FROM incidents WHERE status = 'running'").fetchone()[0]
    prs = conn.execute("SELECT COUNT(*) FROM incidents WHERE pr_url IS NOT NULL AND pr_url != ''").fetchone()[0]
    conn.close()
    return {
        "total": total,
        "fixed": fixed,
        "skipped": skipped,
        "errored": errored,
        "running": running,
        "prs_opened": prs,
    }


def add_pipeline_event(incident_id: int, node: str, event_type: str, data: dict | None = None):
    conn = get_db()
    conn.execute(
        "INSERT INTO pipeline_events (incident_id, node, event_type, data) VALUES (?, ?, ?, ?)",
        (incident_id, node, event_type, json.dumps(data) if data else None),
    )
    conn.commit()
    conn.close()


def get_pipeline_events(incident_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM pipeline_events WHERE incident_id = ? ORDER BY id ASC",
        (incident_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_timeline(days: int = 7) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        """SELECT date(created_at) as day, COUNT(*) as count, status
           FROM incidents
           WHERE created_at >= datetime('now', ?)
           GROUP BY day, status
           ORDER BY day ASC""",
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
