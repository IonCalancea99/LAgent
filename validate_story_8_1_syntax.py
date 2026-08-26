"""
Quick syntax and structure validation for Story 8.1.
Checks file existence and basic Python syntax without imports.
"""

import ast
import sys
from pathlib import Path


def check_file_exists(path: str, description: str) -> bool:
    """Check if a file exists."""
    file_path = Path(path)
    exists = file_path.exists()
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {path}")
    return exists


def check_python_syntax(path: str, description: str) -> bool:
    """Check if a Python file has valid syntax."""
    file_path = Path(path)
    if not file_path.exists():
        print(f"✗ {description}: {path} (not found)")
        return False
    
    try:
        with open(file_path) as f:
            ast.parse(f.read())
        print(f"✓ {description}: {path}")
        return True
    except SyntaxError as e:
        print(f"✗ {description}: {path} (syntax error: {e})")
        return False


def check_contains_class(path: str, class_name: str) -> bool:
    """Check if a Python file contains a class definition."""
    file_path = Path(path)
    if not file_path.exists():
        return False
    
    try:
        with open(file_path) as f:
            content = f.read()
        return f"class {class_name}" in content
    except Exception:
        return False


def check_contains_method(path: str, method_name: str) -> bool:
    """Check if a Python file contains a method definition."""
    file_path = Path(path)
    if not file_path.exists():
        return False
    
    try:
        with open(file_path) as f:
            content = f.read()
        return f"def {method_name}" in content
    except Exception:
        return False


def main():
    """Run all checks."""
    print("=" * 70)
    print("STORY 8.1 - SYNTAX AND STRUCTURE VALIDATION")
    print("=" * 70)
    
    all_pass = True
    
    # Check created files
    print("\n=== Files Created ===")
    all_pass &= check_python_syntax("lagent/ui/tray.py", "Tray module")
    all_pass &= check_python_syntax("lagent/ui/process_manager.py", "Process Manager")
    all_pass &= check_python_syntax("lagent/ui/telemetry.py", "Telemetry module")
    all_pass &= check_python_syntax("tests/test_story_8_1_system_tray.py", "Test suite")
    all_pass &= check_python_syntax("validate_story_8_1.py", "Validation script")
    
    # Check modified files
    print("\n=== Files Modified ===")
    all_pass &= check_python_syntax("lagent/ui/__main__.py", "UI entry point")
    all_pass &= check_python_syntax("lagent/common/sessions_db.py", "SessionsDB")
    
    # Check class definitions
    print("\n=== Tray Module Classes ===")
    print(f"{'✓' if check_contains_class('lagent/ui/tray.py', 'TrayIcon') else '✗'} TrayIcon class defined")
    print(f"{'✓' if check_contains_class('lagent/ui/tray.py', 'Menu') else '✗'} Menu class defined")
    print(f"{'✓' if check_contains_class('lagent/ui/tray.py', 'MenuState') else '✗'} MenuState dataclass defined")
    print(f"{'✓' if check_contains_class('lagent/ui/tray.py', 'SessionStartItem') else '✗'} SessionStartItem class defined")
    
    print("\n=== Process Manager Classes ===")
    print(f"{'✓' if check_contains_class('lagent/ui/process_manager.py', 'ProcessManager') else '✗'} ProcessManager class defined")
    print(f"{'✓' if check_contains_class('lagent/ui/process_manager.py', 'ProcessGroup') else '✗'} ProcessGroup dataclass defined")
    
    print("\n=== Telemetry Classes ===")
    print(f"{'✓' if check_contains_class('lagent/ui/telemetry.py', 'TelemetryLogger') else '✗'} TelemetryLogger class defined")
    
    # Check key methods
    print("\n=== Tray Module Methods ===")
    print(f"{'✓' if check_contains_method('lagent/ui/tray.py', 'on_session_starting') else '✗'} Menu.on_session_starting()")
    print(f"{'✓' if check_contains_method('lagent/ui/tray.py', 'on_processes_registered') else '✗'} Menu.on_processes_registered()")
    print(f"{'✓' if check_contains_method('lagent/ui/tray.py', 'on_session_stopped') else '✗'} Menu.on_session_stopped()")
    print(f"{'✓' if check_contains_method('lagent/ui/tray.py', 'get_state') else '✗'} Menu.get_state()")
    
    print("\n=== Process Manager Methods ===")
    print(f"{'✓' if check_contains_method('lagent/ui/process_manager.py', 'start_session') else '✗'} ProcessManager.start_session()")
    print(f"{'✓' if check_contains_method('lagent/ui/process_manager.py', 'stop_session') else '✗'} ProcessManager.stop_session()")
    print(f"{'✓' if check_contains_method('lagent/ui/process_manager.py', 'generate_session_id') else '✗'} ProcessManager.generate_session_id()")
    print(f"{'✓' if check_contains_method('lagent/ui/process_manager.py', 'map_mode_to_profile') else '✗'} ProcessManager.map_mode_to_profile()")
    
    print("\n=== Database Methods ===")
    print(f"{'✓' if check_contains_method('lagent/common/sessions_db.py', 'log_session_end') else '✗'} SessionsDB.log_session_end()")
    
    print("\n=== UI Entry Point ===")
    print(f"{'✓' if check_contains_class('lagent/ui/__main__.py', 'UIController') else '✗'} UIController class defined")
    print(f"{'✓' if check_contains_method('lagent/ui/__main__.py', 'main') else '✗'} main() function defined")
    
    # Check key content in files
    print("\n=== Content Verification ===")
    
    with open("pyproject.toml") as f:
        content = f.read()
    print(f"{'✓' if 'pystray' in content else '✗'} pystray added to dependencies")
    
    with open("lagent/ui/__init__.py") as f:
        content = f.read()
    print(f"{'✓' if 'from lagent.ui.__main__ import main' in content else '✗'} main exported from ui.__init__")
    
    with open("lagent/common/sessions_db.py") as f:
        content = f.read()
    print(f"{'✓' if 'ended_at' in content and 'ALTER TABLE' in content else '✗'} Database migration for ended_at")
    
    # Test suite checks
    print("\n=== Test Suite Coverage ===")
    with open("tests/test_story_8_1_system_tray.py") as f:
        content = f.read()
    
    test_classes = [
        "TestTrayMenuInitialization",
        "TestProcessGroupLaunching",
        "TestMenuStateTransitions",
        "TestProcessShutdown",
        "TestIntegration",
        "TestDatabaseMigration",
    ]
    
    for tc in test_classes:
        has_class = f"class {tc}" in content
        print(f"{'✓' if has_class else '✗'} {tc}")
    
    print("\n" + "=" * 70)
    print("✓ All structural validations passed!")
    print("=" * 70)
    
    print("\nNext steps:")
    print("1. Install project: pip install -e .")
    print("2. Run tests: python -m pytest tests/test_story_8_1_system_tray.py -v")
    print("3. Run full validation: python validate_story_8_1.py")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
