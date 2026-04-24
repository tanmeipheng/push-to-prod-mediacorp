"""
Tests for the exponential backoff resilience pattern applied to the
Report Generator's database write operation.
"""

import sqlite3
import pytest
from unittest.mock import patch, MagicMock, call
from tenacity import RetryError


# ---------------------------------------------------------------------------
# Helper: import the module under test
# ---------------------------------------------------------------------------
import importlib, sys, types

# We import the fixed module; adjust the module name to match your file name.
# Assuming the fixed file is saved as `report_generator.py`.
import report_generator as rg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWriteReportRetry:
    """Unit tests for _write_report with mocked sqlite3.connect."""

    def test_succeeds_on_first_attempt(self, tmp_path):
        """_write_report should succeed immediately when no lock error occurs."""
        db_path = str(tmp_path / "test.db")

        # Set up a real DB so the write can actually succeed
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT OR IGNORE INTO reports (id, value) VALUES (1, 'seed')")
        conn.commit()
        conn.close()

        # Should not raise
        rg._write_report(db_path)

        # Verify the value was updated
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT value FROM reports WHERE id = 1").fetchone()
        conn.close()
        assert row[0] == "report_data"

    def test_retries_on_operational_error_then_succeeds(self, tmp_path):
        """
        _write_report should retry when sqlite3.OperationalError is raised
        and eventually succeed on a later attempt.
        """
        db_path = str(tmp_path / "test.db")

        # Track call count
        call_count = 0
        real_connect = sqlite3.connect

        def mock_connect(path, timeout=5.0):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Simulate 'database is locked' for the first two attempts
                raise sqlite3.OperationalError("database is locked")
            # Third attempt: use a real connection to a fresh DB
            conn = real_connect(db_path, timeout=timeout)
            return conn

        # Prepare the real DB for the successful attempt
        setup_conn = real_connect(db_path)
        setup_conn.execute("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY, value TEXT)")
        setup_conn.execute("INSERT OR IGNORE INTO reports (id, value) VALUES (1, 'seed')")
        setup_conn.commit()
        setup_conn.close()

        with patch("report_generator.sqlite3.connect", side_effect=mock_connect):
            rg._write_report(db_path)

        assert call_count == 3, f"Expected 3 attempts, got {call_count}"

        # Verify the value was updated on the successful attempt
        verify_conn = real_connect(db_path)
        row = verify_conn.execute("SELECT value FROM reports WHERE id = 1").fetchone()
        verify_conn.close()
        assert row[0] == "report_data"

    def test_raises_after_max_attempts(self, tmp_path):
        """
        _write_report should raise sqlite3.OperationalError (via tenacity reraise)
        after exhausting all retry attempts.
        """
        db_path = str(tmp_path / "test.db")

        with patch(
            "report_generator.sqlite3.connect",
            side_effect=sqlite3.OperationalError("database is locked"),
        ):
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                rg._write_report(db_path)

    def test_does_not_retry_on_non_operational_error(self, tmp_path):
        """
        _write_report should NOT retry on errors that are not
        sqlite3.OperationalError (e.g., a generic RuntimeError).
        """
        db_path = str(tmp_path / "test.db")
        call_count = 0

        def mock_connect(path, timeout=5.0):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("unexpected error")

        with patch("report_generator.sqlite3.connect", side_effect=mock_connect):
            with pytest.raises(RuntimeError, match="unexpected error"):
                rg._write_report(db_path)

        # Should have been called exactly once — no retries
        assert call_count == 1

    def test_retry_count_matches_attempts(self, tmp_path):
        """
        Verify that the number of connect calls equals the number of
        retry attempts configured (stop_after_attempt=6).
        """
        db_path = str(tmp_path / "test.db")
        call_count = 0

        def mock_connect(path, timeout=5.0):
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("database is locked")

        with patch("report_generator.sqlite3.connect", side_effect=mock_connect):
            with pytest.raises(sqlite3.OperationalError):
                rg._write_report(db_path)

        # stop_after_attempt(6) means 6 total calls
        assert call_count == 6, f"Expected 6 attempts, got {call_count}"


class TestGenerateReport:
    """Integration-style tests for generate_report using mocked _write_report."""

    def test_generate_report_calls_write_report(self, tmp_path, monkeypatch):
        """generate_report should call _write_report and succeed."""
        # Redirect DB_PATH to a temp location
        monkeypatch.setattr(rg, "DB_PATH", str(tmp_path / "report.db"))

        write_calls = []

        def fake_write_report(db_path):
            write_calls.append(db_path)

        monkeypatch.setattr(rg, "_write_report", fake_write_report)

        rg.generate_report()

        assert len(write_calls) == 1

    def test_generate_report_propagates_error_after_retries(self, tmp_path, monkeypatch):
        """generate_report should propagate the error if _write_report exhausts retries."""
        monkeypatch.setattr(rg, "DB_PATH", str(tmp_path / "report.db"))

        def fake_write_report(db_path):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(rg, "_write_report", fake_write_report)

        with pytest.raises(sqlite3.OperationalError):
            rg.generate_report()
