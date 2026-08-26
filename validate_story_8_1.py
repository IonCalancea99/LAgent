"""
Validation script for Story 8.1: System Tray Icon & Session Control Menu

Validates all acceptance criteria and architecture compliance.
Run with: python validate_story_8_1.py
"""

import sys
import tempfile
import importlib.util
from pathlib import Path

# Track validation results
checks = []


def check(name: str, condition: bool, details: str = ""):
    """Record a check result."""
    status = "✓" if condition else "✗"
    checks.append((name, condition, details))
    print(f"{status} {name}")
    if details and not condition:
        print(f"  → {details}")


def validate_imports():
    """Validate all required modules can be imported."""
    print("\n=== AC-1: Imports & Module Structure ===")
    
    try:
        from lagent.common.sessions_db import SessionsDB
        check("Import SessionsDB", True)
    except Exception as e:
        check("Import SessionsDB", False, str(e))
    
    try:
        from lagent.ui.tray import TrayIcon, Menu, MenuState, SessionStartItem
        check("Import TrayIcon and Menu", True)
    except Exception as e:
        check("Import TrayIcon and Menu", False, str(e))
    
    try:
        from lagent.ui.process_manager import ProcessManager, ProcessGroup
        check("Import ProcessManager", True)
    except Exception as e:
        check("Import ProcessManager", False, str(e))
    
    try:
        from lagent.ui.telemetry import TelemetryLogger
        check("Import TelemetryLogger", True)
    except Exception as e:
        check("Import TelemetryLogger", False, str(e))
    
    try:
        from lagent.ui import main
        check("Import UI main()", True)
    except Exception as e:
        check("Import UI main()", False, str(e))


def validate_menu_structure():
    """Validate Menu class structure."""
    print("\n=== AC-1: Menu Structure ===")
    
    from lagent.ui.tray import Menu, MenuState
    
    menu = Menu()
    
    check("Menu has start_session", hasattr(menu, 'start_session'))
    check("Menu has stop_session", hasattr(menu, 'stop_session'))
    check("Menu has recording_mode_toggle", hasattr(menu, 'recording_mode_toggle'))
    check("Menu has status_overlay_toggle", hasattr(menu, 'status_overlay_toggle'))
    check("Menu has exit", hasattr(menu, 'exit'))
    
    check("Start Session has modes", hasattr(menu.start_session, 'modes'))
    if hasattr(menu.start_session, 'modes'):
        modes = menu.start_session.modes
        check("Modes include Fishing", "Fishing" in modes)
        check("Modes include Combat", "Combat" in modes)
        check("Modes include Shadow", "Shadow" in modes)
    
    # Initial state
    state = menu.get_state()
    check("Initial: Start enabled", state.start_session_enabled is True)
    check("Initial: Stop disabled", state.stop_session_enabled is False)


def validate_menu_state_transitions():
    """Validate menu state transitions."""
    print("\n=== AC-3: Menu State Transitions ===")
    
    from lagent.ui.tray import Menu
    
    menu = Menu()
    
    # Starting transition
    menu.on_session_starting()
    state1 = menu.get_state()
    check("After starting: Start disabled", state1.start_session_enabled is False)
    check("After starting: Stop disabled (pre-register)", state1.stop_session_enabled is False)
    
    # Processes registered
    menu.on_processes_registered()
    state2 = menu.get_state()
    check("After register: Stop enabled", state2.stop_session_enabled is True)
    check("After register: Start still disabled", state2.start_session_enabled is False)
    
    # Stopped transition
    menu.on_session_stopped()
    state3 = menu.get_state()
    check("After stopped: Start enabled", state3.start_session_enabled is True)
    check("After stopped: Stop disabled", state3.stop_session_enabled is False)


def validate_tray_icon():
    """Validate TrayIcon class."""
    print("\n=== AC-1: Tray Icon ===")
    
    from lagent.ui.tray import TrayIcon
    
    with tempfile.TemporaryDirectory() as tmpdir:
        icon_path = Path(tmpdir) / "icon.png"
        icon_path.write_bytes(b"fake icon data")
        
        tray = TrayIcon(icon_path=str(icon_path))
        
        check("TrayIcon created", tray is not None)
        check("TrayIcon has menu", hasattr(tray, 'menu'))
        check("TrayIcon has setup_menu_callbacks", hasattr(tray, 'setup_menu_callbacks'))
        
        # Try lazy loading pystray (may fail if not installed)
        try:
            icon = tray.get_icon_instance()
            check("Pystray available", icon is not None)
        except Exception as e:
            check("Pystray available", False, f"pystray not installed or display unavailable: {e}")


def validate_process_manager():
    """Validate ProcessManager class."""
    print("\n=== AC-2: Process Manager ===")
    
    from lagent.ui.process_manager import ProcessManager, ProcessGroup
    from lagent.common.sessions_db import SessionsDB
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SessionsDB(str(db_path))
        
        pm = ProcessManager(sessions_db=db, startup_timeout=10.0, shutdown_timeout=5.0)
        
        check("ProcessManager created", pm is not None)
        check("Has generate_session_id", hasattr(pm, 'generate_session_id'))
        check("Has start_session", hasattr(pm, 'start_session'))
        check("Has stop_session", hasattr(pm, 'stop_session'))
        
        # Test session ID generation
        sid = pm.generate_session_id()
        check("Session ID generated", sid is not None and len(sid) > 0)
        
        # Test mode mapping
        try:
            config = pm.map_mode_to_profile("fishing")
            check("Fishing mode maps", config is not None)
            check("Fishing has profile", 'profile' in config)
            check("Fishing has processes", 'processes' in config)
        except Exception as e:
            check("Fishing mode maps", False, str(e))
        
        db.close()


def validate_database_schema():
    """Validate database schema changes."""
    print("\n=== AC-4: Database Schema ===")
    
    from lagent.common.sessions_db import SessionsDB
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SessionsDB(str(db_path))
        
        # Check ended_at column exists
        cursor = db.conn.cursor()
        cursor.execute("PRAGMA table_info(sessions)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        check("Sessions table has ended_at", 'ended_at' in columns)
        
        # Test log_session_start and log_session_end
        session_id = "test-session-123"
        try:
            db.log_session_start(session_id, profile="fishing", mode="fishing")
            check("log_session_start works", True)
        except Exception as e:
            check("log_session_start works", False, str(e))
        
        try:
            session = db.get_session(session_id)
            check("get_session works", session is not None)
            check("Session has ended_at field", 'ended_at' in session if session else False)
            check("ended_at is initially None", session['ended_at'] is None if session else False)
        except Exception as e:
            check("get_session works", False, str(e))
        
        # Test log_session_end
        try:
            db.log_session_end(session_id, outcome="clean")
            check("log_session_end works", True)
            
            # Verify ended_at is set
            session = db.get_session(session_id)
            check("ended_at is populated", session['ended_at'] is not None if session else False)
        except Exception as e:
            check("log_session_end works", False, str(e))
        
        db.close()


def validate_telemetry():
    """Validate TelemetryLogger."""
    print("\n=== AC-2/4: Telemetry Logging ===")
    
    from lagent.common.sessions_db import SessionsDB
    from lagent.ui.telemetry import TelemetryLogger
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SessionsDB(str(db_path))
        telemetry = TelemetryLogger(db)
        
        session_id = "test-session-456"
        db.log_session_start(session_id, profile="combat", mode="combat")
        
        # Test startup_failed event
        try:
            event_id = telemetry.log_startup_failed(
                session_id,
                failing_process="gpu_server",
                error_message="Connection timeout"
            )
            check("log_startup_failed works", event_id is not None)
            
            # Verify event in DB
            events = db.get_events_by_type(session_id, "startup_failed")
            check("Event persisted in DB", len(events) > 0)
            if events:
                event = events[0]
                check("Event has correct payload", event['payload']['process'] == 'gpu_server')
        except Exception as e:
            check("log_startup_failed works", False, str(e))
        
        # Test session_stopped event
        try:
            db.log_session_end(session_id, outcome="clean")
            telemetry.log_session_stopped(
                session_id,
                mode="combat",
                outcome="clean",
                child_results={"warlord": 0, "prophet": 0}
            )
            check("log_session_stopped works", True)
            
            events = db.get_events_by_type(session_id, "session_stopped")
            check("session_stopped event persisted", len(events) > 0)
        except Exception as e:
            check("log_session_stopped works", False, str(e))
        
        db.close()


def validate_no_agent_imports():
    """Validate that UI doesn't import agent/hsl/gpu_server."""
    print("\n=== AD-5: No Agent/HSL/GPU Imports ===")
    
    import sys
    
    # Clear modules
    to_remove = [m for m in sys.modules if 'lagent.ui' in m]
    for m in to_remove:
        del sys.modules[m]
    
    modules_before = set(sys.modules.keys())
    
    try:
        from lagent.ui.tray import TrayIcon
        from lagent.ui.process_manager import ProcessManager
        from lagent.ui.telemetry import TelemetryLogger
    except Exception:
        pass
    
    modules_after = set(sys.modules.keys())
    new_modules = modules_after - modules_before
    
    forbidden = [m for m in new_modules if any(x in m for x in [
        'lagent.agent.',
        'lagent.hsl.',
        'lagent.gpu_server.',
        'lagent.orchestrator.',
        'lagent.train.',
    ])]
    
    check("UI doesn't import agent modules", len(forbidden) == 0, 
          f"Forbidden imports: {forbidden}" if forbidden else "")


def validate_pyproject():
    """Validate pyproject.toml has pystray."""
    print("\n=== Dependencies ===")
    
    with open("pyproject.toml") as f:
        content = f.read()
    
    check("pystray in dependencies", "pystray" in content)


def print_summary():
    """Print validation summary."""
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    total = len(checks)
    passed = sum(1 for _, result, _ in checks if result)
    failed = total - passed
    
    print(f"Total checks: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\nFailed checks:")
        for name, result, details in checks:
            if not result:
                print(f"  ✗ {name}")
                if details:
                    print(f"    → {details}")
    
    print("=" * 60)
    
    return failed == 0


def main():
    """Run all validations."""
    print("Validating Story 8.1 Implementation\n")
    
    try:
        validate_imports()
        validate_menu_structure()
        validate_menu_state_transitions()
        validate_tray_icon()
        validate_process_manager()
        validate_database_schema()
        validate_telemetry()
        validate_no_agent_imports()
        validate_pyproject()
    except Exception as e:
        print(f"\nFATAL ERROR during validation: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    success = print_summary()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
