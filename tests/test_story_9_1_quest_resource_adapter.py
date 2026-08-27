"""Acceptance tests for Story 9.1: quest resource adapter and validation."""

from copy import deepcopy

import pytest

from lagent.agent.quest import QuestResourceAdapter, QuestResourceValidationError
from lagent.agent.quest.schema import QuestProfile, validate_quest_profile
from lagent.common import AgentProfile

VALID_RESOURCE = {
    "quest_id": "marcela_supply_check",
    "quest_name": "Supply Check",
    "starting_npc": "Marcela",
    "objective_sequence": [
        {
            "order": 1,
            "id": "talk_marcela",
            "name": "Speak to Marcela",
            "target_npc": "Marcela",
            "type": "dialogue",
            "completion_indicators": ["conversation_started"],
            "dialogue_choice": "supply_check",
            "route_hint": "north_gate",
            "timeout_seconds": 30.0,
            "retry_limit": 2,
        },
        {
            "order": 2,
            "id": "visit_vendor",
            "name": "Visit the vendor",
            "target_npc": "Mira",
            "type": "travel",
            "completion_indicators": ["vendor_reached"],
            "route_hint": "market_lane",
            "timeout_seconds": 45.0,
            "retry_limit": 3,
        },
    ],
    "dialogue_options": [
        {"key": "A", "text": "I am here for the supply check.", "requires_confirmation": False},
        {"key": "B", "text": "Tell me what you need.", "requires_confirmation": True},
    ],
    "navigation_route": ["town_square", "market_lane"],
    "timeouts": {"travel": 45.0, "dialogue": 30.0},
    "retries": {"dialogue": 2, "travel": 3},
    "safe_stop_conditions": ["unknown_npc", "unsupported_route"],
    "completion_indicators": ["quest_complete"],
}


def test_valid_resource_parses_into_canonical_contract():
    resource = QuestResourceAdapter.validate_resource(VALID_RESOURCE)

    assert resource.quest_id == "marcela_supply_check"
    assert resource.quest_name == "Supply Check"
    assert resource.starting_npc == "Marcela"
    assert [step.id for step in resource.objective_sequence] == ["talk_marcela", "visit_vendor"]
    assert resource.dialogue_options[0].key == "A"
    assert resource.navigation_route == ["town_square", "market_lane"]


@pytest.mark.parametrize(
    "payload_factory, match",
    [
        (lambda payload: {**payload, "quest_id": ""}, "quest_id"),
        (
            lambda payload: {
                **payload,
                "objective_sequence": [
                    {"order": 2, "id": "first_step", "name": "First", "target_npc": "Marcela", "type": "dialogue"},
                    {"order": 1, "id": "second_step", "name": "Second", "target_npc": "Mira", "type": "travel"},
                ],
            },
            "objective_sequence",
        ),
    ],
)
def test_missing_or_malformed_values_fail_closed(payload_factory, match):
    payload = payload_factory(deepcopy(VALID_RESOURCE))

    with pytest.raises(QuestResourceValidationError, match=match):
        QuestResourceAdapter.validate_resource(payload)


def test_profile_schema_accepts_quest_enabled_profile_and_rejects_invalid_values():
    profile_dict = {
        "name": "quest",
        "roi_positions": {},
        "fsm_bindings": {},
        "skill_key_bindings": {},
        "buff_timer_durations": {},
        "confidence_thresholds": {},
        "skill_timing": {"default": {"mean": 0.1, "std": 0.05}},
        "quest_profile": {
            "quest_id": "marcela_supply_check",
            "quest_name": "Supply Check",
            "starting_npc": "Marcela",
            "objective_sequence": ["talk_marcela", "visit_vendor"],
            "dialogue_options": ["supply_check"],
            "navigation_route": ["town_square", "market_lane"],
            "timeouts": {"travel": 45.0},
            "retries": {"travel": 3},
            "safe_stop_conditions": ["unknown_npc"],
        },
    }

    validated = validate_quest_profile(profile_dict)
    assert isinstance(validated, QuestProfile)
    assert validated.quest_id == "marcela_supply_check"

    invalid = deepcopy(profile_dict)
    invalid["quest_profile"]["starting_npc"] = "Unknown NPC"

    with pytest.raises(QuestResourceValidationError, match="starting_npc|unsupported"):
        validate_quest_profile(invalid)


def test_agent_profile_remains_compatible_without_quest_data():
    profile = AgentProfile(
        name="warlord",
        roi_positions={},
        fsm_bindings={},
        skill_key_bindings={},
        buff_timer_durations={},
        confidence_thresholds={},
        skill_timing={"default": {"mean": 0.1, "std": 0.05}},
    )

    assert profile.name == "warlord"
    assert validate_quest_profile(profile) is profile
