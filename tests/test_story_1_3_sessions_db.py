"""
Test Story 1.3: Session Database - WAL-mode SQLite Setup

Tests follow red-green-refactor discipline:
- RED: Write tests that fail (verify functionality specs)
- GREEN: Implement minimal code to pass
- REFACTOR: Improve quality while keeping tests green
"""

import pytest
import sqlite3
import tempfile
import json
import os
from pathlib import Path
from datetime import datetime, date
from uuid import uuid4

# Import the module we're about to create
# This will fail on first run (RED phase)
try:
    from lagent.common.sessions_db import SessionsDB, create_db_bootstrap
except ImportError:
    SessionsDB = None
    create_db_bootstrap = None


class TestDBBootstrapUtility:
    """RED: Tests for shared DB bootstrap utility."""

    def test_bootstrap_utility_exists(self):
        """Test that create_db_bootstrap function is defined."""
        assert create_db_bootstrap is not None, "create_db_bootstrap function must exist"

    def test_bootstrap_creates_db_at_path(self):
        """Test that bootstrap creates database at specified path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            # Bootstrap should create the DB
            db = create_db_bootstrap(str(db_path))
            assert db_path.exists(), "Database file should be created"
            db.close()

    def test_bootstrap_enables_wal_mode(self):
        """Test that bootstrap enables WAL journal mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = create_db_bootstrap(str(db_path))
            
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            
            assert mode.lower() == "wal", "WAL mode must be enabled"
            conn.close()

    def test_bootstrap_sets_write_safe_pragmas(self):
        """Test that bootstrap sets write-safe pragmas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = create_db_bootstrap(str(db_path))
            
            cursor = conn.cursor()
            # Check key write-safe pragmas
            cursor.execute("PRAGMA synchronous")
            synchronous = cursor.fetchone()[0]
            
            assert synchronous >= 1, "PRAGMA synchronous should be NORMAL or FULL"
            conn.close()

    def test_bootstrap_creates_sessions_table(self):
        """Test that bootstrap creates sessions table with correct schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = create_db_bootstrap(str(db_path))
            
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
            result = cursor.fetchone()
            
            assert result is not None, "sessions table must exist"
            
            # Verify columns
            cursor.execute("PRAGMA table_info(sessions)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert "session_id" in columns, "session_id column must exist"
            assert "started_at" in columns, "started_at column must exist"
            assert "profile" in columns, "profile column must exist"
            assert "mode" in columns, "mode column must exist"
            
            conn.close()

    def test_bootstrap_creates_events_table(self):
        """Test that bootstrap creates events table with correct schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = create_db_bootstrap(str(db_path))
            
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
            result = cursor.fetchone()
            
            assert result is not None, "events table must exist"
            
            # Verify columns
            cursor.execute("PRAGMA table_info(events)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert "id" in columns, "id column must exist"
            assert "session_id" in columns, "session_id column must exist"
            assert "ts" in columns, "ts column must exist"
            assert "source" in columns, "source column must exist"
            assert "type" in columns, "type column must exist"
            assert "payload_json" in columns, "payload_json column must exist"
            
            conn.close()

    def test_bootstrap_schema_idempotent(self):
        """Test that schema creation is idempotent (can run multiple times)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            # Create DB first time
            conn1 = create_db_bootstrap(str(db_path))
            cursor1 = conn1.cursor()
            cursor1.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count_1 = cursor1.fetchone()[0]
            conn1.close()
            
            # Create DB second time (idempotent)
            conn2 = create_db_bootstrap(str(db_path))
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count_2 = cursor2.fetchone()[0]
            conn2.close()
            
            assert table_count_1 == table_count_2, "Schema creation must be idempotent"


class TestSessionsDBClass:
    """RED: Tests for SessionsDB wrapper class."""

    def test_sessions_db_class_exists(self):
        """Test that SessionsDB class is defined."""
        assert SessionsDB is not None, "SessionsDB class must exist"

    def test_sessions_db_init(self):
        """Test that SessionsDB initializes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionsDB(str(db_path))
            
            assert db.path == str(db_path), "DB path should be stored"
            db.close()

    def test_sessions_db_log_session_start(self):
        """Test logging a session start event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionsDB(str(db_path))
            
            session_id = "test-session-001"
            profile = "prophet"
            mode = "active"
            
            db.log_session_start(session_id, profile, mode)
            
            # Verify in database
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, profile, mode FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            assert row is not None, "Session should be logged in database"
            assert row[0] == session_id, "session_id should match"
            assert row[1] == profile, "profile should match"
            assert row[2] == mode, "mode should match"
            
            conn.close()
            db.close()

    def test_sessions_db_append_event(self):
        """Test appending an event to database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionsDB(str(db_path))

            session_id = "test-session-001"
            db.log_session_start(session_id, "prophet", "active")
            source = "agent"
            event_type = "startup"
            payload = {"component": "warlord", "status": "initialized"}

            db.append_event(session_id, source, event_type, payload)

            # Verify in database
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, source, type, payload_json FROM events WHERE session_id = ?",
                         (session_id,))
            row = cursor.fetchone()

            assert row is not None, "Event should be appended to database"
            assert row[0] == session_id, "session_id should match"
            assert row[1] == source, "source should match"
            assert row[2] == event_type, "type should match"

            stored_payload = json.loads(row[3])
            assert stored_payload == payload, "payload should be JSON-serialized and match"

            conn.close()
            db.close()

    def test_append_event_with_datetime_payload(self):
        """Datetime and UUID payload values should serialize cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionsDB(str(db_path))
            db.log_session_start("session-datetime", "prophet", "active")

            payload = {
                "when": datetime(2024, 1, 2, 3, 4, 5),
                "day": date(2024, 1, 2),
                "request_id": uuid4(),
            }

            event_id = db.append_event("session-datetime", "agent", "startup", payload)
            row = db.conn.execute(
                "SELECT payload_json FROM events WHERE id = ?", (event_id,)
            ).fetchone()

            stored = json.loads(row[0])
            assert stored["when"] == payload["when"].isoformat()
            assert stored["day"] == payload["day"].isoformat()
            assert stored["request_id"] == str(payload["request_id"])

            db.close()

    def test_append_event_nonexistent_session(self):
        """Events for a session that was never started should fail with IntegrityError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionsDB(str(db_path))

            with pytest.raises(sqlite3.IntegrityError):
                db.append_event("missing-session", "agent", "startup", {"status": "bad"})

            db.close()

    def test_get_session(self):
        """Session metadata should be readable through the DB helper."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionsDB(str(db_path))
            db.log_session_start("session-read", "warlord", "autonomous")

            session = db.get_session("session-read")
            assert session["session_id"] == "session-read"
            assert session["profile"] == "warlord"
            assert session["mode"] == "autonomous"
            assert "started_at" in session

            db.close()

    def test_get_events_by_type(self):
        """Events should be queryable by session and event type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionsDB(str(db_path))
            db.log_session_start("session-events", "prophet", "active")

            db.append_event("session-events", "agent", "startup", {"step": 1})
            db.append_event("session-events", "agent", "startup", {"step": 2})
            db.append_event("session-events", "agent", "heartbeat", {"step": 3})

            starts = db.get_events_by_type("session-events", "startup", limit=10)
            assert len(starts) == 2
            assert all(event["type"] == "startup" for event in starts)
            assert [event["payload"]["step"] for event in starts] == [1, 2]

            db.close()


class TestConcurrency:
    """RED: Tests for concurrent access safety (AC2)."""

    def test_concurrent_writes_two_connections(self):
        """
        Test that two separate SQLite connections can write concurrently
        without "database is locked" errors (AC2).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            # Initialize DB
            init_conn = create_db_bootstrap(str(db_path))
            init_conn.close()
            
            # Open two separate connections (simulating separate processes)
            conn1 = sqlite3.connect(str(db_path), timeout=10)
            conn2 = sqlite3.connect(str(db_path), timeout=10)
            
            # Enable WAL mode if not already
            conn1.execute("PRAGMA journal_mode=WAL")
            conn2.execute("PRAGMA journal_mode=WAL")
            
            # Both connections append events
            session_id_1 = "session-1"
            session_id_2 = "session-2"
            
            try:
                # Write from connection 1
                conn1.execute(
                    "INSERT INTO events (session_id, ts, source, type, payload_json) VALUES (?, ?, ?, ?, ?)",
                    (session_id_1, datetime.now().isoformat(), "agent1", "event", json.dumps({"data": "conn1"}))
                )
                conn1.commit()
                
                # Write from connection 2
                conn2.execute(
                    "INSERT INTO events (session_id, ts, source, type, payload_json) VALUES (?, ?, ?, ?, ?)",
                    (session_id_2, datetime.now().isoformat(), "agent2", "event", json.dumps({"data": "conn2"}))
                )
                conn2.commit()
                
                # Verify both writes succeeded
                cursor1 = conn1.cursor()
                cursor1.execute("SELECT COUNT(*) FROM events")
                count = cursor1.fetchone()[0]
                
                assert count == 2, "Both events should be written successfully"
                
            finally:
                conn1.close()
                conn2.close()

    def test_no_database_locked_errors(self):
        """Test that concurrent writes don't produce 'database is locked' errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            # Initialize DB
            init_conn = create_db_bootstrap(str(db_path))
            init_conn.close()
            
            # Multiple rapid writes from two connections
            conn1 = sqlite3.connect(str(db_path), timeout=10)
            conn2 = sqlite3.connect(str(db_path), timeout=10)
            
            try:
                for i in range(5):
                    conn1.execute(
                        "INSERT INTO events (session_id, ts, source, type, payload_json) VALUES (?, ?, ?, ?, ?)",
                        (f"s1-{i}", datetime.now().isoformat(), "agent1", "type", json.dumps({"i": i}))
                    )
                    conn1.commit()
                    
                    conn2.execute(
                        "INSERT INTO events (session_id, ts, source, type, payload_json) VALUES (?, ?, ?, ?, ?)",
                        (f"s2-{i}", datetime.now().isoformat(), "agent2", "type", json.dumps({"i": i}))
                    )
                    conn2.commit()
                
                # If we reach here, no "database is locked" errors occurred
                assert True
                
            finally:
                conn1.close()
                conn2.close()


class TestAcceptanceCriteria:
    """RED: Tests mapping to story Acceptance Criteria."""

    def test_ac1_db_created_with_wal_mode_and_schema(self):
        """
        AC1: Given data/sessions.db does not exist, when any process writes first 
        event/session record, then sessions.db is created with WAL journal mode 
        and required tables.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sessions.db"
            assert not db_path.exists(), "DB should not exist initially"
            
            # First write (bootstrap)
            db = SessionsDB(str(db_path))
            db.log_session_start("session-001", "prophet", "active")
            db.close()
            
            # Verify DB exists
            assert db_path.exists(), "DB should be created after first write"
            
            # Verify WAL mode
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal", "WAL mode must be enabled"
            
            # Verify tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = {row[0] for row in cursor.fetchall()}
            assert "events" in tables, "events table must exist"
            assert "sessions" in tables, "sessions table must exist"
            
            conn.close()

    def test_ac2_concurrent_writes_no_locked_errors(self):
        """
        AC2: Given WL Agent and PP Agent each hold separate SQLite connections, 
        when both write concurrently, then no `database is locked` error occurs 
        and both events persist.
        """
        # This is tested by test_concurrent_writes_two_connections
        pass

    def test_ac3_session_start_logged_with_correct_fields(self):
        """
        AC3: Given session start is logged, when querying sessions table, 
        then row contains correct session_id, started_at, profile, mode.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionsDB(str(db_path))
            
            session_id = "ion-session-123"
            profile = "warlord"
            mode = "autonomous"
            
            db.log_session_start(session_id, profile, mode)
            db.close()
            
            # Verify by direct query
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id, profile, mode, started_at FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            
            assert row is not None, "Session must be logged"
            assert row[0] == session_id, f"session_id mismatch: {row[0]} != {session_id}"
            assert row[1] == profile, f"profile mismatch: {row[1]} != {profile}"
            assert row[2] == mode, f"mode mismatch: {row[2]} != {mode}"
            assert row[3] is not None, "started_at must be set"
            
            conn.close()
