#!/usr/bin/env python3
"""
Manual validation of sessions_db implementation for story 1.3.
Tests RED -> GREEN requirements without pytest.
"""

import sys
import sqlite3
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Import directly from file to avoid pydantic dependency in __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "sessions_db",
    "/Users/VCALAIO/Documents/OwnApps/LAgent/lagent/common/sessions_db.py"
)
sessions_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sessions_db)

SessionsDB = sessions_db.SessionsDB
create_db_bootstrap = sessions_db.create_db_bootstrap


def test_bootstrap_creates_db():
    """Test: bootstrap creates database at path"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        assert not db_path.exists(), "DB should not exist initially"
        
        db = create_db_bootstrap(str(db_path))
        assert db_path.exists(), "✓ Database file created"
        db.close()
    return True


def test_bootstrap_enables_wal():
    """Test: bootstrap enables WAL mode"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = create_db_bootstrap(str(db_path))
        
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        
        assert mode.lower() == "wal", f"Expected WAL, got {mode}"
        print(f"✓ WAL mode enabled: {mode}")
        conn.close()
    return True


def test_bootstrap_creates_tables():
    """Test: bootstrap creates sessions and events tables"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = create_db_bootstrap(str(db_path))
        
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cursor.fetchall()}
        
        assert "events" in tables, "events table not found"
        assert "sessions" in tables, "sessions table not found"
        print(f"✓ Tables created: {sorted(tables)}")
        conn.close()
    return True


def test_bootstrap_idempotent():
    """Test: schema creation is idempotent"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        conn1 = create_db_bootstrap(str(db_path))
        cursor1 = conn1.cursor()
        cursor1.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        count1 = cursor1.fetchone()[0]
        conn1.close()
        
        conn2 = create_db_bootstrap(str(db_path))
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        count2 = cursor2.fetchone()[0]
        conn2.close()
        
        assert count1 == count2, f"Table count changed: {count1} vs {count2}"
        print(f"✓ Idempotent schema creation (tables: {count1})")
    return True


def test_sessions_db_log_start():
    """Test: SessionsDB.log_session_start works"""
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
        
        assert row is not None, "Session not found"
        assert row == (session_id, profile, mode), f"Session data mismatch: {row}"
        print(f"✓ Session logged: {session_id} ({profile}/{mode})")
        
        conn.close()
        db.close()
    return True


def test_sessions_db_append_event():
    """Test: SessionsDB.append_event works"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SessionsDB(str(db_path))
        
        session_id = "test-session-001"
        db.log_session_start(session_id, "prophet", "active")
        source = "agent"
        event_type = "startup"
        payload = {"component": "warlord", "status": "initialized"}
        
        event_id = db.append_event(session_id, source, event_type, payload)
        
        # Verify in database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, source, type, payload_json FROM events WHERE id = ?",
            (event_id,)
        )
        row = cursor.fetchone()
        
        assert row is not None, "Event not found"
        assert row[0] == session_id, f"session_id mismatch: {row[0]}"
        assert row[1] == source, f"source mismatch: {row[1]}"
        assert row[2] == event_type, f"type mismatch: {row[2]}"
        
        stored_payload = json.loads(row[3])
        assert stored_payload == payload, f"payload mismatch: {stored_payload}"
        print(f"✓ Event logged: id={event_id}, type={event_type}")
        
        conn.close()
        db.close()
    return True


def test_concurrent_writes():
    """Test: AC2 - Concurrent writes from two connections"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        # Initialize
        init_conn = create_db_bootstrap(str(db_path))
        init_conn.close()
        
        # Two separate connections
        conn1 = sqlite3.connect(str(db_path), timeout=10)
        conn2 = sqlite3.connect(str(db_path), timeout=10)
        
        try:
            # Write from conn1
            conn1.execute(
                "INSERT INTO events (session_id, ts, source, type, payload_json) VALUES (?, ?, ?, ?, ?)",
                ("session-1", datetime.now().isoformat(), "agent1", "event", json.dumps({"data": "conn1"}))
            )
            conn1.commit()
            
            # Write from conn2
            conn2.execute(
                "INSERT INTO events (session_id, ts, source, type, payload_json) VALUES (?, ?, ?, ?, ?)",
                ("session-2", datetime.now().isoformat(), "agent2", "event", json.dumps({"data": "conn2"}))
            )
            conn2.commit()
            
            # Verify both writes succeeded
            cursor1 = conn1.cursor()
            cursor1.execute("SELECT COUNT(*) FROM events")
            count = cursor1.fetchone()[0]
            
            assert count == 2, f"Expected 2 events, got {count}"
            print(f"✓ Concurrent writes successful (2 events from separate connections)")
            
        finally:
            conn1.close()
            conn2.close()
    
    return True


def test_ac1_auto_creation():
    """Test: AC1 - DB auto-created on first write with WAL mode and schema"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sessions.db"
        assert not db_path.exists(), "DB should not exist initially"
        
        # First write
        db = SessionsDB(str(db_path))
        db.log_session_start("session-001", "prophet", "active")
        db.close()
        
        # Verify DB exists with WAL mode
        assert db_path.exists(), "DB not created"
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal", f"WAL not enabled: {mode}"
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cursor.fetchall()}
        assert "events" in tables and "sessions" in tables, f"Missing tables: {tables}"
        
        print(f"✓ AC1: DB auto-created with WAL mode and schema")
        conn.close()
    
    return True


def test_ac3_session_fields():
    """Test: AC3 - Session start logged with correct fields"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SessionsDB(str(db_path))
        
        session_id = "ion-session-123"
        profile = "warlord"
        mode = "autonomous"
        
        db.log_session_start(session_id, profile, mode)
        db.close()
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, profile, mode, started_at FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        
        assert row is not None, "Session not found"
        assert row[0] == session_id, f"session_id mismatch"
        assert row[1] == profile, f"profile mismatch"
        assert row[2] == mode, f"mode mismatch"
        assert row[3] is not None, f"started_at not set"
        
        print(f"✓ AC3: Session fields correct (session_id, started_at, profile, mode)")
        conn.close()
    
    return True


def main():
    """Run all validation tests."""
    tests = [
        ("Bootstrap creates DB", test_bootstrap_creates_db),
        ("Bootstrap enables WAL", test_bootstrap_enables_wal),
        ("Bootstrap creates tables", test_bootstrap_creates_tables),
        ("Bootstrap idempotent", test_bootstrap_idempotent),
        ("SessionsDB.log_session_start", test_sessions_db_log_start),
        ("SessionsDB.append_event", test_sessions_db_append_event),
        ("Concurrent writes (AC2)", test_concurrent_writes),
        ("AC1: Auto-creation with WAL", test_ac1_auto_creation),
        ("AC3: Session fields", test_ac3_session_fields),
    ]
    
    print("=" * 70)
    print("TASK 1: Implement shared DB bootstrap utility")
    print("=" * 70)
    print()
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print()
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
