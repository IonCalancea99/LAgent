"""
Test Story 8.1: System Tray Icon & Session Control Menu

Tests follow red-green-refactor discipline:
- RED: Write tests that fail (verify functionality specs)
- GREEN: Implement minimal code to pass
- REFACTOR: Improve quality while keeping tests green

Tests cover:
- Tray process startup and menu creation
- Session lifecycle (start, running, stop)
- Menu state transitions
- Process group launching and termination
- Database persistence with ended_at
- Event logging for startup/shutdown/errors
"""

import pytest
import tempfile
import subprocess
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, call
from dataclasses import dataclass
from typing import Optional, List

# Import modules we're about to create
try:
    from lagent.ui.tray import TrayIcon, Menu, MenuState
    from lagent.ui.process_manager import ProcessManager, ProcessGroup
    from lagent.ui.telemetry import TelemetryLogger
    from lagent.common.sessions_db import SessionsDB
except ImportError as e:
    # Expected in RED phase
    pass


# ============================================================================
# AC-1: Tray process starts and exposes the menu
# ============================================================================

class TestTrayMenuInitialization:
    """AC-1: Tray icon initialization and menu structure."""

    def test_tray_icon_class_exists(self):
        """Test that TrayIcon class is defined."""
        from lagent.ui.tray import TrayIcon
        assert TrayIcon is not None

    def test_tray_icon_requires_icon_path(self):
        """Test that TrayIcon requires icon asset path."""
        from lagent.ui.tray import TrayIcon
        
        with tempfile.TemporaryDirectory() as tmpdir:
            icon_path = Path(tmpdir) / "icon.png"
            icon_path.write_bytes(b"fake icon data")
            
            # Should not raise
            tray = TrayIcon(icon_path=str(icon_path))
            assert tray is not None

    def test_tray_icon_creates_menu(self):
        """Test that TrayIcon creates a Menu instance."""
        from lagent.ui.tray import TrayIcon, Menu
        
        with tempfile.TemporaryDirectory() as tmpdir:
            icon_path = Path(tmpdir) / "icon.png"
            icon_path.write_bytes(b"fake icon data")
            
            tray = TrayIcon(icon_path=str(icon_path))
            assert hasattr(tray, 'menu')
            assert isinstance(tray.menu, Menu)

    def test_menu_has_required_items(self):
        """Test that Menu has all required items."""
        from lagent.ui.tray import Menu
        
        menu = Menu()
        
        # Verify menu structure
        assert hasattr(menu, 'start_session'), "Menu must have start_session"
        assert hasattr(menu, 'stop_session'), "Menu must have stop_session"
        assert hasattr(menu, 'recording_mode_toggle'), "Menu must have recording_mode_toggle"
        assert hasattr(menu, 'status_overlay_toggle'), "Menu must have status_overlay_toggle"
        assert hasattr(menu, 'exit'), "Menu must have exit"

    def test_menu_has_session_modes(self):
        """Test that Menu.start_session has Fishing, Combat, Shadow."""
        from lagent.ui.tray import Menu
        
        menu = Menu()
        
        # start_session should have modes
        assert hasattr(menu.start_session, 'modes')
        modes = menu.start_session.modes
        assert 'Fishing' in modes
        assert 'Combat' in modes
        assert 'Shadow' in modes

    def test_menu_initial_state(self):
        """Test menu initial state: Start enabled, Stop disabled."""
        from lagent.ui.tray import Menu, MenuState
        
        menu = Menu()
        state = menu.get_state()
        
        assert state.start_session_enabled is True
        assert state.stop_session_enabled is False
        assert state.recording_mode_enabled is False
        assert state.status_overlay_enabled is False

    def test_tray_icon_does_not_import_agent_modules(self):
        """Test that tray.py doesn't import agent/hsl/gpu_server."""
        import sys
        
        # Track imports before
        imports_before = set(sys.modules.keys())
        
        from lagent.ui.tray import TrayIcon
        
        # Track imports after
        imports_after = set(sys.modules.keys())
        new_imports = imports_after - imports_before
        
        # Verify no agent/hsl/gpu modules imported
        forbidden = [m for m in new_imports if any(x in m for x in ['lagent.agent', 'lagent.hsl', 'lagent.gpu_server'])]
        assert len(forbidden) == 0, f"TrayIcon should not import agent modules: {forbidden}"


# ============================================================================
# AC-2: Start launches the complete runtime
# ============================================================================

class TestProcessGroupLaunching:
    """AC-2: Session startup and process group management."""

    def test_process_manager_class_exists(self):
        """Test that ProcessManager class is defined."""
        from lagent.ui.process_manager import ProcessManager
        assert ProcessManager is not None

    def test_process_group_class_exists(self):
        """Test that ProcessGroup class is defined."""
        from lagent.ui.process_manager import ProcessGroup
        assert ProcessGroup is not None

    def test_process_manager_generates_session_id(self):
        """Test that ProcessManager can generate session IDs."""
        from lagent.ui.process_manager import ProcessManager
        from lagent.common.sessions_db import SessionsDB
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sessions.db"
            db = SessionsDB(str(db_path))
            
            pm = ProcessManager(sessions_db=db, startup_timeout=5.0, shutdown_timeout=5.0)
            session_id = pm.generate_session_id()
            
            assert session_id is not None
            assert isinstance(session_id, str)
            assert len(session_id) > 0
            
            db.close()

    def test_process_group_tracks_child_processes(self):
        """Test that ProcessGroup tracks subprocess handles."""
        from lagent.ui.process_manager import ProcessGroup
        
        group = ProcessGroup(session_id="test-session-123", mode="fishing", profile="fishing")
        
        assert group.session_id == "test-session-123"
        assert group.mode == "fishing"
        assert group.profile == "fishing"
        assert hasattr(group, 'processes')
        assert len(group.processes) == 0

    def test_session_startup_creates_session_row(self):
        """Test that session startup creates a row in sessions table."""
        from lagent.ui.process_manager import ProcessManager
        from lagent.common.sessions_db import SessionsDB
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sessions.db"
            db = SessionsDB(str(db_path))
            
            pm = ProcessManager(sessions_db=db, startup_timeout=5.0, shutdown_timeout=5.0)
            session_id = pm.generate_session_id()
            
            # Record session start
            db.log_session_start(session_id, profile="fishing", mode="fishing")
            
            # Verify session row exists
            session = db.get_session(session_id)
            assert session is not None
            assert session['session_id'] == session_id
            assert session['profile'] == "fishing"
            assert session['mode'] == "fishing"
            
            db.close()

    def test_startup_failure_logs_event(self):
        """Test that startup failure is logged with correct event structure."""
        from lagent.ui.telemetry import TelemetryLogger
        from lagent.common.sessions_db import SessionsDB
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sessions.db"
            db = SessionsDB(str(db_path))
            
            session_id = "test-session-123"
            db.log_session_start(session_id, profile="fishing", mode="fishing")
            
            # Log startup failure
            telemetry = TelemetryLogger(db)
            event_id = telemetry.log_startup_failed(session_id, "gpu_server", "Connection timeout")
            
            assert event_id is not None
            
            # Verify event in database
            events = db.get_events_by_type(session_id, "startup_failed")
            assert len(events) > 0
            
            event = events[0]
            assert event['type'] == 'startup_failed'
            assert event['payload']['process'] == 'gpu_server'
            assert event['payload']['error'] == 'Connection timeout'
            
            db.close()


# ============================================================================
# AC-3: Menu state prevents conflicting commands
# ============================================================================

class TestMenuStateTransitions:
    """AC-3: Menu state management during session lifecycle."""

    def test_menu_state_transitions_on_session_start(self):
        """Test that menu transitions when session starts."""
        from lagent.ui.tray import Menu
        
        menu = Menu()
        
        # Initial state
        assert menu.get_state().start_session_enabled is True
        assert menu.get_state().stop_session_enabled is False
        
        # Simulate session starting
        menu.on_session_starting()
        state = menu.get_state()
        
        assert state.start_session_enabled is False
        # Stop is disabled until processes are registered
        assert state.stop_session_enabled is False

    def test_menu_state_transitions_on_process_registered(self):
        """Test that Stop becomes enabled after process group is registered."""
        from lagent.ui.tray import Menu
        
        menu = Menu()
        menu.on_session_starting()
        
        # Before registration
        assert menu.get_state().stop_session_enabled is False
        
        # After registration
        menu.on_processes_registered()
        
        assert menu.get_state().stop_session_enabled is True
        assert menu.get_state().start_session_enabled is False

    def test_menu_state_transitions_on_session_stopped(self):
        """Test that menu transitions back when session stops."""
        from lagent.ui.tray import Menu
        
        menu = Menu()
        menu.on_session_starting()
        menu.on_processes_registered()
        
        # Session is running
        assert menu.get_state().start_session_enabled is False
        assert menu.get_state().stop_session_enabled is True
        
        # Stop session
        menu.on_session_stopped()
        state = menu.get_state()
        
        assert state.start_session_enabled is True
        assert state.stop_session_enabled is False


# ============================================================================
# AC-4: Stop performs clean process-group shutdown
# ============================================================================

class TestProcessShutdown:
    """AC-4: Process termination and shutdown semantics."""

    def test_process_group_shutdown_records_ended_at(self):
        """Test that session shutdown records ended_at timestamp."""
        from lagent.ui.process_manager import ProcessManager
        from lagent.common.sessions_db import SessionsDB
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sessions.db"
            db = SessionsDB(str(db_path))
            
            session_id = "test-session-456"
            db.log_session_start(session_id, profile="combat", mode="combat")
            
            # Record shutdown
            db.log_session_end(session_id, outcome="clean")
            
            # Verify ended_at is set
            session = db.get_session(session_id)
            assert session is not None
            assert 'ended_at' in session
            assert session['ended_at'] is not None
            
            db.close()

    def test_session_shutdown_logs_event(self):
        """Test that shutdown creates session_stopped event."""
        from lagent.ui.telemetry import TelemetryLogger
        from lagent.common.sessions_db import SessionsDB
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sessions.db"
            db = SessionsDB(str(db_path))
            
            session_id = "test-session-456"
            db.log_session_start(session_id, profile="combat", mode="combat")
            
            # Log shutdown
            telemetry = TelemetryLogger(db)
            telemetry.log_session_stopped(
                session_id,
                mode="combat",
                outcome="clean",
                child_results={"warlord": 0, "prophet": 0, "orchestrator": 0}
            )
            
            # Verify event
            events = db.get_events_by_type(session_id, "session_stopped")
            assert len(events) > 0
            
            event = events[0]
            assert event['type'] == 'session_stopped'
            assert event['payload']['outcome'] == 'clean'
            
            db.close()

    def test_database_has_ended_at_column_backward_compatible(self):
        """Test that ended_at column is added backward-compatibly."""
        from lagent.common.sessions_db import SessionsDB
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sessions.db"
            db = SessionsDB(str(db_path))
            
            # Verify ended_at column exists
            cursor = db.conn.cursor()
            cursor.execute("PRAGMA table_info(sessions)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert 'ended_at' in columns, "ended_at column must exist in sessions table"
            
            db.close()


# ============================================================================
# AC Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete AC flow."""

    def test_menu_and_process_manager_lifecycle(self):
        """Test complete menu + process manager lifecycle."""
        from lagent.ui.tray import Menu
        from lagent.ui.process_manager import ProcessManager
        from lagent.common.sessions_db import SessionsDB
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sessions.db"
            db = SessionsDB(str(db_path))
            
            menu = Menu()
            pm = ProcessManager(sessions_db=db, startup_timeout=5.0, shutdown_timeout=5.0)
            
            # Initial state
            assert menu.get_state().start_session_enabled is True
            
            # User clicks Start
            menu.on_session_starting()
            session_id = pm.generate_session_id()
            db.log_session_start(session_id, profile="fishing", mode="fishing")
            
            # Processes registered
            menu.on_processes_registered()
            assert menu.get_state().stop_session_enabled is True
            
            # User clicks Stop
            menu.on_session_stopped()
            db.log_session_end(session_id, outcome="clean")
            
            # Verify final state
            final_state = menu.get_state()
            assert final_state.start_session_enabled is True
            assert final_state.stop_session_enabled is False
            
            # Verify session in database
            session = db.get_session(session_id)
            assert session['ended_at'] is not None
            
            db.close()

    def test_ui_entry_point_exists(self):
        """Test that UI entry point can be imported."""
        from lagent.ui import main
        assert main is not None
        assert callable(main)

    def test_no_agent_imports_in_ui_package(self):
        """Test that ui package doesn't import agent/hsl/gpu_server."""
        import sys
        
        imports_before = set(sys.modules.keys())
        
        # Import entire ui package
        import lagent.ui
        
        imports_after = set(sys.modules.keys())
        new_imports = imports_after - imports_before
        
        # Check no runtime module imports
        forbidden = [m for m in new_imports if any(x in m for x in ['lagent.agent.', 'lagent.hsl.', 'lagent.gpu_server.', 'lagent.orchestrator.'])]
        assert len(forbidden) == 0, f"UI package should not import runtime modules: {forbidden}"


# ============================================================================
# Database Migration Tests
# ============================================================================

class TestDatabaseMigration:
    """Test database schema migration for ended_at column."""

    def test_ended_at_nullable_for_running_sessions(self):
        """Test that ended_at is NULL for running sessions."""
        from lagent.common.sessions_db import SessionsDB
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sessions.db"
            db = SessionsDB(str(db_path))
            
            session_id = "test-session-789"
            db.log_session_start(session_id, profile="shadow", mode="shadow")
            
            session = db.get_session(session_id)
            assert session['ended_at'] is None
            
            db.close()

    def test_log_session_end_method_exists(self):
        """Test that log_session_end method is defined."""
        from lagent.common.sessions_db import SessionsDB
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sessions.db"
            db = SessionsDB(str(db_path))
            
            assert hasattr(db, 'log_session_end')
            assert callable(db.log_session_end)
            
            db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
