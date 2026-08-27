"""SQLite event-backed quest checkpoints and recovery decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from lagent.common import QuestCheckpoint, QuestPerceptionEvidence, QuestPerceptionStatus, QuestResource


class QuestRecoveryState(str, Enum):
    RESUME = "resume"
    COMPLETE = "complete"
    SAFE_STOP = "safe_stop"


@dataclass(frozen=True)
class QuestRecoveryDecision:
    state: QuestRecoveryState
    reason: str
    next_objective_index: int | None
    checkpoint: QuestCheckpoint | None


class QuestCheckpointManager:
    """Persist and reconstruct verified quest boundaries from session events."""

    def __init__(self, db: Any, session_id: str, resource: QuestResource) -> None:
        self.db = db
        self.session_id = session_id
        self.resource = resource

    def checkpoint_objective(
        self,
        objective_index: int,
        *,
        verification_source: str,
        evidence: QuestPerceptionEvidence,
    ) -> QuestCheckpoint:
        if (
            not 0 <= objective_index < len(self.resource.objective_sequence)
            or not verification_source
            or verification_source == "timer"
            or evidence.quest_id != self.resource.quest_id
            or evidence.status is not QuestPerceptionStatus.FOUND
        ):
            raise ValueError("checkpoint requires a verified objective boundary")
        objective = self.resource.objective_sequence[objective_index]
        checkpoint = QuestCheckpoint(
            name=f"objective:{objective.id}",
            required_state="verified",
            session_id=self.session_id,
            quest_id=self.resource.quest_id,
            objective_index=objective_index,
            status="verified",
            verification_source=verification_source,
            evidence=evidence.model_dump(mode="json"),
        )
        payload = checkpoint.model_dump(mode="json")
        payload.update(
            {
                "quest_name": self.resource.quest_name,
                "objective_id": objective.id,
                "objective_name": objective.name,
                "total_objectives": len(self.resource.objective_sequence),
            }
        )
        self.db.append_event(
            self.session_id,
            "agent.quest",
            "quest_checkpoint",
            payload,
        )
        return checkpoint

    def latest_checkpoint(self) -> QuestCheckpoint | None:
        events = self.db.get_events_by_type(self.session_id, "quest_checkpoint")
        for event in reversed(events):
            try:
                checkpoint = QuestCheckpoint.model_validate(event["payload"])
            except (KeyError, ValueError, TypeError):
                continue
            evidence_status = checkpoint.evidence.get("status")
            if (
                checkpoint.session_id == self.session_id
                and checkpoint.quest_id == self.resource.quest_id
                and checkpoint.status == "verified"
                and checkpoint.verification_source
                and evidence_status == QuestPerceptionStatus.FOUND.value
                and 0 <= checkpoint.objective_index < len(self.resource.objective_sequence)
            ):
                return checkpoint
        return None

    def restore(self, interruption_reason: str) -> QuestRecoveryDecision:
        checkpoint = self.latest_checkpoint()
        if checkpoint is None:
            decision = QuestRecoveryDecision(
                QuestRecoveryState.SAFE_STOP,
                "operator_intervention_required",
                None,
                None,
            )
        else:
            next_index = checkpoint.objective_index + 1
            state = QuestRecoveryState.COMPLETE if next_index >= len(self.resource.objective_sequence) else QuestRecoveryState.RESUME
            decision = QuestRecoveryDecision(
                state,
                interruption_reason,
                None if state is QuestRecoveryState.COMPLETE else next_index,
                checkpoint,
            )
        self.db.append_event(
            self.session_id,
            "agent.quest",
            "quest_recovery",
            {
                "interruption_reason": interruption_reason,
                "state": decision.state.value,
                "reason": decision.reason,
                "next_objective_index": decision.next_objective_index,
                "checkpoint_objective_index": checkpoint.objective_index if checkpoint else None,
            },
        )
        return decision

    def log_failure(self, reason: str, *, objective_index: int, retry_count: int) -> None:
        checkpoint = self.latest_checkpoint()
        self.db.append_event(
            self.session_id,
            "agent.quest",
            "quest_failure",
            {
                "quest_id": self.resource.quest_id,
                "quest_name": self.resource.quest_name,
                "objective_index": objective_index,
                "total_objectives": len(self.resource.objective_sequence),
                "retry_count": retry_count,
                "reason": reason,
                "last_verified_objective_index": checkpoint.objective_index if checkpoint else None,
                "last_verified_evidence": checkpoint.evidence if checkpoint else None,
            },
        )