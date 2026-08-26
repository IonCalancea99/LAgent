"""Warlord combat policy for the pull, fight, and loot cycle."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from lagent.common import Action, PartyState, PerceptionResult
from lagent.agent.lifecycle import (
    DeathRecoveryController,
    InventoryReturnController,
    SessionCapController,
    detect_lifecycle_signal,
)


class WarlordCombatFSM:
    """Profile-driven Warlord FSM with one HSL action per decision tick."""

    SAFE_STATES = {"PAUSED", "DEAD", "RETURNING", "STOPPED"}

    def __init__(self, *, profile: Any, session_id: str | None = None, db: Any | None = None,
                 party_bus: Any | None = None, clock: Callable[[], float] = time.time,
                 session_cap_duration: float | None = None) -> None:
        self.profile = profile
        self.session_id = session_id
        self.db = db
        self.party_bus = party_bus
        self.clock = clock
        self.state = "IDLE"
        self.next_state: str | None = None
        self._loot_started_at: float | None = None
        self.recovery = DeathRecoveryController(profile=profile, session_id=session_id, db=db, clock=clock)
        self.inventory_return = InventoryReturnController(profile=profile, session_id=session_id, db=db)
        
        # Session cap controller (optional; if not provided, no cap enforcement)
        # Extract cap duration from parameter, profile dict, or use default
        cap_duration = session_cap_duration
        if cap_duration is None:
            if isinstance(profile, dict):
                cap_duration = profile.get("session_cap_duration", 14400.0)
            else:
                cap_duration = getattr(profile, "session_cap_duration", 14400.0)
        self.session_cap = SessionCapController(cap_duration, clock=clock, session_id=session_id, db=db)

    def _section(self, name: str) -> dict[str, Any]:
        bindings = self.profile.get("fsm_bindings", {}) if isinstance(self.profile, dict) else getattr(self.profile, "fsm_bindings", {})
        value = next((value for key, value in bindings.items() if str(key).upper() == name), {})
        return value if isinstance(value, dict) else {}

    def _skills(self) -> dict[str, str]:
        return self.profile.get("skill_key_bindings", {}) if isinstance(self.profile, dict) else getattr(self.profile, "skill_key_bindings", {})

    def _key(self, *names: str) -> str | None:
        skills = self._skills()
        for name in names:
            key = next((value for binding, value in skills.items() if str(binding).lower() == name), None)
            if key:
                return key
        return None

    @staticmethod
    def _detections(result: PerceptionResult, *names: str) -> list[Any]:
        aliases = {name.lower() for name in names}
        return [detection for detection in result.detections if detection.class_name.lower() in aliases]

    def _mob_detections(self, result: PerceptionResult) -> list[Any]:
        return self._detections(result, "mob", "enemy", "monster")

    def _in_melee_range(self, result: PerceptionResult) -> bool:
        if self._detections(result, "melee_range", "in_melee_range", "melee"):
            return True
        section = self._section("PULLING")
        center = section.get("frame_center", (500, 500))
        tolerance = float(section.get("melee_tolerance", 75.0))
        for detection in self._mob_detections(result):
            x1, y1, x2, y2 = detection.bbox_xyxy
            if abs((x1 + x2) / 2 - center[0]) <= tolerance and abs((y1 + y2) / 2 - center[1]) <= tolerance:
                return True
        return False

    def _log(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.db is not None and self.session_id is not None:
            self.db.append_event(self.session_id, "agent.warlord", event_type, {"state": self.state, **payload})

    def _publish(self, state: str) -> None:
        if self.party_bus is None:
            return
        snapshot = PartyState(fsm_state=state, hp_percent=100.0, mp_percent=100.0,
                              position=(0, 0), heartbeat_timestamp=self.clock())
        self.party_bus.publish_state(snapshot.model_dump(mode="json"))

    def _transition(self, state: str, reason: str) -> None:
        self.next_state = state
        self._log("state_transition", {"from": self.state, "to": state, "reason": reason, "timestamp": self.clock()})
        self._publish(state)

    def __call__(self, result: PerceptionResult, state_name: str) -> Action | None:
        self.state = state_name.upper()
        self.next_state = None

        # Check session cap at every tick
        if self.session_cap is not None and self.session_cap.expired():
            if self.state not in {"STOPPED"}:
                self._transition("STOPPED", "session_cap_reached")
                self.state = "STOPPED"
            return None

        # Check for lifecycle signals (death, inventory-full, etc.)
        signal = detect_lifecycle_signal(result, clock=self.clock)
        if signal and signal.name == "death_detected":
            # Try to start recovery if not already in DEAD state
            if self.recovery.begin(self.state):
                # Recovery started; publish DEAD state and transition
                self._transition("DEAD", "death_detected")
                self.state = "DEAD"  # Explicitly set state
                # Dispatch first recovery action immediately
                action = self.recovery.next_action()
                if action is not None:
                    return action
                # If no recovery actions, fall through to complete recovery
        elif signal and signal.name == "inventory_full":
            # Try to start inventory return if not already in RETURNING state
            if self.inventory_return.begin():
                # Return started; publish RETURNING state and transition
                self._transition("RETURNING", "inventory_full_detected")
                self.state = "RETURNING"  # Explicitly set state
                # Dispatch first return action immediately
                action = self.inventory_return.next_action()
                if action is not None:
                    return action
                # If no return actions, fall through to complete return

        # If in DEAD state, dispatch recovery actions
        if self.state == "DEAD":
            action = self.recovery.next_action()
            if action is not None:
                return action
            # Recovery sequence complete; return to pre-death state
            resumed_state = self.recovery.complete()
            self._transition(resumed_state, "recovery_complete")
            self.state = resumed_state
            return None

        # If in RETURNING state, dispatch return/disposition actions
        return_completed = False
        if self.state == "RETURNING":
            if self.inventory_return.state != "RETURNING":
                return None
            action = self.inventory_return.next_action()
            if action is not None:
                return action
            # Return sequence complete; return to idle
            self.inventory_return.complete()
            self._transition("IDLE", "inventory_return_complete")
            self.state = "IDLE"
            return_completed = True

        # Suppress combat actions in lifecycle interruption states
        if self.state in self.SAFE_STATES:
            return None

        if self.state == "IDLE":
            self._loot_started_at = None
            if not self._mob_detections(result):
                if return_completed:
                    return None
                return Action(action_type="wait", duration=0.0)
            self._transition("PULLING", "mob_detected")
            self._log("combat_decision", {"decision": "pull"})
            return Action(action_type="key_press", key=self._key("pull", "assist", "attack"))

        if self.state == "PULLING":
            if self._in_melee_range(result):
                self._transition("FIGHTING", "melee_range_reached")
                self._log("combat_decision", {"decision": "aoe"})
                return Action(action_type="key_press", key=self._key("aoe", "attack"))
            self._log("combat_decision", {"decision": "pull"})
            return Action(action_type="key_press", key=self._key("pull", "assist", "attack"))

        if self.state == "FIGHTING":
            if not self._mob_detections(result):
                self._transition("LOOTING", "mob_area_clear")
                self._loot_started_at = self.clock()
                self._log("combat_decision", {"decision": "loot"})
                return Action(action_type="key_press", key=self._key("loot"))
            self._log("combat_decision", {"decision": "aoe"})
            return Action(action_type="key_press", key=self._key("aoe", "attack"))

        if self.state == "LOOTING":
            timeout = float(self._section("LOOTING").get("loot_timeout", 5.0))
            if self._loot_started_at is None:
                self._loot_started_at = self.clock()
            elapsed = self.clock() - self._loot_started_at
            if not self._detections(result, "loot") or elapsed >= timeout:
                self._transition("IDLE", "loot_timeout" if elapsed >= timeout else "loot_window_closed")
                self._log("combat_decision", {"decision": "resume_idle", "elapsed": elapsed})
                return Action(action_type="wait", duration=0.0)
            return Action(action_type="key_press", key=self._key("loot"))

        raise ValueError(f"Invalid Warlord FSM state: {state_name}")


__all__ = ["WarlordCombatFSM"]