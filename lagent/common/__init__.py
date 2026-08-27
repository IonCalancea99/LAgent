"""
lagent.common — canonical shared import root.

The six types defined here are the sole source of truth across all processes:
- GameState, PartyState, PerceptionResult, Detection, Action, AgentProfile

AD-12: lagent.common is the only package initializer that exports these shared types.
No agent, GPU server, orchestrator, UI, HSL, or training module re-exports or
locally redefines them.
"""

from lagent.common.types import (
    GameState,
    PartyState,
    PerceptionResult,
    Detection,
    Action,
    AgentProfile,
    DialogueChoice,
    ObjectiveStep,
    QuestCheckpoint,
    QuestPerceptionEvidence,
    QuestPerceptionStatus,
    QuestResource,
    QuestResourceValidationError,
)

__all__ = [
    "GameState",
    "PartyState",
    "PerceptionResult",
    "Detection",
    "Action",
    "AgentProfile",
    "DialogueChoice",
    "ObjectiveStep",
    "QuestCheckpoint",
    "QuestPerceptionEvidence",
    "QuestPerceptionStatus",
    "QuestResource",
    "QuestResourceValidationError",
]
