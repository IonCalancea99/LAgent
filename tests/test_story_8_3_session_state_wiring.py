"""Focused Story 8.3 tests for deterministic session state and tray feedback."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from lagent.ui.notifications import NotificationAdapter
from lagent.ui.process_manager import ProcessManager, ProcessGroup
from lagent.ui.state import SessionState, UIEvent, UIState, reduce_state, format_tooltip


def test_reducer_projects_lifecycle_and_ignores_duplicate_or_stale_events():
    state = UIState()
    state = reduce_state(state, UIEvent("startup_started", "session-1", {"mode": "combat", "profile": "warlord+prophet"}))
    state = reduce_state(state, UIEvent("startup_complete", "session-1"))
    assert state.status is SessionState.RUNNING
    assert state.session_id == "session-1"

    duplicate = reduce_state(state, UIEvent("startup_complete", "session-1"))
    stale = reduce_state(duplicate, UIEvent("session_halt", "old-session", {"event_id": "old"}))
    assert duplicate == state
    assert stale == state


def test_reducer_session_rollover_cannot_be_overwritten_by_old_session():
    state = reduce_state(UIState(), UIEvent("startup_started", "session-1", {"mode": "fishing", "profile": "fishing"}))
    state = reduce_state(state, UIEvent("startup_started", "session-2", {"mode": "combat", "profile": "warlord+prophet"}))
    state = reduce_state(state, UIEvent("session_halt", "session-1", {"event_id": "old-halt"}))
    assert state.session_id == "session-2"
    assert state.status is SessionState.STARTING


def test_tooltip_formats_idle_active_recording_halted_and_unknown():
    started = datetime.now() - timedelta(seconds=3724)
    assert format_tooltip(UIState()) == "LAgent - Idle"
    active = UIState(status=SessionState.RUNNING, session_id="s", mode="combat", profile="warlord+prophet", started_at=started)
    assert format_tooltip(active, now=started + timedelta(seconds=3724)) == "Combat · warlord+prophet · 01:02:04"
    recording = UIState(status=SessionState.RECORDING, session_id="s", mode="combat", profile="warlord+prophet", started_at=started)
    assert format_tooltip(recording, now=started + timedelta(seconds=2)) == "Combat · warlord+prophet · 00:00:02 (Recording)"
    halted = UIState(status=SessionState.HALTED, session_id="s", mode="combat", profile="warlord+prophet", started_at=started)
    assert "Halted" in format_tooltip(halted, now=started)
    unknown = UIState(status=SessionState.UNKNOWN, session_id="s", last_tooltip="Combat · warlord+prophet · 00:01:00")
    assert format_tooltip(unknown) == "Stale - Combat · warlord+prophet · 00:01:00"


def test_recording_flag_is_added_only_to_agent_launches():
    manager = ProcessManager()
    agent = manager.build_process_command("warlord_agent", "s", "warlord", recording=True)
    gpu = manager.build_process_command("gpu_server", "s", "warlord", recording=True)
    assert "--record" in agent
    assert "--record" not in gpu


def test_halt_notifications_are_deduplicated_per_event():
    adapter = NotificationAdapter()
    adapter.notify_halted("session-1", "event-1")
    adapter.notify_halted("session-1", "event-1")
    assert adapter.sent == [("Session halted - check status overlay", "session-1")]


def test_recording_restart_rolls_back_without_overlapping_agents():
    manager = ProcessManager()
    old = ProcessGroup("session-1", "combat", "warlord+prophet")
    old.add_process("warlord_agent", Mock(poll=Mock(return_value=None)))
    old.add_process("prophet_agent", Mock(poll=Mock(return_value=None)))
    manager.current_session = old
    manager._launch_child_processes = Mock(side_effect=RuntimeError("replacement failed"))
    with pytest.raises(RuntimeError):
        manager.restart_recording(True)
    assert manager.current_session is None
    assert old.processes["warlord_agent"].terminate.called
    assert old.processes["prophet_agent"].terminate.called
