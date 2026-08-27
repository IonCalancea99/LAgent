"""Quest profile schema validation for the quest-enabled contract."""

from __future__ import annotations

from typing import Any

from lagent.agent.quest.adapter import QuestResourceAdapter
from lagent.common import AgentProfile
from lagent.common.types import QuestResource, QuestResourceValidationError


class QuestProfile:
    """Advisory schema object for quest-capable profiles."""

    def __init__(self, *, quest_id: str, quest_name: str, starting_npc: str, objective_sequence: list[str], dialogue_options: list[str], navigation_route: list[str], timeouts: dict[str, float], retries: dict[str, int], safe_stop_conditions: list[str]):
        self.quest_id = quest_id
        self.quest_name = quest_name
        self.starting_npc = starting_npc
        self.objective_sequence = objective_sequence
        self.dialogue_options = dialogue_options
        self.navigation_route = navigation_route
        self.timeouts = timeouts
        self.retries = retries
        self.safe_stop_conditions = safe_stop_conditions


def validate_quest_profile(profile: Any) -> AgentProfile | QuestProfile:
    """Validate a profile with optional quest metadata and return the normalized contract."""
    if isinstance(profile, (AgentProfile,)):
        return profile

    if not isinstance(profile, dict):
        raise QuestResourceValidationError("profile must be a mapping")

    quest_profile = profile.get("quest_profile")
    if quest_profile is None:
        return profile

    if not isinstance(quest_profile, dict):
        raise QuestResourceValidationError("quest_profile must be a mapping")

    normalized_profile = dict(quest_profile)
    objectives = normalized_profile.get("objective_sequence")
    if isinstance(objectives, list) and all(isinstance(item, str) for item in objectives):
        normalized_profile["objective_sequence"] = [
            {
                "order": index,
                "id": objective_id,
                "name": objective_id.replace("_", " ").title(),
                "target_npc": normalized_profile.get("starting_npc", ""),
                "type": "profile",
            }
            for index, objective_id in enumerate(objectives, start=1)
        ]

    dialogue_options = normalized_profile.get("dialogue_options")
    if isinstance(dialogue_options, list) and all(isinstance(item, str) for item in dialogue_options):
        normalized_profile["dialogue_options"] = [
            {"key": option, "text": option.replace("_", " ").title()}
            for option in dialogue_options
        ]

    resource = QuestResourceAdapter.validate_resource(normalized_profile)

    if resource.starting_npc not in {"Marcela", "Mira"}:
        raise QuestResourceValidationError("unsupported starting_npc for quest profile")

    return QuestProfile(
        quest_id=resource.quest_id,
        quest_name=resource.quest_name,
        starting_npc=resource.starting_npc,
        objective_sequence=[step.id for step in resource.objective_sequence],
        dialogue_options=[choice.key for choice in resource.dialogue_options],
        navigation_route=resource.navigation_route,
        timeouts=resource.timeouts,
        retries=resource.retries,
        safe_stop_conditions=resource.safe_stop_conditions,
    )
