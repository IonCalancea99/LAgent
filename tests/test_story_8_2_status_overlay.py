"""Focused Story 8.2 tests for overlay telemetry and deterministic formatting."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lagent.common.sessions_db import SessionsDB
from lagent.ui.telemetry import TelemetryReader, clamp_percentage, format_elapsed


def make_database():
    directory = tempfile.TemporaryDirectory()
    database = SessionsDB(str(Path(directory.name) / "sessions.db"))
    return directory, database


def test_formatting_and_clamping():
    assert format_elapsed(3661.9) == "01:01:01"
    assert format_elapsed(None) == "--:--:--"
    assert clamp_percentage(125) == 100
    assert clamp_percentage(-5) == 0
    assert clamp_percentage("invalid") is None


def test_no_session_is_stopped_and_unknown():
    directory, database = make_database()
    try:
        rows = TelemetryReader(database.path).read()
        assert set(rows) == {"WL", "PP"}
        assert all(row.state == "Stopped" and row.hp_percent is None and row.mp_percent is None for row in rows.values())
    finally:
        database.close()
        directory.cleanup()


def test_latest_state_is_sanitized_and_missing_agent_is_stale():
    directory, database = make_database()
    try:
        database.log_session_start("session-1", "fishing", "fishing")
        database.append_event("session-1", "agent.warlord", "state", {
            "state": "PULLING", "hp_percent": 125, "mp_percent": -2,
        })
        now = datetime.now()
        rows = TelemetryReader(database.path).read("session-1", now)
        assert rows["WL"].state == "PULLING"
        assert rows["WL"].hp_percent == 100 and rows["WL"].mp_percent == 0
        assert rows["PP"].state == "Stopped" and rows["PP"].stale
    finally:
        database.close()
        directory.cleanup()


def test_malformed_event_retains_last_valid_snapshot_and_rollover_discards_it():
    directory, database = make_database()
    try:
        database.log_session_start("session-1", "fishing", "fishing")
        database.append_event("session-1", "agent.warlord", "state", {
            "fsm_state": "WAITING", "hp_percent": 80, "mp_percent": 30,
        })
        reader = TelemetryReader(database.path)
        valid = reader.read("session-1", datetime.now())["WL"]
        database.conn.execute(
            "INSERT INTO events (session_id, ts, source, type, payload_json) VALUES (?, ?, ?, ?, ?)",
            ("session-1", datetime.now().isoformat(), "agent.warlord", "state", "not-json"),
        )
        database.conn.commit()
        retained = reader.read("session-1", datetime.now())["WL"]
        assert retained.state == valid.state and retained.hp_percent == valid.hp_percent and retained.stale

        database.log_session_start("session-2", "combat", "combat")
        rolled = reader.read("session-2", datetime.now())["WL"]
        assert rolled.state == "Stopped" and rolled.hp_percent is None
    finally:
        database.close()
        directory.cleanup()


def test_event_age_marks_row_stale():
    directory, database = make_database()
    try:
        database.log_session_start("session-1", "fishing", "fishing")
        old = (datetime.now() - timedelta(seconds=3)).isoformat()
        database.conn.execute(
            "INSERT INTO events (session_id, ts, source, type, payload_json) VALUES (?, ?, ?, ?, ?)",
            ("session-1", old, "agent.prophet", "state", '{"state":"BUFFING"}'),
        )
        database.conn.commit()
        row = TelemetryReader(database.path).read("session-1", datetime.now())["PP"]
        assert row.state == "BUFFING" and row.stale
    finally:
        database.close()
        directory.cleanup()


def test_overlay_creates_two_visible_rows_offscreen():
    pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication
    from lagent.ui.overlay import StatusOverlay

    application = QApplication.instance() or QApplication([])
    overlay = StatusOverlay(":memory:")
    assert set(overlay.rows) == {"WL", "PP"}
    assert all(row.isVisible() is False for row in overlay.rows.values())
    overlay.show_overlay()
    application.processEvents()
    assert overlay.isVisible()
    overlay.close()