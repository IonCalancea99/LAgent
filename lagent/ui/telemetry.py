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
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def clamp_percentage(value: Any) -> Optional[float]:
    """Return a finite percentage in the display range, or unknown."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return max(0.0, min(100.0, number))


def format_elapsed(seconds: Optional[float]) -> str:
    """Format elapsed session time deterministically as HH:MM:SS."""
    if seconds is None or not math.isfinite(seconds) or seconds < 0:
        return "--:--:--"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}"


@dataclass
class AgentSnapshot:
    agent: str
    state: str = "Stopped"
    hp_percent: Optional[float] = None
    mp_percent: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    stale: bool = False
    error: Optional[str] = None
    event_timestamp: Optional[datetime] = None

    @property
    def elapsed(self) -> str:
        return format_elapsed(self.elapsed_seconds)


class QuestStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class QuestSnapshot:
    quest_name: Optional[str] = None
    current_objective: Optional[str] = None
    objective_index: Optional[int] = None
    total_objectives: Optional[int] = None
    status: QuestStatus = QuestStatus.IDLE
    failure_reason: Optional[str] = None
    event_sequence: int = -1


def format_quest_summary(snapshot: QuestSnapshot) -> str:
    """Format a compact operator-facing quest status string."""

    if snapshot.status is QuestStatus.IDLE or not snapshot.quest_name:
        return ""
    objective = snapshot.current_objective or "Objective"
    if snapshot.objective_index is not None and snapshot.total_objectives:
        progress = f"{snapshot.objective_index + 1}/{snapshot.total_objectives}"
    else:
        progress = "--"
    status = snapshot.status.value.capitalize()
    summary = f"{snapshot.quest_name} · {objective} · {progress} · {status}"
    if snapshot.status is QuestStatus.FAILED and snapshot.failure_reason:
        reason = snapshot.failure_reason.replace("_", " ").capitalize().replace("Npc", "NPC")
        summary = f"{summary} · {reason}"
    return summary


class TelemetryReader:
    """Read-only, short-lived SQLite reader for overlay state snapshots."""

    SOURCES = {"WL": "agent.warlord", "PP": "agent.prophet"}

    def __init__(self, db_path: str, stale_after: float = 2.0, clock=None):
        self.db_path = db_path
        self.stale_after = stale_after
        self.clock = clock or datetime.now
        self._snapshots: Dict[str, AgentSnapshot] = {}
        self._session_id: Optional[str] = None

    def read(self, session_id: Optional[str] = None, now: Optional[datetime] = None) -> Dict[str, AgentSnapshot]:
        current = now or self.clock()
        snapshots = {name: AgentSnapshot(name) for name in self.SOURCES}
        if not session_id:
            self._session_id = None
            self._snapshots = snapshots
            return snapshots
        if session_id != self._session_id:
            self._snapshots = {}
        try:
            with sqlite3.connect(self.db_path, timeout=0.25) as connection:
                session = connection.execute(
                    "SELECT started_at FROM sessions WHERE session_id = ?", (session_id,)
                ).fetchone()
                if session is None:
                    return snapshots
                elapsed = self._elapsed(self._parse_timestamp(session[0]), current)
                for name, source in self.SOURCES.items():
                    row = connection.execute(
                        """SELECT ts, payload_json FROM events
                           WHERE session_id = ? AND source = ?
                           AND type IN ('state', 'state_transition', 'heartbeat', 'tick')
                           ORDER BY id DESC LIMIT 1""",
                        (session_id, source),
                    ).fetchone()
                    snapshots[name] = self._snapshot_from_event(
                        name, row, self._snapshots.get(name), elapsed, current
                    )
        except (sqlite3.Error, OSError) as exc:
            logger.warning("Overlay telemetry read failed: %s", exc)
            snapshots = {name: self._snapshots.get(name, AgentSnapshot(name)) for name in self.SOURCES}
        self._snapshots = snapshots
        self._session_id = session_id
        return snapshots

    read_snapshot = read

    def read_quest(self, session_id: Optional[str]) -> QuestSnapshot:
        """Project ordered quest events for one session without mutating runtime state."""

        snapshot = QuestSnapshot()
        if not session_id:
            return snapshot
        try:
            with sqlite3.connect(self.db_path, timeout=0.25) as connection:
                rows = connection.execute(
                    """SELECT id, type, payload_json FROM events
                       WHERE session_id = ? AND source = 'agent.quest'
                       AND type IN ('quest_transition', 'quest_checkpoint', 'quest_failure', 'quest_recovery')
                       ORDER BY id ASC""",
                    (session_id,),
                ).fetchall()
        except (sqlite3.Error, OSError) as exc:
            logger.warning("Quest telemetry read failed: %s", exc)
            return snapshot

        for event_id, event_type, payload_json in rows:
            try:
                payload = json.loads(payload_json)
                if not isinstance(payload, dict):
                    continue
            except (TypeError, json.JSONDecodeError):
                continue
            sequence = payload.get("event_sequence", event_id)
            if not isinstance(sequence, int) or sequence <= snapshot.event_sequence:
                continue
            snapshot.event_sequence = sequence
            snapshot.quest_name = payload.get("quest_name", snapshot.quest_name)
            snapshot.current_objective = payload.get("objective_name", snapshot.current_objective)
            snapshot.objective_index = payload.get("objective_index", snapshot.objective_index)
            snapshot.total_objectives = payload.get("total_objectives", snapshot.total_objectives)

            if event_type == "quest_transition":
                state = str(payload.get("state", "")).casefold()
                snapshot.status = {
                    "paused": QuestStatus.PAUSED,
                    "complete": QuestStatus.COMPLETE,
                    "safe_stop": QuestStatus.FAILED,
                }.get(state, QuestStatus.RUNNING)
                snapshot.failure_reason = payload.get("terminal_result") if snapshot.status is QuestStatus.FAILED else None
            elif event_type == "quest_failure":
                snapshot.status = QuestStatus.FAILED
                snapshot.failure_reason = payload.get("reason")
            elif event_type == "quest_recovery":
                recovery_state = payload.get("state")
                snapshot.status = {
                    "safe_stop": QuestStatus.FAILED,
                    "complete": QuestStatus.COMPLETE,
                }.get(recovery_state, QuestStatus.RUNNING)
                snapshot.failure_reason = payload.get("reason") if snapshot.status is QuestStatus.FAILED else None
            elif event_type == "quest_checkpoint":
                snapshot.status = QuestStatus.RUNNING
        return snapshot

    def latest_event_time(self, session_id: Optional[str]) -> Optional[datetime]:
        """Return the latest runtime heartbeat/state timestamp for a session."""
        if not session_id:
            return None
        try:
            with sqlite3.connect(self.db_path, timeout=0.25) as connection:
                row = connection.execute(
                    """SELECT ts FROM events
                       WHERE session_id = ?
                       AND source IN ('agent.warlord', 'agent.prophet', 'orchestrator')
                       ORDER BY id DESC LIMIT 1""",
                    (session_id,),
                ).fetchone()
        except (sqlite3.Error, OSError) as exc:
            logger.warning("Telemetry freshness read failed: %s", exc)
            return None
        return self._parse_timestamp(row[0]) if row else None

    def _snapshot_from_event(self, name, row, previous, elapsed, now):
        if row is None:
            retained = previous or AgentSnapshot(name)
            retained.elapsed_seconds, retained.stale, retained.error = elapsed, True, "No telemetry"
            return retained
        timestamp = self._parse_timestamp(row[0])
        try:
            payload = json.loads(row[1])
            if not isinstance(payload, dict):
                raise ValueError("payload is not an object")
            state = payload.get("fsm_state", payload.get("state", payload.get("to_state")))
            if not isinstance(state, str) or not state.strip():
                raise ValueError("missing FSM state")
            hp = clamp_percentage(payload.get("hp_percent"))
            mp = clamp_percentage(payload.get("mp_percent"))
            if hp is None and mp is None and ("hp_percent" in payload or "mp_percent" in payload):
                raise ValueError("invalid health or mana")
            age = self._elapsed(timestamp, now)
            stale = age is None or age > self.stale_after
            return AgentSnapshot(name, state.strip(), hp, mp, elapsed, stale,
                                 "Stale telemetry" if stale else None, timestamp)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            retained = previous or AgentSnapshot(name)
            retained.elapsed_seconds, retained.stale, retained.error = elapsed, True, f"Invalid telemetry: {exc}"
            return retained

    @staticmethod
    def _parse_timestamp(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _elapsed(started, now):
        if started is None:
            return None
        if started.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=started.tzinfo)
        if started.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        return max(0.0, (now - started).total_seconds())


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

    def log_recording_mode_changed(self, session_id: str, enabled: bool) -> int:
        return self.db.append_event(session_id, "ui", "recording_mode_changed", {"enabled": enabled})

    def log_session_halted(self, session_id: str, reason: str, event_id: Optional[str] = None) -> int:
        return self.db.append_event(session_id, "ui", "session_halted", {
            "reason": reason, "event_id": event_id or "session_halted",
        })
