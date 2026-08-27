"""Acceptance tests for Story 9.7: read-only quest status projection."""

from lagent.common.sessions_db import SessionsDB
from lagent.ui.telemetry import QuestStatus, TelemetryReader, format_quest_summary
from lagent.ui.tray import TrayIcon


def append_transition(db, session_id, *, sequence, state, index=0, reason=None):
    return db.append_event(
        session_id,
        "agent.quest",
        "quest_transition",
        {
            "quest_id": "marcela_supply_check",
            "quest_name": "Supply Check",
            "objective_id": "talk_marcela" if index == 0 else "confirm_supply",
            "objective_name": "Speak to Marcela" if index == 0 else "Confirm supply",
            "objective_index": index,
            "total_objectives": 2,
            "state": state,
            "event_sequence": sequence,
            "terminal_result": reason,
        },
    )


def test_active_quest_projects_name_objective_index_and_running_status(tmp_path):
    db = SessionsDB(str(tmp_path / "sessions.db"))
    db.log_session_start("session-9", "quest", "shadow")
    append_transition(db, "session-9", sequence=1, state="navigating")

    snapshot = TelemetryReader(db.path).read_quest("session-9")

    assert snapshot.quest_name == "Supply Check"
    assert snapshot.current_objective == "Speak to Marcela"
    assert snapshot.objective_index == 0
    assert snapshot.total_objectives == 2
    assert snapshot.status is QuestStatus.RUNNING
    assert format_quest_summary(snapshot) == "Supply Check · Speak to Marcela · 1/2 · Running"
    db.close()


def test_pause_completion_and_failure_are_operator_readable(tmp_path):
    db = SessionsDB(str(tmp_path / "sessions.db"))
    db.log_session_start("paused", "quest", "shadow")
    db.log_session_start("complete", "quest", "shadow")
    db.log_session_start("failed", "quest", "shadow")
    append_transition(db, "paused", sequence=1, state="paused")
    append_transition(db, "complete", sequence=1, state="complete", index=1, reason="completed")
    append_transition(db, "failed", sequence=1, state="safe_stop", reason="npc_not_found")
    reader = TelemetryReader(db.path)

    assert reader.read_quest("paused").status is QuestStatus.PAUSED
    completed = reader.read_quest("complete")
    assert completed.status is QuestStatus.COMPLETE and completed.objective_index == 1
    failed = reader.read_quest("failed")
    assert failed.status is QuestStatus.FAILED
    assert failed.failure_reason == "npc_not_found"
    assert format_quest_summary(failed).endswith("Failed · NPC not found")
    db.close()


def test_no_quest_and_new_session_clear_prior_projection(tmp_path):
    db = SessionsDB(str(tmp_path / "sessions.db"))
    db.log_session_start("quest-session", "quest", "shadow")
    db.log_session_start("combat-session", "combat", "combat")
    append_transition(db, "quest-session", sequence=1, state="navigating")
    reader = TelemetryReader(db.path)

    assert reader.read_quest("quest-session").status is QuestStatus.RUNNING
    cleared = reader.read_quest("combat-session")

    assert cleared.status is QuestStatus.IDLE
    assert cleared.quest_name is None
    assert format_quest_summary(cleared) == ""
    db.close()


def test_stale_and_duplicate_sequences_cannot_overwrite_current_state(tmp_path):
    db = SessionsDB(str(tmp_path / "sessions.db"))
    db.log_session_start("session-9", "quest", "shadow")
    append_transition(db, "session-9", sequence=2, state="navigating", index=1)
    append_transition(db, "session-9", sequence=1, state="safe_stop", reason="route_stuck")
    append_transition(db, "session-9", sequence=2, state="safe_stop", reason="retry_limit_reached")

    snapshot = TelemetryReader(db.path).read_quest("session-9")

    assert snapshot.status is QuestStatus.RUNNING
    assert snapshot.objective_index == 1
    assert snapshot.failure_reason is None
    db.close()


def test_tray_projects_compact_summary_without_owning_quest_state():
    tray = TrayIcon("unused.png")
    snapshot = TelemetryReader(":memory:").read_quest(None)
    assert tray.update_quest_status(snapshot) == "LAgent - Idle"

    active = snapshot.__class__(
        quest_name="Supply Check",
        current_objective="Speak to Marcela",
        objective_index=0,
        total_objectives=2,
        status=QuestStatus.RUNNING,
    )
    tooltip = tray.update_quest_status(active)

    assert tooltip == "LAgent - Idle | Supply Check · Speak to Marcela · 1/2 · Running"