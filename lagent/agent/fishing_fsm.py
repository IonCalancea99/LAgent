"""Fishing Mode FSM with temporal Pump/Reel fight control."""

from __future__ import annotations

from collections import deque
import logging
import math
import time
from typing import Any, Callable, Optional

from lagent.common import Action, PerceptionResult

logger = logging.getLogger(__name__)


class FishingFSM:
    """
    Finite State Machine for Fishing Mode.
    
    States:
    - IDLE: Ready to cast
    - CASTING: Rod cast in progress
    - WAITING: Waiting for bite event
    - STOPPED: Halted (safe state)
    
    Transitions:
    - IDLE → CASTING: Cast rod via key press
    - CASTING → WAITING: After cast completes
    - WAITING → IDLE: On timeout or bite detection
    - Any → STOPPED: On halt signal
    """

    def __init__(
        self,
        cast_key: Optional[str] = None,
        reel_key: Optional[str] = None,
        wait_timeout: Optional[float] = None,
        tension_class: Optional[str] = None,
        tension_confidence_threshold: Optional[float] = None,
        profile: Optional[Any] = None,
        session_id: Optional[str] = None,
        db: Optional[Any] = None,
        clock: Callable[[], float] = time.monotonic,
        pump_key: Optional[str] = None,
        observation_window: Optional[int] = None,
        trend_tolerance: Optional[float] = None,
        action_cooldown: Optional[float] = None,
        disappearance_count: Optional[int] = None,
        fight_timeout: Optional[float] = None,
    ):
        """
        Initialize Fishing FSM.
        
        Args:
            cast_key: Key to press for casting rod
            wait_timeout: Timeout in seconds for waiting for bite
            profile: Agent profile with skill timing and bindings
            session_id: Session ID for logging
            db: Sessions database for event logging
        """
        self.profile = profile
        self.session_id = session_id
        self.db = db
        self.clock = clock

        bindings = {}
        if isinstance(profile, dict):
            bindings = profile.get("fsm_bindings", {})
        elif profile is not None:
            bindings = getattr(profile, "fsm_bindings", {})
        idle_binding = bindings.get("IDLE", {})
        waiting_binding = bindings.get("WAITING", {})
        reeling_binding = bindings.get("REELING", {})
        self.cast_key = cast_key or idle_binding.get("cast_key", "2")
        self.reel_key = reel_key or waiting_binding.get("reel_key") or reeling_binding.get("reel_key", "3")
        self.pump_key = pump_key or waiting_binding.get("pump_key", "4")
        self.wait_timeout = wait_timeout if wait_timeout is not None else waiting_binding.get("wait_timeout", 10.0)
        self.tension_class = (tension_class or waiting_binding.get("tension_class", "tension_indicator")).lower()
        self.tension_confidence_threshold = (
            tension_confidence_threshold
            if tension_confidence_threshold is not None
            else waiting_binding.get("tension_confidence_threshold", 0.80)
        )
        self.observation_window = self._positive_int(
            "observation_window",
            observation_window if observation_window is not None else waiting_binding.get("observation_window", 3),
            minimum=2,
        )
        self.trend_tolerance = self._fraction(
            "trend_tolerance",
            trend_tolerance if trend_tolerance is not None else waiting_binding.get("trend_tolerance", 0.03),
        )
        self.action_cooldown = self._non_negative_float(
            "action_cooldown",
            action_cooldown if action_cooldown is not None else waiting_binding.get("action_cooldown", 0.5),
        )
        self.disappearance_count = self._positive_int(
            "disappearance_count",
            disappearance_count if disappearance_count is not None else waiting_binding.get("disappearance_count", 3),
        )
        self.fight_timeout = self._positive_float(
            "fight_timeout",
            fight_timeout if fight_timeout is not None else waiting_binding.get("fight_timeout", 30.0),
        )
        
        # FSM state tracking
        self.state = "IDLE"
        self.wait_started_at: Optional[float] = None
        self.halted = False
        self.paused = False
        self._paused_state: Optional[str] = None
        self.next_state: Optional[str] = None
        self._width_history: deque[float] = deque(maxlen=self.observation_window)
        self._maximum_width = 0.0
        self._gauge_seen = False
        self._absent_frames = 0
        self._fight_started_at: Optional[float] = None
        self._last_action_at: Optional[float] = None

    @staticmethod
    def _positive_int(name: str, value: Any, *, minimum: int = 1) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
        return value

    @staticmethod
    def _non_negative_float(name: str, value: Any) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"{name} must be a non-negative number")
        return float(value)

    @staticmethod
    def _positive_float(name: str, value: Any) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be a positive number")
        return float(value)

    @staticmethod
    def _fraction(name: str, value: Any) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value < 1
        ):
            raise ValueError(f"{name} must be a number in [0, 1)")
        return float(value)

    @property
    def observed_widths(self) -> tuple[float, ...]:
        return tuple(self._width_history)

    def _reset_fight(self) -> None:
        self._width_history.clear()
        self._maximum_width = 0.0
        self._gauge_seen = False
        self._absent_frames = 0
        self._fight_started_at = None
        self._last_action_at = None

    def _classify_trend(self) -> tuple[str, list[float]]:
        normalized = [width / self._maximum_width for width in self._width_history]
        deltas = [current - previous for previous, current in zip(normalized, normalized[1:])]
        total_delta = normalized[-1] - normalized[0]
        if max(normalized) - min(normalized) <= self.trend_tolerance:
            return "steady", normalized
        if total_delta > self.trend_tolerance and all(delta >= -self.trend_tolerance for delta in deltas):
            return "rising", normalized
        if total_delta < -self.trend_tolerance and all(delta <= self.trend_tolerance for delta in deltas):
            return "falling", normalized
        return "mixed", normalized

    def _wait_action(self) -> Action:
        self.next_state = "WAITING"
        return Action(action_type="wait", duration=0.1)

    def _finish_fight(self, event_type: str, payload: dict[str, Any]) -> Action:
        self._log_event(event_type, payload)
        self.wait_started_at = None
        self._reset_fight()
        self.next_state = "IDLE"
        return Action(action_type="wait", duration=0.0)

    def _tension_detection(self, result: PerceptionResult) -> Any | None:
        aliases = {self.tension_class, "tension", "tension_indicator"}
        return max(
            (
                detection
                for detection in result.detections
                if detection.class_name.lower() in aliases
                and detection.bbox_xyxy[2] > detection.bbox_xyxy[0]
            ),
            key=lambda detection: detection.confidence,
            default=None,
        )

    def _has_tension_evidence(self, result: PerceptionResult) -> bool:
        aliases = {self.tension_class, "tension", "tension_indicator"}
        return any(detection.class_name.lower() in aliases for detection in result.detections)

    def _log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Log FSM event to sessions database."""
        if self.db is not None and self.session_id is not None:
            try:
                self.db.append_event(
                    self.session_id,
                    "fsm",
                    event_type,
                    {**payload, "state": self.state},
                )
            except (IOError, OSError, PermissionError) as e:
                logger.critical("Unrecoverable logging error (database corruption or permission denied): %s", e)
                raise
            except Exception as e:
                logger.warning("Transient logging error (continuing): %s", e)

    def handle_halt(self) -> None:
        """
        AC-3: Handle halt signal. Abandon current state safely.
        
        Transitions to STOPPED state and produces no further input.
        Idempotent: safe to call multiple times.
        """
        if self.halted:
            logger.debug("Fishing FSM halt called while already halted; ignoring duplicate")
            return
        logger.info("Fishing FSM halt signal received at state %s", self.state)
        self._log_event("halt", {"reason": "user_interrupt"})
        self.wait_started_at = None
        self._reset_fight()
        self.halted = True
        self.state = "STOPPED"

    def pause_for_session_halt(self, missed_agent_id: str, missed_count: int) -> None:
        if self.paused:
            return
        self._paused_state = self.state
        self.paused = True
        self.halted = True
        self.wait_started_at = None
        self._reset_fight()
        self.state = "PAUSED"
        self._log_event(
            "session_halt",
            {"reason": "heartbeat_missed", "missed_agent_id": missed_agent_id, "missed_count": missed_count},
        )

    def resume_session(self, reason: str = "operator_resume") -> None:
        if not self.paused or reason != "operator_resume":
            return
        self.state = self._paused_state or "IDLE"
        self._paused_state = None
        self.paused = False
        self.halted = False
        self._log_event("session_resume", {"reason": reason})

    def __call__(self, result: PerceptionResult, state_name: str) -> Action | None:
        """
        FSM state handler: Process perception and return action.
        
        Args:
            result: PerceptionResult from GPU inference
            state_name: Current FSM state name
            
        Returns:
            Action to dispatch via HSL, or None
        """
        # Detect if we're entering WAITING state fresh (from a different state)
        entering_waiting_fresh = (state_name == "WAITING" and self.state != "WAITING")
        self.next_state = None
        self.state = state_name
        
        # AC-3: If halted, produce no further input
        if self.paused or self.halted or state_name in ("STOPPED", "PAUSED"):
            logger.debug("FSM in STOPPED state; no action produced")
            return None

        if state_name == "IDLE":
            # AC-1: IDLE → CASTING: Execute rod cast key sequence
            self.wait_started_at = None
            self._reset_fight()
            logger.debug("Fishing FSM: IDLE → casting rod (key=%s)", self.cast_key)
            self._log_event("transition", {"from": "IDLE", "to": "CASTING", "action": "cast_key"})
            return Action(action_type="key_press", key=self.cast_key)

        elif state_name == "CASTING":
            # CASTING → WAITING: Wait briefly for cast animation to complete
            # Then external loop handler transitions to WAITING
            logger.debug("Fishing FSM: CASTING → wait for cast completion")
            return Action(action_type="wait", duration=0.5)

        elif state_name == "WAITING":
            now = self.clock()
            if entering_waiting_fresh or self.wait_started_at is None:
                self.wait_started_at = now
                logger.debug("Fishing FSM: WAITING started at %s", self.wait_started_at)

            wait_elapsed = now - self.wait_started_at
            if not self._gauge_seen and wait_elapsed >= self.wait_timeout:
                tension = self._tension_detection(result)
                logger.info("Fishing FSM: WAITING timeout (waited %.2f seconds) → IDLE", wait_elapsed)
                self._log_event(
                    "missed_tension",
                    {
                        "confidence": tension.confidence if tension is not None else 0.0,
                        "tension_window": wait_elapsed,
                        "timeout": True,
                    },
                )
                self._log_event("timeout", {"wait_timeout": self.wait_timeout, "elapsed": wait_elapsed})
                return self._finish_fight("wait_complete", {"reason": "bite_timeout"})

            tension = self._tension_detection(result)
            if tension is not None and tension.confidence >= self.tension_confidence_threshold:
                width = float(max(0, tension.bbox_xyxy[2] - tension.bbox_xyxy[0]))
                if width > 0:
                    if not self._gauge_seen:
                        self._gauge_seen = True
                        self._fight_started_at = now
                    self._absent_frames = 0
                    self._maximum_width = max(self._maximum_width, width)
                    self._width_history.append(width)

                    fight_started_at = self._fight_started_at if self._fight_started_at is not None else now
                    fight_elapsed = now - fight_started_at
                    if fight_elapsed >= self.fight_timeout:
                        return self._finish_fight(
                            "timeout",
                            {"reason": "fight_timeout", "fight_timeout": self.fight_timeout, "elapsed": fight_elapsed},
                        )

                    if len(self._width_history) == self.observation_window:
                        trend, normalized = self._classify_trend()
                        selected_action = "reel" if trend == "rising" else "pump" if trend == "steady" else None
                        cooldown_ready = (
                            self._last_action_at is None or now - self._last_action_at >= self.action_cooldown
                        )
                        self._log_event(
                            "tension_trend",
                            {
                                "trend": trend,
                                "selected_action": selected_action if cooldown_ready else None,
                                "normalized_widths": normalized,
                                "cooldown_ready": cooldown_ready,
                            },
                        )
                        self._width_history.clear()
                        if selected_action is not None and cooldown_ready:
                            key = self.reel_key if selected_action == "reel" else self.pump_key
                            self._last_action_at = now
                            self._log_event(selected_action, {"key": key, "trend": trend})
                            self.next_state = "WAITING"
                            return Action(action_type="key_press", key=key)

                    return self._wait_action()

            if self._gauge_seen:
                self._width_history.clear()
                if self._has_tension_evidence(result):
                    return self._wait_action()
                self._absent_frames += 1
                if self._absent_frames >= self.disappearance_count:
                    return self._finish_fight(
                        "fight_complete",
                        {"absent_frames": self._absent_frames},
                    )
                fight_started_at = self._fight_started_at if self._fight_started_at is not None else now
                fight_elapsed = now - fight_started_at
                if fight_elapsed >= self.fight_timeout:
                    return self._finish_fight(
                        "timeout",
                        {"reason": "fight_timeout", "fight_timeout": self.fight_timeout, "elapsed": fight_elapsed},
                    )
                return self._wait_action()

            # AC-2: Check for timeout; if exceeded, return to IDLE
            remaining = max(0.0, self.wait_timeout - wait_elapsed)

            # Still waiting for bite
            logger.debug("Fishing FSM: WAITING for bite (%.2f seconds remaining)", remaining)
            self.next_state = "WAITING"
            return Action(action_type="wait", duration=min(0.1, remaining))

        elif state_name == "REELING":
            self._log_event("reel", {"key": self.reel_key})
            self.next_state = "WAITING"
            return Action(action_type="key_press", key=self.reel_key)

        # Unknown FSM state: raise error to catch integration bugs early
        logger.error("Unknown FSM state: %s", state_name)
        raise ValueError(f"Invalid FSM state: {state_name}. Valid states: IDLE, CASTING, WAITING, REELING, STOPPED")
