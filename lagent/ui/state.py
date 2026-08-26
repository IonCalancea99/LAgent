"""Deterministic session state model used by the tray and overlay."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
import time
from typing import Any, Dict, Optional

from lagent.ui.telemetry import format_elapsed


class SessionState(Enum):
    IDLE = "Idle"
    STARTING = "Starting"
    RUNNING = "Running"
    RECORDING = "Recording"
    STOPPING = "Stopping"
    HALTED = "Halted"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class UIEvent:
    type: str
    session_id: Optional[str] = None
    payload: Dict[str, Any] = None

    def __post_init__(self):
        if self.payload is None:
            object.__setattr__(self, "payload", {})


@dataclass(frozen=True)
class UIState:
    status: SessionState = SessionState.IDLE
    session_id: Optional[str] = None
    mode: Optional[str] = None
    profile: Optional[str] = None
    started_at: Optional[datetime] = None
    started_monotonic: Optional[float] = None
    recording: bool = False
    telemetry_stale: bool = False
    last_tooltip: Optional[str] = None
    halt_event_id: Optional[str] = None


def reduce_state(state: UIState, event: UIEvent) -> UIState:
    """Apply one lifecycle/telemetry event; events from old sessions are ignored."""
    payload = event.payload if isinstance(event.payload, dict) else {}
    starts_new = event.type in {"startup_started", "session_started"}
    if starts_new:
        if event.session_id is None or not isinstance(event.payload, dict):
            return state
        mode = payload.get("mode")
        profile = payload.get("profile")
        if mode is not None and not isinstance(mode, str):
            return state
        if profile is not None and not isinstance(profile, str):
            return state
        event_started = _timestamp(payload.get("started_at"))
        if (event_started is not None and state.started_at is not None
                and event_started < state.started_at
                and state.status not in {SessionState.IDLE, SessionState.HALTED, SessionState.UNKNOWN}):
            return state
        return replace(
            state,
            status=SessionState.STARTING,
            session_id=event.session_id,
            mode=mode,
            profile=profile,
            started_at=event_started or datetime.now(),
            started_monotonic=time.monotonic(),
            recording=bool(payload.get("recording", False)),
            telemetry_stale=False,
            last_tooltip=None,
            halt_event_id=None,
        )

    if event.session_id is None or state.session_id is None or event.session_id != state.session_id:
        return state
    if event.type in {"startup_complete", "processes_registered", "recording_ready"}:
        return replace(state, status=SessionState.RECORDING if state.recording else SessionState.RUNNING, telemetry_stale=False)
    if event.type in {"recording_started", "recording_restart_ready"}:
        return replace(state, status=SessionState.RECORDING, recording=True, telemetry_stale=False)
    if event.type in {"recording_stopped", "recording_restart_failed"}:
        return replace(state, status=SessionState.RUNNING if event.type == "recording_stopped" else SessionState.HALTED,
                       recording=False, telemetry_stale=False)
    if event.type in {"stop_requested", "stopping"}:
        return replace(state, status=SessionState.STOPPING)
    if event.type in {"session_stopped", "stopped"}:
        return replace(state, status=SessionState.IDLE, session_id=None, mode=None, profile=None,
                       started_at=None, started_monotonic=None, recording=False, telemetry_stale=False)
    if event.type in {"session_halt", "child_exited", "startup_failed"}:
        return replace(state, status=SessionState.HALTED, halt_event_id=payload.get("event_id", event.type), telemetry_stale=False)
    if event.type in {"telemetry_stale", "refresh_timeout"}:
        if state.status in {SessionState.IDLE, SessionState.HALTED}:
            return replace(state, telemetry_stale=True)
        return replace(state, status=SessionState.UNKNOWN, telemetry_stale=True,
                       last_tooltip=format_tooltip(state))
    if event.type in {"telemetry_fresh", "heartbeat"} and state.status == SessionState.UNKNOWN:
        return replace(state, status=SessionState.RECORDING if state.recording else SessionState.RUNNING, telemetry_stale=False)
    return state


def format_tooltip(state: UIState, now: Optional[datetime] = None) -> str:
    if state.status == SessionState.IDLE or state.session_id is None:
        return "LAgent - Idle"
    if state.status == SessionState.UNKNOWN:
        return f"Stale - {state.last_tooltip or 'LAgent - Unknown'}"
    elapsed = "--:--:--"
    if state.started_monotonic is not None and now is None:
        elapsed = format_elapsed(max(0.0, time.monotonic() - state.started_monotonic))
    elif state.started_at is not None:
        current = now or datetime.now()
        elapsed = format_elapsed(max(0.0, (current - state.started_at).total_seconds()))
    mode = (state.mode or state.status.value).title()
    profile = state.profile or "unknown"
    suffix = " (Recording)" if state.status == SessionState.RECORDING else ""
    prefix = "Halted - " if state.status == SessionState.HALTED else ""
    return f"{prefix}{mode} · {profile} · {elapsed}{suffix}"


def _timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None
