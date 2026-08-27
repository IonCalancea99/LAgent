"""Agent-owned deterministic quest state machine."""

from __future__ import annotations

from typing import Any

from lagent.agent.quest.state import QuestEvent, QuestState
from lagent.common import QuestPerceptionStatus, QuestResource


class QuestFSM:
    """Advance ordered objectives only through positively verified events."""

    _FAILURE_EVENTS = {"timeout", "ambiguous", "navigation_failed", "interaction_failed"}

    def __init__(self, resource: QuestResource, session_id: str | None = None, db: Any | None = None) -> None:
        if not resource.objective_sequence:
            raise ValueError("quest resource must contain objectives")
        self.resource = resource
        self.session_id = session_id
        self.db = db
        self.state = QuestState.DISCOVERING
        self.current_objective_index = 0
        self.retries_remaining = self._retry_limit()
        self.terminal_reason: str | None = None
        self._seen_event_ids: set[str] = set()
        self._last_sequence = -1
        self._retry_state = QuestState.NAVIGATING

    def _retry_limit(self) -> int:
        objective = self.resource.objective_sequence[self.current_objective_index]
        if objective.retry_limit is not None:
            return objective.retry_limit
        return self.resource.retries.get("default", 0)

    def _log_transition(self, reason: str) -> None:
        if self.db is None or self.session_id is None:
            return
        objective = self.resource.objective_sequence[self.current_objective_index]
        self.db.append_event(
            self.session_id,
            "agent.quest",
            "quest_transition",
            {
                "quest_id": self.resource.quest_id,
                "quest_name": self.resource.quest_name,
                "objective_index": self.current_objective_index,
                "objective_id": objective.id,
                "objective_name": objective.name,
                "total_objectives": len(self.resource.objective_sequence),
                "state": self.state.value,
                "event_sequence": self._last_sequence,
                "retries_remaining": self.retries_remaining,
                "reason": reason,
                "terminal_result": self.terminal_reason,
            },
        )

    def _transition(self, state: QuestState, reason: str, terminal_reason: str | None = None) -> bool:
        self.state = state
        self.terminal_reason = terminal_reason
        self._log_transition(reason)
        return True

    def _handle_failure(self, event_type: str) -> bool:
        retry_state = {
            "navigation_failed": QuestState.NAVIGATING,
            "interaction_failed": QuestState.INTERACTING,
        }.get(event_type, self.state)
        self.retries_remaining = max(0, self.retries_remaining - 1)
        if self.retries_remaining == 0:
            reason = f"{event_type}_retry_exhausted"
            return self._transition(QuestState.SAFE_STOP, event_type, reason)
        self._retry_state = retry_state
        return self._transition(QuestState.RETRY, event_type)

    def _advance_objective(self) -> bool:
        self.current_objective_index += 1
        if self.current_objective_index >= len(self.resource.objective_sequence):
            self.current_objective_index = len(self.resource.objective_sequence) - 1
            return self._transition(QuestState.COMPLETE, "objective_verified", "completed")
        self.retries_remaining = self._retry_limit()
        return self._transition(QuestState.NAVIGATING, "objective_verified")

    def handle(self, event: QuestEvent) -> bool:
        """Apply one monotonic event; return whether it caused a transition."""

        if self.state in {QuestState.COMPLETE, QuestState.SAFE_STOP}:
            return False
        if event.event_id in self._seen_event_ids or event.sequence <= self._last_sequence:
            return False

        self._seen_event_ids.add(event.event_id)
        self._last_sequence = event.sequence
        if event.objective_index != self.current_objective_index:
            return False

        if event.event_type in self._FAILURE_EVENTS:
            return self._handle_failure(event.event_type)
        if self.state is QuestState.DISCOVERING and event.event_type == "resource_validated":
            return self._transition(QuestState.NAVIGATING, event.event_type)
        if self.state is QuestState.NAVIGATING and event.event_type == "navigation_verified":
            return self._transition(QuestState.INTERACTING, event.event_type)
        if self.state is QuestState.INTERACTING and event.event_type == "interaction_verified":
            return self._transition(QuestState.VERIFYING, event.event_type)
        if self.state is QuestState.RETRY and event.event_type.startswith("retry_"):
            return self._transition(self._retry_state, event.event_type)
        if self.state is QuestState.VERIFYING and event.event_type == "objective_verified":
            evidence = event.evidence
            if (
                evidence is None
                or evidence.quest_id != self.resource.quest_id
                or evidence.status is not QuestPerceptionStatus.FOUND
            ):
                return False
            return self._advance_objective()
        return False