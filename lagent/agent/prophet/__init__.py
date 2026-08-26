"""PP Agent behavior policy and buff safety gate."""

from __future__ import annotations

import math
import logging
import time
from collections.abc import Callable
from typing import Any

from lagent.common import Action, AgentProfile, GameState, PerceptionResult

logger = logging.getLogger(__name__)


class PPBuffSafetyCheck:
    """Evaluate whether a timed PP buff cast is safe to execute.

    The safety gate is intentionally non-destructive: it reads current-frame
    perception data and the peer party state but never mutates GameState.
    """

    def __init__(
        self,
        *,
        aggro_risk_radius: float = 150.0,
        retry_interval: float = 1.0,
    ) -> None:
        self.aggro_risk_radius = float(aggro_risk_radius)
        self.retry_interval = float(retry_interval)
        if not math.isfinite(self.aggro_risk_radius) or self.aggro_risk_radius < 0:
            raise ValueError("aggro_risk_radius must be a finite non-negative number")
        if not math.isfinite(self.retry_interval) or self.retry_interval < 0:
            raise ValueError("retry_interval must be a finite non-negative number")

    def _bbox_center(self, detection: Any) -> tuple[float, float]:
        x1, y1, x2, y2 = detection.bbox_xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def evaluate(
        self,
        state: GameState,
        perception: PerceptionResult,
        *,
        session_db: Any | None = None,
        session_id: str | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        """Return a deterministic safety outcome for the current frame and peer state."""
        reasons: list[str] = []

        peer_state = getattr(state, "peer_party_state", None)
        wl_pulling = bool(peer_state is not None and getattr(peer_state, "fsm_state", None) == "PULLING")
        if wl_pulling:
            reasons.append("wl_pulling")

        mob_within_radius = False
        if getattr(state, "character_position", None) is not None:
            character_x, character_y = state.character_position
            for detection in getattr(perception, "detections", []):
                center_x, center_y = self._bbox_center(detection)
                distance = math.hypot(center_x - character_x, center_y - character_y)
                if distance <= self.aggro_risk_radius:
                    mob_within_radius = True
                    reasons.append(f"aggro_risk_radius:{detection.class_name}")
                    break

        safe = (not wl_pulling) and (not mob_within_radius)
        retry_at: float | None = None
        event_logged: bool | None = None
        if not safe:
            current_time = now if now is not None else time.time()
            retry_at = current_time + self.retry_interval
            if session_db is not None and session_id is not None:
                payload = {
                    "agent_id": "prophet",
                    "session_id": session_id,
                    "reason": "buff_cast_deferred",
                    "safe": False,
                    "mob_within_radius": mob_within_radius,
                    "wl_pulling": wl_pulling,
                    "next_eligible_at": retry_at,
                    "aggro_risk_radius": self.aggro_risk_radius,
                    "failed_checks": reasons,
                    "wl_fsm_state": getattr(peer_state, "fsm_state", None),
                }
                try:
                    session_db.append_event(session_id, "agent.prophet", "buff_cast_deferred", payload)
                    event_logged = True
                except Exception:
                    event_logged = False
                    logger.exception("failed to append buff_cast_deferred event for %s", session_id)

        return {
            "safe": safe,
            "reasons": reasons,
            "mob_within_radius": mob_within_radius,
            "wl_pulling": wl_pulling,
            "retry_at": retry_at,
            "event_logged": event_logged,
            "aggro_risk_radius": self.aggro_risk_radius,
            "retry_interval": self.retry_interval,
        }


class BuffTimer:
    """Independent timer for a single buff."""

    def __init__(self, name: str, duration: float, *, clock: Callable[[], float] = time.time) -> None:
        self.name = name
        self.duration = float(duration)
        self.clock = clock
        self.reset_at = self.clock()

    def is_expired(self, now: float | None = None) -> bool:
        now = now if now is not None else self.clock()
        return (now - self.reset_at) >= self.duration

    def reset(self, now: float | None = None) -> None:
        self.reset_at = now if now is not None else self.clock()


class ProphetBuffPolicy:
    """Timer-driven PP buff cycle with safety-gated retry path for deferred casts."""

    SAFE_STATES = {"PAUSED", "DEAD", "RETURNING", "STOPPED"}

    def __init__(
        self,
        profile: Any = None,
        game_state_provider: Callable[[PerceptionResult], GameState] | None = None,
        *,
        session_id: str | None = None,
        db: Any | None = None,
        party_bus: Any | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.profile = profile
        self.game_state_provider = game_state_provider
        self.session_id = session_id
        self.db = db
        self.party_bus = party_bus
        self.clock = clock
        self.state = "IDLE"
        self.next_state: str | None = None

        # Load buff timers and safety check parameters from profile
        buff_durations = self._buff_durations()
        self.timers = {name: BuffTimer(name, duration, clock=clock) for name, duration in buff_durations.items()}
        aggro_risk_radius = float(getattr(profile, "aggro_risk_radius", 150.0) if hasattr(profile, "aggro_risk_radius") else profile.get("aggro_risk_radius", 150.0))
        retry_interval = float(getattr(profile, "retry_interval", 1.0) if hasattr(profile, "retry_interval") else profile.get("retry_interval", 1.0))
        self.safety_check = PPBuffSafetyCheck(aggro_risk_radius=aggro_risk_radius, retry_interval=retry_interval)

        # Track pending buff and deferred retry timestamps
        self._pending_buff: str | None = None
        self._retry_at: float | None = None

    def _buff_durations(self) -> dict[str, float]:
        if isinstance(self.profile, dict):
            return dict(self.profile.get("buff_timer_durations", {}))
        return dict(getattr(self.profile, "buff_timer_durations", {}))

    def _skill_bindings(self) -> dict[str, str]:
        if isinstance(self.profile, dict):
            return dict(self.profile.get("skill_key_bindings", {}))
        return dict(getattr(self.profile, "skill_key_bindings", {}))

    def _key_for_buff(self, buff_name: str) -> str | None:
        bindings = self._skill_bindings()
        # Try exact match first, then fallback to generic "buff" key
        return bindings.get(buff_name) or bindings.get("buff")

    def _log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.db is not None and self.session_id is not None:
            self.db.append_event(self.session_id, "agent.prophet", event_type, {"state": self.state, **payload})

    def _publish(self, state: str) -> None:
        if self.party_bus is None:
            return
        from lagent.common import PartyState
        snapshot = PartyState(
            fsm_state=state,
            hp_percent=100.0,
            mp_percent=100.0,
            position=(0, 0),
            heartbeat_timestamp=self.clock(),
        )
        self.party_bus.publish_state(snapshot.model_dump(mode="json"))

    def __call__(self, perception: PerceptionResult, state_name: str) -> Action | None:
        """Evaluate pending buffs, apply safety checks, and dispatch cast or retry actions."""
        self.state = state_name.upper()
        self.next_state = None

        # Suppress all actions in lifecycle interruption states
        if self.state in self.SAFE_STATES:
            self._pending_buff = None
            self._retry_at = None
            return None

        now = self.clock()

        # Re-evaluate pending buff if retry time has passed
        if self._pending_buff is not None and self._retry_at is not None and now < self._retry_at:
            self._log_event("buff_retry_waiting", {
                "buff_name": self._pending_buff,
                "retry_at": self._retry_at,
                "timestamp": now,
            })
            return Action(action_type="wait", duration=0.1)

        # Check for newly expired timers if no buff is currently pending
        if self._pending_buff is None:
            for buff_name, timer in self.timers.items():
                if timer.is_expired(now):
                    self._pending_buff = buff_name
                    self._retry_at = None
                    self.state = "BUFFING"
                    self._publish("BUFFING")
                    self._log_event("buff_timer_expired", {"buff_name": buff_name, "timestamp": now})
                    # Return early after setting pending buff; will attempt cast on next call
                    return Action(action_type="wait", duration=0.1)

        # If no pending buff, return idle action
        if self._pending_buff is None:
            return Action(action_type="wait", duration=0.1)

        # Attempt to cast pending buff after safety check
        buff_name = self._pending_buff
        game_state = self.game_state_provider(perception) if self.game_state_provider else None
        outcome = self.safety_check.evaluate(
            game_state or GameState(
                hp_percent=100.0,
                mp_percent=100.0,
                active_buffs=[],
                character_position=(0, 0),
                ui_mode="combat",
            ),
            perception,
            session_db=self.db,
            session_id=self.session_id,
            now=now,
        )

        self._log_event("buff_safety_check", {
            "buff_name": buff_name,
            "safe": outcome["safe"],
            "reasons": outcome["reasons"],
            "timestamp": now,
        })

        if not outcome["safe"]:
            # Defer the cast and schedule retry
            self._retry_at = outcome.get("retry_at", now + self.safety_check.retry_interval)
            self._log_event("buff_cast_deferred", {
                "buff_name": buff_name,
                "reasons": outcome["reasons"],
                "retry_at": self._retry_at,
                "timestamp": now,
            })
            return Action(action_type="wait", duration=0.1)

        # Safety check passed; cast the buff
        buff_key = self._key_for_buff(buff_name)
        if not buff_key:
            self._log_event("buff_key_missing", {"buff_name": buff_name, "timestamp": now})
            self._pending_buff = None
            self._retry_at = None
            return Action(action_type="wait", duration=0.1)

        # Reset timer and dispatch cast action
        self.timers[buff_name].reset(now)
        self.next_state = "IDLE"
        self.state = "IDLE"
        self._publish("IDLE")
        self._log_event("buff_cast_attempted", {
            "buff_name": buff_name,
            "key": buff_key,
            "timestamp": now,
        })
        self._pending_buff = None
        self._retry_at = None
        return Action(action_type="key_press", key=buff_key)


__all__ = ["PPBuffSafetyCheck", "BuffTimer", "ProphetBuffPolicy", "ProphetBuffCycleFSM"]

# Backward compatibility alias
ProphetBuffCycleFSM = ProphetBuffPolicy
