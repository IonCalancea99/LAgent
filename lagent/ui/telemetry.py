"""
Telemetry: Event and metric logging for LAgent UI.

Story 8.1: System Tray Icon & Session Control Menu

Implements:
- Telemetry event logging for UI lifecycle
- Startup/shutdown events
- Error and diagnostic events
- Integration with SessionsDB
"""

import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class TelemetryLogger:
    """
    Logs telemetry events for UI lifecycle.
    
    Wraps SessionsDB to provide high-level telemetry methods.
    """
    
    def __init__(self, sessions_db: Any):
        """
        Initialize telemetry logger.
        
        Args:
            sessions_db: SessionsDB instance for recording events
        """
        self.db = sessions_db
    
    def log_startup_started(self, session_id: str, mode: str, profile: str) -> int:
        """
        Log when session startup begins.
        
        Args:
            session_id: Session ID
            mode: Session mode (fishing, combat, shadow)
            profile: Agent profile
        
        Returns:
            Event ID
        """
        return self.db.append_event(
            session_id,
            source="ui",
            type="startup_started",
            payload={
                "session_id": session_id,
                "mode": mode,
                "profile": profile,
            }
        )
    
    def log_process_launched(
        self,
        session_id: str,
        process_name: str,
        pid: int,
        args: List[str]
    ) -> int:
        """
        Log when a child process is launched.
        
        Args:
            session_id: Session ID
            process_name: Name of process (gpu_server, agent, etc.)
            pid: Process ID
            args: Command-line arguments
        
        Returns:
            Event ID
        """
        return self.db.append_event(
            session_id,
            source="ui",
            type="process_launched",
            payload={
                "process_name": process_name,
                "pid": pid,
                "args": args,
            }
        )
    
    def log_startup_failed(
        self,
        session_id: str,
        failing_process: str,
        error_message: str
    ) -> int:
        """
        Log startup failure for a process.
        
        Args:
            session_id: Session ID
            failing_process: Name of process that failed
            error_message: Error details
        
        Returns:
            Event ID
        """
        return self.db.append_event(
            session_id,
            source="ui",
            type="startup_failed",
            payload={
                "process": failing_process,
                "error": error_message,
            }
        )
    
    def log_startup_complete(self, session_id: str) -> int:
        """
        Log when startup completes successfully.
        
        Args:
            session_id: Session ID
        
        Returns:
            Event ID
        """
        return self.db.append_event(
            session_id,
            source="ui",
            type="startup_complete",
            payload={
                "session_id": session_id,
            }
        )
    
    def log_session_stopped(
        self,
        session_id: str,
        mode: str,
        outcome: str,
        child_results: Optional[Dict[str, int]] = None
    ) -> int:
        """
        Log when session stops.
        
        Args:
            session_id: Session ID
            mode: Session mode
            outcome: "clean" or "forced"
            child_results: Exit codes of child processes
        
        Returns:
            Event ID
        """
        return self.db.append_event(
            session_id,
            source="ui",
            type="session_stopped",
            payload={
                "session_id": session_id,
                "mode": mode,
                "outcome": outcome,
                "child_results": child_results or {},
            }
        )
    
    def log_ui_error(
        self,
        session_id: Optional[str],
        error_type: str,
        error_message: str,
        stacktrace: Optional[str] = None
    ) -> int:
        """
        Log an error in the UI.
        
        Args:
            session_id: Session ID (may be None if error before session)
            error_type: Type of error
            error_message: Error message
            stacktrace: Optional stack trace
        
        Returns:
            Event ID (or None if session_id is None and db requires it)
        """
        if session_id is None:
            logger.error(f"UI Error (no session): {error_type}: {error_message}")
            return None
        
        return self.db.append_event(
            session_id,
            source="ui",
            type="error",
            payload={
                "error_type": error_type,
                "error_message": error_message,
                "stacktrace": stacktrace,
            }
        )
    
    def log_menu_action(
        self,
        session_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Log a menu action.
        
        Args:
            session_id: Session ID
            action: Action name (start_fishing, stop_session, etc.)
            details: Optional action details
        
        Returns:
            Event ID
        """
        return self.db.append_event(
            session_id,
            source="ui",
            type="menu_action",
            payload={
                "action": action,
                "details": details or {},
            }
        )
