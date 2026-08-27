"""Acceptance tests for Story 9.2: deterministic Supply Check perception."""

from copy import deepcopy

import pytest

from lagent.common import QuestPerceptionStatus
from lagent.gpu_server.quest_fixture import (
    SupplyCheckFixtureEvaluator,
    load_supply_check_fixture,
)


@pytest.fixture
def evaluator() -> SupplyCheckFixtureEvaluator:
    return SupplyCheckFixtureEvaluator(confidence_threshold=0.8)


@pytest.mark.parametrize(
    ("fixture_name", "evidence_type"),
    [
        ("marcela", "npc"),
        ("objective", "objective"),
        ("interaction_prompt", "interaction_prompt"),
        ("dialogue", "dialogue"),
    ],
)
def test_positive_fixtures_produce_contract_evidence(evaluator, fixture_name, evidence_type):
    result = evaluator.evaluate(load_supply_check_fixture(fixture_name))

    assert result.status is QuestPerceptionStatus.FOUND
    assert result.evidence_type == evidence_type
    assert result.quest_id == "marcela_supply_check"
    assert result.confidence >= 0.8


def test_dialogue_records_raw_ocr_text_for_validated_choice(evaluator):
    result = evaluator.evaluate(load_supply_check_fixture("dialogue"))

    assert result.selected_dialogue_key == "supply_check"
    assert result.raw_ocr_text == "I am here for the supply check."


@pytest.mark.parametrize(
    ("fixture_name", "expected_status"),
    [
        ("npc_missing", QuestPerceptionStatus.NOT_FOUND),
        ("npc_blurred", QuestPerceptionStatus.AMBIGUOUS),
        ("objective_occluded", QuestPerceptionStatus.AMBIGUOUS),
        ("prompt_low_confidence", QuestPerceptionStatus.AMBIGUOUS),
        ("dialogue_occluded", QuestPerceptionStatus.VERIFY_FAILED),
        ("dialogue_low_confidence", QuestPerceptionStatus.VERIFY_FAILED),
        ("completion_missing", QuestPerceptionStatus.VERIFY_FAILED),
    ],
)
def test_negative_and_ambiguous_fixtures_fail_closed(evaluator, fixture_name, expected_status):
    result = evaluator.evaluate(load_supply_check_fixture(fixture_name))

    assert result.status is expected_status
    assert result.selected_dialogue_key is None


def test_completion_requires_transition_and_explicit_evidence(evaluator):
    valid = evaluator.evaluate(load_supply_check_fixture("completion"))
    stale_fixture = deepcopy(load_supply_check_fixture("completion"))
    stale_fixture["objective_transition"] = False
    stale = evaluator.evaluate(stale_fixture)

    assert valid.status is QuestPerceptionStatus.FOUND
    assert valid.evidence_type == "completion"
    assert valid.objective_transition is True
    assert valid.safe_terminal is True
    assert stale.status is QuestPerceptionStatus.VERIFY_FAILED
    assert stale.safe_terminal is False


@pytest.mark.parametrize("fixture_name", ["marcela", "objective", "dialogue", "completion"])
def test_repeated_fixture_replay_is_deterministic(evaluator, fixture_name):
    fixture = load_supply_check_fixture(fixture_name)

    first = evaluator.evaluate(deepcopy(fixture))
    second = evaluator.evaluate(deepcopy(fixture))

    assert first.model_dump() == second.model_dump()