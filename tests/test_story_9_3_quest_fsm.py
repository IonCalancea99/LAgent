"""Acceptance tests for Story 9.3: deterministic quest FSM."""

from lagent.agent.quest.fsm import QuestFSM
from lagent.agent.quest.state import QuestEvent, QuestState
from lagent.common import (
    ObjectiveStep,
    QuestPerceptionEvidence,
    QuestPerceptionStatus,
    QuestResource,
)


class EventDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def make_resource(retry_limit=2):
    return QuestResource(
        quest_id="marcela_supply_check",
        quest_name="Supply Check",
        starting_npc="Marcela",
        objective_sequence=[
            ObjectiveStep(
                order=1,
                id="talk_marcela",
                name="Talk to Marcela",
                target_npc="Marcela",
                type="dialogue",
                retry_limit=retry_limit,
            ),
            ObjectiveStep(
                order=2,
                id="confirm_supply",
                name="Confirm the supply check",
                target_npc="Marcela",
                type="dialogue",
                retry_limit=retry_limit,
            ),
        ],
        navigation_route=["town_square", "marcela"],
        retries={"default": retry_limit},
        safe_stop_conditions=["ambiguous", "retry_exhausted"],
    )


def found_evidence(evidence_type="objective"):
    return QuestPerceptionEvidence(
        quest_id="marcela_supply_check",
        evidence_type=evidence_type,
        status=QuestPerceptionStatus.FOUND,
        confidence=0.95,
    )


def event(sequence, event_type, evidence=None, objective_index=0):
    return QuestEvent(
        event_id=f"event-{sequence}",
        sequence=sequence,
        event_type=event_type,
        objective_index=objective_index,
        evidence=evidence,
    )


def test_happy_path_uses_explicit_states_and_completes_only_after_verification():
    fsm = QuestFSM(make_resource())

    assert fsm.state is QuestState.DISCOVERING
    assert fsm.handle(event(1, "resource_validated")) is True
    assert fsm.state is QuestState.NAVIGATING
    assert fsm.handle(event(2, "navigation_verified")) is True
    assert fsm.state is QuestState.INTERACTING
    assert fsm.handle(event(3, "interaction_verified")) is True
    assert fsm.state is QuestState.VERIFYING
    assert fsm.handle(event(4, "objective_verified", found_evidence())) is True
    assert fsm.current_objective_index == 1
    assert fsm.state is QuestState.NAVIGATING

    fsm.handle(event(5, "navigation_verified", objective_index=1))
    fsm.handle(event(6, "interaction_verified", objective_index=1))
    fsm.handle(event(7, "objective_verified", found_evidence(), objective_index=1))

    assert fsm.state is QuestState.COMPLETE
    assert fsm.terminal_reason == "completed"


def test_timer_or_unverified_evidence_cannot_advance_objective():
    fsm = QuestFSM(make_resource())
    fsm.handle(event(1, "resource_validated"))
    fsm.handle(event(2, "navigation_verified"))
    fsm.handle(event(3, "interaction_verified"))
    unverified = QuestPerceptionEvidence(
        quest_id="marcela_supply_check",
        evidence_type="objective",
        status=QuestPerceptionStatus.AMBIGUOUS,
        confidence=0.4,
    )

    assert fsm.handle(event(4, "objective_verified", unverified)) is False
    assert fsm.handle(event(5, "timer_elapsed")) is False
    assert fsm.current_objective_index == 0
    assert fsm.state is QuestState.VERIFYING


def test_retry_exhaustion_enters_safe_stop_with_specific_reason():
    fsm = QuestFSM(make_resource(retry_limit=2))
    fsm.handle(event(1, "resource_validated"))

    assert fsm.handle(event(2, "navigation_failed")) is True
    assert fsm.state is QuestState.RETRY
    assert fsm.retries_remaining == 1
    assert fsm.handle(event(3, "retry_navigation")) is True
    assert fsm.state is QuestState.NAVIGATING
    assert fsm.handle(event(4, "navigation_failed")) is True
    assert fsm.state is QuestState.SAFE_STOP
    assert fsm.terminal_reason == "navigation_failed_retry_exhausted"


def test_duplicate_and_stale_events_are_ignored():
    fsm = QuestFSM(make_resource())
    first = event(1, "resource_validated")

    assert fsm.handle(first) is True
    assert fsm.handle(first) is False
    assert fsm.handle(QuestEvent(event_id="stale", sequence=0, event_type="navigation_verified", objective_index=0)) is False
    assert fsm.state is QuestState.NAVIGATING


def test_each_transition_emits_structured_session_event():
    database = EventDB()
    fsm = QuestFSM(make_resource(), session_id="session-9", db=database)

    fsm.handle(event(1, "resource_validated"))
    fsm.handle(event(2, "navigation_failed"))

    assert len(database.events) == 2
    session_id, source, event_type, payload = database.events[-1]
    assert (session_id, source, event_type) == ("session-9", "agent.quest", "quest_transition")
    assert payload["objective_index"] == 0
    assert payload["state"] == "retry"
    assert payload["retries_remaining"] == 1
    assert payload["reason"] == "navigation_failed"
    assert payload["terminal_result"] is None