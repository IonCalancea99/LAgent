"""Deterministic lifecycle controllers shared by combat policies."""

from __future__ import annotations

import time
from dataclasses import dataclass
from collections.abc import Callable, Iterable
from typing import Any

from lagent.common import Action, PerceptionResult


@dataclass(frozen=True)
class LifecycleSignal:
    name: str
    timestamp: float
    payload: dict[str, Any]


def detect_lifecycle_signal(result: PerceptionResult, *, clock: Callable[[], float] = time.time) -> LifecycleSignal | None:
    """Normalize explicit detection/OCR markers into one lifecycle signal."""
    names = {detection.class_name.lower() for detection in result.detections}
    if names & {"death", "dead", "death_screen"} or result.ocr_values.get("death"):
        return LifecycleSignal("death_detected", clock(), {})
    if names & {"inventory_full", "full_inventory"} or result.ocr_values.get("inventory_full"):
        return LifecycleSignal("inventory_full", clock(), {})
    return None


class DeathRecoveryController:
    """Idempotent profile-driven respawn and recovery sequence."""

    def __init__(self, *, profile: Any, session_id: str | None = None, db: Any | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.profile = profile
        self.session_id = session_id
        self.db = db
        self.clock = clock
        self.state = "IDLE"
        self.pre_death_state = "IDLE"
        self.started_at: float | None = None
        self._actions: list[Action] = []
        self._action_index = 0

    def _config(self) -> dict[str, Any]:
        if isinstance(self.profile, dict):
            return self.profile.get("recovery", {})
        return getattr(self.profile, "recovery", {}) or {}

    def _log(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.db is not None and self.session_id is not None:
            self.db.append_event(self.session_id, "lifecycle", event_type, payload)

    def begin(self, prior_state: str) -> bool:
        if self.state == "DEAD":
            return False
        self.pre_death_state = prior_state if prior_state in {"IDLE", "PULLING", "FIGHTING", "LOOTING", "BUFFING"} else "IDLE"
        self.state = "DEAD"
        self.started_at = self.clock()
        self._action_index = 0
        actions: Iterable[dict[str, Any]] = self._config().get("actions", [{"action_type": "key_press", "key": "enter"}])
        self._actions = [Action.model_validate(action) for action in actions]
        self._log("death_detected", {"pre_death_state": self.pre_death_state, "timestamp": self.started_at})
        return True

    def next_action(self) -> Action | None:
        if self.state != "DEAD" or self._action_index >= len(self._actions):
            return None
        action = self._actions[self._action_index]
        self._action_index += 1
        self._log("recovery_action", {"action": action.model_dump(mode="json")})
        return action

    def complete(self) -> str:
        if self.state != "DEAD":
            return self.state
        start_time = self.started_at if self.started_at is not None else self.clock()
        elapsed = self.clock() - start_time
        self.state = self.pre_death_state
        self._log("recovery_complete", {"elapsed_seconds": elapsed, "within_budget": elapsed <= 60.0, "resumed_state": self.state})
        return self.state


class InventoryReturnController:
    """Idempotent town-return and explicitly authorized loot disposition."""

    def __init__(self, *, profile: Any, session_id: str | None = None, db: Any | None = None) -> None:
        self.profile = profile
        self.session_id = session_id
        self.db = db
        self.state = "IDLE"
        self._actions: list[Action] = []

    def _config(self) -> dict[str, Any]:
        if isinstance(self.profile, dict):
            return self.profile.get("inventory", {})
        return getattr(self.profile, "inventory", {}) or {}

    def _log(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.db is not None and self.session_id is not None:
            self.db.append_event(self.session_id, "lifecycle", event_type, payload)

    def begin(self) -> bool:
        if self.state == "RETURNING":
            return False
        self.state = "RETURNING"
        self._actions = [Action.model_validate(action) for action in self._config().get("return_actions", [])]
        self._log("inventory_return_started", {})
        return True

    def next_action(self) -> Action | None:
        if self.state != "RETURNING" or not self._actions:
            return None
        return self._actions.pop(0)

    def dispose_loot(self, item_name: str) -> str:
        config = self._config()
        if item_name in config.get("deposit", []):
            disposition = "deposit"
        elif item_name in config.get("drop", []):
            disposition = "drop"
        else:
            disposition = "retain"
            self._log("loot_disposition_blocked", {"item": item_name, "reason": "no_authorizing_rule"})
            return disposition
        self._log("loot_disposition", {"item": item_name, "disposition": disposition})
        return disposition

    def complete(self) -> None:
        self.state = "IDLE"
        self._log("inventory_return_completed", {})


class SessionCapController:
    """Monotonic, idempotent session-cap gate."""

    def __init__(self, duration: float, *, clock: Callable[[], float] = time.monotonic,
                 session_id: str | None = None, db: Any | None = None) -> None:
        if duration < 0:
            raise ValueError("session cap duration must be non-negative")
        self.duration = duration
        self.clock = clock
        self.session_id = session_id
        self.db = db
        self.started_at = clock()
        self.reached = False

    def expired(self) -> bool:
        if self.reached:
            return True
        if self.clock() - self.started_at < self.duration:
            return False
        self.reached = True
        if self.db is not None and self.session_id is not None:
            self.db.append_event(self.session_id, "lifecycle", "session_cap_reached", {"elapsed_seconds": self.clock() - self.started_at})
        return True


class QuestRecoveryController:
    """Apply existing lifecycle interruption semantics to verified quest checkpoints."""

    def __init__(self, checkpoint_manager: Any) -> None:
        self.checkpoint_manager = checkpoint_manager

    def recover(self, interruption_reason: str, *, prior_runtime_state: str | None = None) -> Any:
        del prior_runtime_state
        return self.checkpoint_manager.restore(interruption_reason)


__all__ = [
    "DeathRecoveryController",
    "InventoryReturnController",
    "LifecycleSignal",
    "QuestRecoveryController",
    "SessionCapController",
    "detect_lifecycle_signal",
]