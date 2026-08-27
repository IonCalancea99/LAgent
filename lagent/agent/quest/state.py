"""Quest FSM state and event contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lagent.common import QuestPerceptionEvidence


class QuestState(str, Enum):
    DISCOVERING = "discovering"
    NAVIGATING = "navigating"
    INTERACTING = "interacting"
    VERIFYING = "verifying"
    RETRY = "retry"
    PAUSED = "paused"
    COMPLETE = "complete"
    SAFE_STOP = "safe_stop"


@dataclass(frozen=True)
class QuestEvent:
    event_id: str
    sequence: int
    event_type: str
    objective_index: int
    evidence: QuestPerceptionEvidence | None = None