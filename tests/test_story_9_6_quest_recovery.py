"""Acceptance tests for Story 9.6: verified checkpoint recovery."""

import pytest

from lagent.agent.lifecycle import QuestRecoveryController
from lagent.agent.quest.checkpoint import QuestCheckpointManager, QuestRecoveryState
from lagent.common import (
    ObjectiveStep,
    QuestPerceptionEvidence,
    QuestPerceptionStatus,
    QuestResource,
)
from lagent.common.sessions_db import SessionsDB


def make_resource():
    return QuestResource(
        quest_id="marcela_supply_check",
        quest_name="Supply Check",
        starting_npc="Marcela",
        objective_sequence=[
            ObjectiveStep(order=1, id="talk_marcela", name="Talk", target_npc="Marcela", type="dialogue"),
            ObjectiveStep(order=2, id="confirm_supply", name="Confirm", target_npc="Marcela", type="dialogue"),
        ],
        navigation_route=["marcela"],
        safe_stop_conditions=["ambiguous_state"],
    )


def verified_evidence():
    return QuestPerceptionEvidence(
        quest_id="marcela_supply_check",
        evidence_type="objective",
        status=QuestPerceptionStatus.FOUND,
        confidence=0.96,
        raw_ocr_text="Objective complete",
    )


@pytest.fixture
def database(tmp_path):
    db = SessionsDB(str(tmp_path / "sessions.db"))
    db.log_session_start("session-9", "quest", "shadow")
    yield db
    db.close()


def test_verified_objective_boundary_is_persisted_with_session_identity(database):
    manager = QuestCheckpointManager(database, "session-9", make_resource())

    checkpoint = manager.checkpoint_objective(0, verification_source="quest_perception", evidence=verified_evidence())
    events = database.get_events_by_type("session-9", "quest_checkpoint")

    assert checkpoint.objective_index == 0
    assert checkpoint.status == "verified"
    assert checkpoint.verification_source == "quest_perception"
    assert events[-1]["payload"]["session_id"] == "session-9"
    assert events[-1]["payload"]["evidence"]["status"] == "found"


def test_unverified_or_mid_objective_checkpoint_is_rejected(database):
    manager = QuestCheckpointManager(database, "session-9", make_resource())
    ambiguous = verified_evidence().model_copy(update={"status": QuestPerceptionStatus.AMBIGUOUS})

    with pytest.raises(ValueError, match="verified objective boundary"):
        manager.checkpoint_objective(0, verification_source="timer", evidence=ambiguous)

    assert database.get_events_by_type("session-9", "quest_checkpoint") == []


def test_process_restart_restores_only_next_objective_from_latest_valid_checkpoint(database):
    QuestCheckpointManager(database, "session-9", make_resource()).checkpoint_objective(
        0, verification_source="quest_perception", evidence=verified_evidence()
    )

    restarted = QuestCheckpointManager(database, "session-9", make_resource())
    decision = restarted.restore("process_restart")

    assert decision.state is QuestRecoveryState.RESUME
    assert decision.next_objective_index == 1
    assert decision.checkpoint.objective_index == 0


def test_interruption_before_checkpoint_requires_safe_stop(database):
    manager = QuestCheckpointManager(database, "session-9", make_resource())

    decision = manager.restore("disconnect")

    assert decision.state is QuestRecoveryState.SAFE_STOP
    assert decision.reason == "operator_intervention_required"
    assert decision.next_objective_index is None


def test_death_recovery_uses_checkpoint_boundary_not_prior_runtime_state(database):
    manager = QuestCheckpointManager(database, "session-9", make_resource())
    manager.checkpoint_objective(0, verification_source="quest_perception", evidence=verified_evidence())
    recovery = QuestRecoveryController(manager)

    decision = recovery.recover("death_detected", prior_runtime_state="interacting")

    assert decision.state is QuestRecoveryState.RESUME
    assert decision.next_objective_index == 1
    assert decision.reason == "death_detected"


def test_failure_event_contains_retry_and_last_verified_evidence(database):
    manager = QuestCheckpointManager(database, "session-9", make_resource())
    manager.checkpoint_objective(0, verification_source="quest_perception", evidence=verified_evidence())

    manager.log_failure("route_stuck_retry_exhausted", objective_index=1, retry_count=3)
    payload = database.get_events_by_type("session-9", "quest_failure")[-1]["payload"]

    assert payload["objective_index"] == 1
    assert payload["retry_count"] == 3
    assert payload["reason"] == "route_stuck_retry_exhausted"
    assert payload["last_verified_evidence"]["raw_ocr_text"] == "Objective complete"