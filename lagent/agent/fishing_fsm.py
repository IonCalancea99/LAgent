"""Fishing Mode FSM: IDLE → CASTING → WAITING with timeout."""

from __future__ import annotations

import logging
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
        clock: Callable[[], float] = time.time,
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
        self.reel_key = reel_key or reeling_binding.get("reel_key", "3")
        self.wait_timeout = wait_timeout if wait_timeout is not None else waiting_binding.get("wait_timeout", 10.0)
        self.tension_class = (tension_class or waiting_binding.get("tension_class", "tension_indicator")).lower()
        self.tension_confidence_threshold = (
            tension_confidence_threshold
            if tension_confidence_threshold is not None
            else waiting_binding.get("tension_confidence_threshold", 0.80)
        )
        
        # FSM state tracking
        self.state = "IDLE"
        self.wait_started_at: Optional[float] = None
        self.halted = False
        self.next_state: Optional[str] = None

    def _tension_detection(self, result: PerceptionResult) -> Any | None:
        aliases = {self.tension_class, "tension", "tension_indicator"}
        return max(
            (detection for detection in result.detections if detection.class_name.lower() in aliases),
            key=lambda detection: detection.confidence,
            default=None,
        )

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
        self.halted = True
        self.state = "STOPPED"

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
        if self.halted or state_name == "STOPPED":
            logger.debug("FSM in STOPPED state; no action produced")
            return None

        if state_name == "IDLE":
            # AC-1: IDLE → CASTING: Execute rod cast key sequence
            logger.debug("Fishing FSM: IDLE → casting rod (key=%s)", self.cast_key)
            self._log_event("transition", {"from": "IDLE", "to": "CASTING", "action": "cast_key"})
            return Action(action_type="key_press", key=self.cast_key)

        elif state_name == "CASTING":
            # CASTING → WAITING: Wait briefly for cast animation to complete
            # Then external loop handler transitions to WAITING
            logger.debug("Fishing FSM: CASTING → wait for cast completion")
            return Action(action_type="wait", duration=0.5)

        elif state_name == "WAITING":
            tension = self._tension_detection(result)
            if tension is not None and tension.confidence >= self.tension_confidence_threshold:
                tension_window = max(0.0, self.clock() - self.wait_started_at) if self.wait_started_at is not None else 0.0
                self._log_event(
                    "tension_detected",
                    {"confidence": tension.confidence, "tension_window": tension_window},
                )
                self.next_state = "REELING"
                return Action(action_type="wait", duration=0.0)

            # AC-2: Check for timeout; if exceeded, return to IDLE
            # Reset timer if entering WAITING for the first time (coming from another state)
            if entering_waiting_fresh or self.wait_started_at is None:
                self.wait_started_at = self.clock()
                logger.debug("Fishing FSM: WAITING started at %s", self.wait_started_at)

            elapsed = self.clock() - self.wait_started_at
            remaining = max(0.0, self.wait_timeout - elapsed)  # Clamp to non-negative

            if remaining <= 0:
                # Timeout: no bite detected, return to IDLE
                logger.info("Fishing FSM: WAITING timeout (waited %.2f seconds) → IDLE", elapsed)
                self._log_event(
                    "missed_tension",
                    {
                        "confidence": tension.confidence if tension is not None else 0.0,
                        "tension_window": elapsed,
                        "timeout": True,
                    },
                )
                self._log_event("timeout", {"wait_timeout": self.wait_timeout, "elapsed": elapsed})
                self.wait_started_at = None
                self.next_state = "IDLE"
                # Signal external handler to transition to IDLE
                return Action(action_type="wait", duration=0.0)

            # Still waiting for bite
            logger.debug("Fishing FSM: WAITING for bite (%.2f seconds remaining)", remaining)
            return Action(action_type="wait", duration=min(0.1, remaining))

        elif state_name == "REELING":
            self._log_event("reel", {"key": self.reel_key})
            self.next_state = "IDLE"
            return Action(action_type="key_press", key=self.reel_key)

        # Unknown FSM state: raise error to catch integration bugs early
        logger.error("Unknown FSM state: %s", state_name)
        raise ValueError(f"Invalid FSM state: {state_name}. Valid states: IDLE, CASTING, WAITING, REELING, STOPPED")
