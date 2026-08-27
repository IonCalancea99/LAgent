"""Provider boundary adapter for quest resources."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from lagent.common.types import (
    DialogueChoice,
    ObjectiveStep,
    QuestResource,
    QuestResourceValidationError,
)


class QuestResourceAdapter:
    """Validate and normalize external quest metadata into the canonical contract."""

    _required_fields = {
        "quest_id",
        "quest_name",
        "starting_npc",
        "objective_sequence",
        "dialogue_options",
        "navigation_route",
        "timeouts",
        "retries",
        "safe_stop_conditions",
    }

    @staticmethod
    def validate_resource(resource: dict[str, Any] | QuestResource) -> QuestResource:
        """Translate an external provider payload into the runtime contract."""
        if isinstance(resource, QuestResource):
            return resource
        if not isinstance(resource, dict):
            raise QuestResourceValidationError("resource must be a mapping")

        missing = sorted(QuestResourceAdapter._required_fields - set(resource))
        if missing:
            field = missing[0]
            raise QuestResourceValidationError(f"resource missing required field: {field}")

        quest_id = str(resource["quest_id"]).strip()
        quest_name = str(resource["quest_name"]).strip()
        starting_npc = str(resource["starting_npc"]).strip()
        if not quest_id or not quest_name or not starting_npc:
            raise QuestResourceValidationError("quest_id, quest_name, and starting_npc are required")

        objectives_raw = resource["objective_sequence"]
        if not isinstance(objectives_raw, list) or not objectives_raw:
            raise QuestResourceValidationError("objective_sequence must be a non-empty list")

        objective_steps: list[ObjectiveStep] = []
        seen_orders: set[int] = set()
        for index, raw_step in enumerate(objectives_raw):
            if not isinstance(raw_step, dict):
                raise QuestResourceValidationError(f"objective_sequence[{index}] must be a mapping")
            if "order" not in raw_step or "id" not in raw_step or "target_npc" not in raw_step:
                raise QuestResourceValidationError(f"objective_sequence[{index}] is missing required fields")
            order = int(raw_step["order"])
            if order in seen_orders:
                raise QuestResourceValidationError("objective_sequence has duplicate order values")
            seen_orders.add(order)
            if order != index + 1:
                raise QuestResourceValidationError("objective_sequence must be sequential and start at 1")

            try:
                objective_steps.append(
                    ObjectiveStep(
                        order=order,
                        id=str(raw_step["id"]).strip(),
                        name=str(raw_step.get("name", raw_step["id"])).strip(),
                        target_npc=str(raw_step["target_npc"]).strip(),
                        type=str(raw_step.get("type", "unknown")).strip(),
                        completion_indicators=[str(item).strip() for item in raw_step.get("completion_indicators", [])],
                        dialogue_choice=(str(raw_step["dialogue_choice"]).strip() if raw_step.get("dialogue_choice") is not None else None),
                        route_hint=(str(raw_step["route_hint"]).strip() if raw_step.get("route_hint") is not None else None),
                        timeout_seconds=float(raw_step["timeout_seconds"]) if raw_step.get("timeout_seconds") is not None else None,
                        retry_limit=int(raw_step["retry_limit"]) if raw_step.get("retry_limit") is not None else None,
                    )
                )
            except ValidationError as exc:
                raise QuestResourceValidationError(f"objective_sequence[{index}] failed contract validation: {exc}") from exc

        if not objective_steps:
            raise QuestResourceValidationError("objective_sequence must not be empty")

        dialogue_raw = resource["dialogue_options"]
        if not isinstance(dialogue_raw, list):
            raise QuestResourceValidationError("dialogue_options must be a list")
        dialogue_options = [
            DialogueChoice(
                key=str(item["key"]).strip(),
                text=str(item["text"]).strip(),
                requires_confirmation=bool(item.get("requires_confirmation", False)),
            )
            for item in dialogue_raw
        ]

        navigation_route = resource["navigation_route"]
        if not isinstance(navigation_route, list) or not navigation_route:
            raise QuestResourceValidationError("navigation_route must be a non-empty list")

        timeouts = resource["timeouts"]
        if not isinstance(timeouts, dict):
            raise QuestResourceValidationError("timeouts must be a mapping")

        retries = resource["retries"]
        if not isinstance(retries, dict):
            raise QuestResourceValidationError("retries must be a mapping")

        safe_stop_conditions = resource["safe_stop_conditions"]
        if not isinstance(safe_stop_conditions, list) or not safe_stop_conditions:
            raise QuestResourceValidationError("safe_stop_conditions must be a non-empty list")

        completion_indicators = resource.get("completion_indicators", [])
        if not isinstance(completion_indicators, list):
            raise QuestResourceValidationError("completion_indicators must be a list")

        if any(step.target_npc == "unknown" for step in objective_steps):
            raise QuestResourceValidationError("unsupported target NPC encountered")

        try:
            quest = QuestResource(
                quest_id=quest_id,
                quest_name=quest_name,
                starting_npc=starting_npc,
                objective_sequence=objective_steps,
                dialogue_options=dialogue_options,
                navigation_route=[str(item) for item in navigation_route],
                timeouts={str(key): float(value) for key, value in timeouts.items()},
                retries={str(key): int(value) for key, value in retries.items()},
                safe_stop_conditions=[str(item) for item in safe_stop_conditions],
                completion_indicators=[str(item) for item in completion_indicators],
            )
        except ValidationError as exc:
            raise QuestResourceValidationError(f"resource failed contract validation: {exc}") from exc
        return quest

    @staticmethod
    def parse_resource(resource: dict[str, Any]) -> QuestResource:
        """Compatibility alias for the external provider parser."""
        return QuestResourceAdapter.validate_resource(resource)
