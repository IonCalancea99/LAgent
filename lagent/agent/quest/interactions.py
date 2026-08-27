"""Bounded quest NPC interaction and dialogue dispatch."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping

from lagent.agent.quest.dialogue import DialogueSelector
from lagent.common import Action, QuestPerceptionEvidence, QuestPerceptionStatus, QuestResource


class InteractionStatus(str, Enum):
    READY = "ready"
    DIALOGUE = "dialogue"
    RETRY = "retry"
    COMPLETE = "complete"
    SAFE_STOP = "safe_stop"


@dataclass(frozen=True)
class InteractionOutcome:
    action: Action | None
    event_type: str | None = None
    failure_reason: str | None = None
    terminal: bool = False


class QuestInteractionController:
    """Gate all quest interaction actions on validated perception evidence."""

    def __init__(
        self,
        resource: QuestResource,
        *,
        hsl: Any,
        interaction_action: Action,
        dialogue_positions: Mapping[str, tuple[int, int]],
        session_id: str,
        db: Any | None = None,
        objective_index: int = 0,
        clock: Callable[[], float] = time.monotonic,
        confidence_threshold: float = 0.8,
    ) -> None:
        self.resource = resource
        self.hsl = hsl
        self.interaction_action = interaction_action
        self.dialogue_positions = dialogue_positions
        self.session_id = session_id
        self.db = db
        self.objective_index = objective_index
        self.clock = clock
        self.started_at = clock()
        self.deadline_seconds = resource.timeouts.get("dialogue", 30.0)
        self.retries_remaining = resource.retries.get("dialogue", 0)
        self.selector = DialogueSelector(resource, confidence_threshold)
        self.status = InteractionStatus.READY

    def _log(self, event_type: str, reason: str, *, terminal: bool) -> None:
        if self.db is None:
            return
        self.db.append_event(
            self.session_id,
            "agent.quest",
            event_type,
            {
                "session_id": self.session_id,
                "quest_id": self.resource.quest_id,
                "objective_index": self.objective_index,
                "reason": reason,
                "retries_remaining": self.retries_remaining,
                "terminal": terminal,
            },
        )

    def _failure(self, reason: str) -> InteractionOutcome:
        self.retries_remaining = max(0, self.retries_remaining - 1)
        terminal = self.retries_remaining == 0
        failure_reason = f"{reason}_retry_exhausted" if terminal else reason
        self.status = InteractionStatus.SAFE_STOP if terminal else InteractionStatus.RETRY
        self._log("quest_interaction_failure", failure_reason, terminal=terminal)
        return InteractionOutcome(None, failure_reason=failure_reason, terminal=terminal)

    def _deadline_failure(self) -> InteractionOutcome:
        self.status = InteractionStatus.SAFE_STOP
        self._log("quest_interaction_failure", "interaction_timeout", terminal=True)
        return InteractionOutcome(None, failure_reason="interaction_timeout", terminal=True)

    def begin_interaction(
        self,
        npc: QuestPerceptionEvidence,
        prompt: QuestPerceptionEvidence,
    ) -> InteractionOutcome:
        if self.status is InteractionStatus.SAFE_STOP or self.clock() - self.started_at > self.deadline_seconds:
            return self._deadline_failure()
        if not 0 <= self.objective_index < len(self.resource.objective_sequence):
            return self._failure("objective_index_out_of_range")
        expected_npc = self.resource.objective_sequence[self.objective_index].target_npc
        if (
            npc.status is not QuestPerceptionStatus.FOUND
            or (npc.observed_value or "").casefold() != expected_npc.casefold()
        ):
            return self._failure("npc_not_found")
        if prompt.status is not QuestPerceptionStatus.FOUND or prompt.evidence_type != "interaction_prompt":
            return self._failure("interaction_timeout")

        self.hsl.dispatch_action(self.interaction_action)
        self.status = InteractionStatus.DIALOGUE
        self._log("quest_interaction_transition", "interaction_verified", terminal=False)
        return InteractionOutcome(self.interaction_action, event_type="interaction_verified")

    def select_dialogue(
        self,
        npc: QuestPerceptionEvidence,
        objective: QuestPerceptionEvidence,
        dialogue: QuestPerceptionEvidence,
    ) -> InteractionOutcome:
        if self.status is not InteractionStatus.DIALOGUE:
            return InteractionOutcome(None, failure_reason="interaction_not_verified")
        match = self.selector.select(npc, objective, dialogue, objective_index=self.objective_index)
        if match.choice is None:
            return self._failure(match.failure_reason or "ambiguous_dialogue")
        position = self.dialogue_positions.get(match.choice.key)
        if position is None:
            return self._failure("dialogue_position_missing")

        action = Action(action_type="mouse_click", x=position[0], y=position[1], button="left", clicks=1)
        self.hsl.dispatch_action(action)
        self.status = InteractionStatus.COMPLETE
        self._log("quest_interaction_transition", "objective_verified", terminal=False)
        return InteractionOutcome(action, event_type="objective_verified")