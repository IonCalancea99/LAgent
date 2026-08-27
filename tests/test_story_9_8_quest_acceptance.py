"""Acceptance tests for Story 9.8: shadow replay and live gate."""

from copy import deepcopy
import random

from lagent.agent.quest.acceptance import (
    LiveQuestGate,
    SupplyCheckReplayHarness,
    build_supply_check_resource,
    load_supply_check_acceptance_fixture,
)
from lagent.common.sessions_db import SessionsDB
from lagent.hsl import HSL


class FailingController:
    def move(self, x, y):
        raise AssertionError("shadow replay emitted OS mouse movement")

    def click(self, button="left", clicks=1):
        raise AssertionError("shadow replay emitted OS mouse click")

    def press(self, key):
        raise AssertionError("shadow replay emitted OS keyboard input")


def make_harness(tmp_path, session_id="shadow-9"):
    database = SessionsDB(str(tmp_path / f"{session_id}.db"))
    database.log_session_start(session_id, "orc_fighter_level_3", "shadow")
    hsl = HSL(
        {"skill_timing": {"default": {"mean": 0.1, "std": 0.0}}},
        controller=FailingController(),
        keyboard_controller=FailingController(),
        sleeper=lambda _: None,
        rng=random.Random(9),
        mode="shadow",
        session_id=session_id,
        sessions_db=database,
    )
    resource = build_supply_check_resource()
    harness = SupplyCheckReplayHarness(
        resource,
        profile_id="orc_fighter_level_3",
        hsl=hsl,
        db=database,
        session_id=session_id,
    )
    return harness, database, resource


def test_full_shadow_replay_completes_without_os_input_and_logs_reviewable_trace(tmp_path):
    harness, database, _ = make_harness(tmp_path)

    result = harness.run(load_supply_check_acceptance_fixture())

    assert result.success is True
    assert result.terminal_state == "complete"
    assert result.verified_objectives == [0, 1]
    assert result.completion_evidence is True
    transitions = database.get_events_by_type("shadow-9", "quest_transition")
    assert {event["payload"]["objective_index"] for event in transitions} == {0, 1}
    assert transitions[-1]["payload"]["terminal_result"] == "completed"
    assert database.get_events_by_type("shadow-9", "action")
    database.close()


def test_missing_or_ambiguous_evidence_never_claims_shadow_success(tmp_path):
    harness, database, _ = make_harness(tmp_path)
    fixture = load_supply_check_acceptance_fixture()
    fixture["objectives"][0]["npc_fixture"] = "npc_missing"

    result = harness.run(fixture)

    assert result.success is False
    assert result.terminal_state in {"retry", "safe_stop"}
    assert result.failure_reason == "npc_not_found"
    assert result.completion_evidence is False
    database.close()


def test_live_gate_requires_passing_shadow_for_exact_contract_and_profile(tmp_path):
    harness, database, resource = make_harness(tmp_path)
    passing = harness.run(load_supply_check_acceptance_fixture())
    gate = LiveQuestGate()

    assert gate.validate(resource, "orc_fighter_level_3", passing).allowed is True
    assert gate.validate(resource, "different_profile", passing).allowed is False
    changed = resource.model_copy(update={"retries": {"travel": 99, "dialogue": 99}})
    assert gate.validate(changed, "orc_fighter_level_3", passing).allowed is False

    failed_fixture = load_supply_check_acceptance_fixture()
    failed_fixture["objectives"][1]["completion_fixture"] = "completion_missing"
    failed = harness.run(failed_fixture)
    assert gate.validate(resource, "orc_fighter_level_3", failed).allowed is False
    database.close()


def test_stale_evidence_and_missing_explicit_completion_fail_closed(tmp_path):
    stale_harness, stale_db, _ = make_harness(tmp_path, "stale-9")
    stale = load_supply_check_acceptance_fixture()
    stale["objectives"][1]["sequence"] = stale["objectives"][0]["sequence"]

    stale_result = stale_harness.run(stale)

    assert stale_result.success is False
    assert stale_result.failure_reason == "stale_evidence"
    stale_db.close()

    missing_harness, missing_db, _ = make_harness(tmp_path, "missing-9")
    missing = load_supply_check_acceptance_fixture()
    missing["objectives"][1]["completion_fixture"] = "completion_missing"
    missing_result = missing_harness.run(missing)

    assert missing_result.success is False
    assert missing_result.failure_reason == "completion_verify_failed"
    missing_db.close()


def test_replaying_same_fixture_produces_same_objective_transition_payloads(tmp_path):
    first_harness, first_db, _ = make_harness(tmp_path, "first-9")
    second_harness, second_db, _ = make_harness(tmp_path, "second-9")
    fixture = load_supply_check_acceptance_fixture()

    first_harness.run(deepcopy(fixture))
    second_harness.run(deepcopy(fixture))
    first_trace = [event["payload"] for event in first_db.get_events_by_type("first-9", "quest_transition")]
    second_trace = [event["payload"] for event in second_db.get_events_by_type("second-9", "quest_transition")]

    assert first_trace == second_trace
    first_db.close()
    second_db.close()