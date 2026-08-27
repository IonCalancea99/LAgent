"""Resource-backed quest dialogue matching."""

from __future__ import annotations

from dataclasses import dataclass

from lagent.common import DialogueChoice, QuestPerceptionEvidence, QuestPerceptionStatus, QuestResource


@dataclass(frozen=True)
class DialogueMatch:
    choice: DialogueChoice | None
    failure_reason: str | None = None


class DialogueSelector:
    """Select only the current objective's exact validated dialogue choice."""

    def __init__(self, resource: QuestResource, confidence_threshold: float = 0.8) -> None:
        self.resource = resource
        self.confidence_threshold = confidence_threshold

    @staticmethod
    def _normalized(text: str | None) -> str:
        return " ".join((text or "").casefold().split())

    def select(
        self,
        npc: QuestPerceptionEvidence,
        objective: QuestPerceptionEvidence,
        dialogue: QuestPerceptionEvidence,
        *,
        objective_index: int = 0,
    ) -> DialogueMatch:
        if not 0 <= objective_index < len(self.resource.objective_sequence):
            return DialogueMatch(None, "objective_index_out_of_range")
        expected_objective = self.resource.objective_sequence[objective_index]
        if (
            npc.status is not QuestPerceptionStatus.FOUND
            or self._normalized(npc.observed_value) != self._normalized(expected_objective.target_npc)
        ):
            return DialogueMatch(None, "npc_mismatch")
        if (
            objective.status is not QuestPerceptionStatus.FOUND
            or self._normalized(expected_objective.name) not in self._normalized(objective.raw_ocr_text)
        ):
            return DialogueMatch(None, "objective_mismatch")
        if dialogue.status is not QuestPerceptionStatus.FOUND or dialogue.confidence < self.confidence_threshold:
            return DialogueMatch(None, "ambiguous_dialogue")

        required_key = expected_objective.dialogue_choice
        if dialogue.selected_dialogue_key != required_key or required_key is None:
            return DialogueMatch(None, "ambiguous_dialogue")
        choice = next((item for item in self.resource.dialogue_options if item.key == required_key), None)
        if choice is None or self._normalized(choice.text) != self._normalized(dialogue.raw_ocr_text):
            return DialogueMatch(None, "ambiguous_dialogue")
        return DialogueMatch(choice)