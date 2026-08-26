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
            retry_at = time.time() + self.retry_interval
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


class ProphetBuffPolicy:
    """Timer-driven PP buff policy with a safety-gated retry path."""

    def __init__(
        self,
        profile: AgentProfile,
        state_provider: Callable[[PerceptionResult], GameState],
        *,
        session_db: Any | None = None,
        session_id: str | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.profile = profile
        self.state_provider = state_provider
        self.session_db = session_db
        self.session_id = session_id
        self.clock = clock
        self.safety_check = PPBuffSafetyCheck(
            aggro_risk_radius=profile.aggro_risk_radius,
            retry_interval=profile.retry_interval,
        )
        self._next_buff_at = self.clock()

    def __call__(self, perception: PerceptionResult, state_name: str) -> Action:
        del state_name
        now = self.clock()
        if now < self._next_buff_at:
            return Action(action_type="wait", duration=min(self._next_buff_at - now, 0.1))

        outcome = self.safety_check.evaluate(
            self.state_provider(perception),
            perception,
            session_db=self.session_db,
            session_id=self.session_id,
        )
        if not outcome["safe"]:
            self._next_buff_at = outcome["retry_at"]
            return Action(action_type="wait", duration=min(self.profile.retry_interval, 0.1))

        buff_key = self.profile.skill_key_bindings.get("buff")
        if not buff_key:
            return Action(action_type="wait", duration=0.0)
        duration = min(self.profile.buff_timer_durations.values(), default=self.profile.retry_interval)
        self._next_buff_at = now + duration
        return Action(action_type="key_press", key=buff_key)


__all__ = ["PPBuffSafetyCheck", "ProphetBuffPolicy"]
