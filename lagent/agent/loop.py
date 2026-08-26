"""Base agent loop for capture → inference → FSM → HSL execution."""

from __future__ import annotations

import logging
import queue
import time
from typing import Any, Callable

from lagent.agent.capture import Frame, FrameQueue
from lagent.agent.inference import PolicyQueue
from lagent.common import Action, PerceptionResult
from lagent.hsl import HSL

logger = logging.getLogger(__name__)


class AgentLoop:
    """Single-window, single-thread base loop for the agent runtime."""

    def __init__(
        self,
        *,
        frame_queue: FrameQueue,
        policy_queue: PolicyQueue,
        state_handler: Callable[[PerceptionResult, str], Action | None],
        hsl: HSL,
        state_name: str = "IDLE",
        profile: Any | None = None,
        session_id: str | None = None,
        db: Any | None = None,
        capture_latency_budget_ms: float = 200.0,
        capture: Any | None = None,
        inference: Any | None = None,
        party_bus: Any | None = None,
        session_cap: Any | None = None,
    ) -> None:
        self.frame_queue = frame_queue
        self.policy_queue = policy_queue
        self.state_handler = state_handler
        self.hsl = hsl
        self.state_name = state_name
        self.profile = profile
        self.session_id = session_id
        self.db = db
        self.capture_latency_budget_ms = capture_latency_budget_ms
        self.capture = capture
        self.inference = inference
        self.party_bus = party_bus
        self.session_cap = session_cap
        self._tick_counter = 0

    def _current_state_name(self) -> str:
        return self.state_name

    def _next_tick_id(self) -> str:
        self._tick_counter += 1
        return f"tick-{self._tick_counter:06d}"

    def _pop_frame(self) -> Frame | None:
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None

    def _pop_policy_result(self) -> PerceptionResult | None:
        try:
            return self.policy_queue.get_nowait()
        except queue.Empty:
            return None

    @staticmethod
    def _task_done(item_queue: Any, item: Any | None) -> None:
        if item is not None:
            item_queue.task_done()

    def _log_tick(self, tick_id: str, payload: dict[str, Any]) -> None:
        if self.db is not None and self.session_id is not None:
            try:
                self.db.append_event(self.session_id, "agent", "tick", {"tick_id": tick_id, **payload})
            except Exception:
                logger.exception("tick logging failed for %s", tick_id)

    def _transition_state(self, from_state: str, action: Action | None) -> str:
        """
        Determine the next FSM state based on current state and FSM bindings.
        
        AC-1: After action is executed, check FSM bindings for next state.
        If a next state is defined, transition to it for the next tick.
        
        Args:
            from_state: Current FSM state
            action: Action produced by state handler (used for decision logic)
            
        Returns:
            Next state name (may be same as from_state if no binding exists)
        """
        fsm_bindings = {}
        if self.profile is not None:
            if isinstance(self.profile, dict):
                fsm_bindings = self.profile.get("fsm_bindings", {})
            else:
                fsm_bindings = getattr(self.profile, "fsm_bindings", {})
        
        if not fsm_bindings:
            logger.warning("AgentLoop: FSM bindings not found in profile; state transition disabled")
            return from_state
        
        current_binding = next(
            (value for key, value in fsm_bindings.items() if str(key).upper() == from_state.upper()),
            {},
        )
        
        # Handle both dict and object bindings
        if isinstance(current_binding, dict):
            next_state = current_binding.get("next")
        else:
            next_state = getattr(current_binding, "next", None)
        
        handler_next_state = getattr(self.state_handler, "next_state", None)
        if handler_next_state is not None:
            next_state = handler_next_state

        if next_state is not None:
            # Validate next_state is in the valid set
            valid_states = {
                "IDLE", "CASTING", "WAITING", "REELING", "STOPPED",
                "PULLING", "FIGHTING", "LOOTING", "BUFFING", "DEAD", "RETURNING", "PAUSED",
            }
            next_state = str(next_state).upper()
            if next_state not in valid_states:
                logger.error("AgentLoop: Invalid FSM state transition: %s → %s (not in valid states)", from_state, next_state)
                return from_state
            
            logger.debug("FSM state transition: %s → %s", from_state, next_state)
            if self.db is not None and self.session_id is not None:
                try:
                    self.db.append_event(
                        self.session_id,
                        "fsm",
                        "state_transition",
                        {"from": from_state, "to": next_state},
                    )
                except (IOError, OSError, PermissionError) as e:
                    logger.critical("Unrecoverable state transition logging error: %s", e)
                    raise
                except Exception as e:
                    logger.warning("Transient state transition logging error (continuing): %s", e)
            return next_state
        
        return from_state

    def request_halt(self) -> None:
        """
        Request FSM halt via callback (AC-3: Callback/Signal Handler integration).
        
        When the session layer detects a halt signal, it calls this method,
        which propagates the halt to the FSM. The FSM will transition to STOPPED
        and produce no further actions.
        
        Called by: session/orchestration layer when halt signal arrives
        """
        if self.state_handler is not None and hasattr(self.state_handler, "pause_for_session_halt"):
            self.request_session_halt("unknown", 0)
            return
        if self.state_handler is not None and hasattr(self.state_handler, "handle_halt"):
            logger.info("AgentLoop: Halt requested; propagating to FSM")
            try:
                self.state_handler.handle_halt()
            except Exception as e:
                logger.exception("Error during FSM halt: %s", e)

    def request_session_halt(self, missed_agent_id: str, missed_count: int) -> None:
        if self.state_handler is None or not hasattr(self.state_handler, "pause_for_session_halt"):
            self.request_halt()
            return
        self.state_handler.pause_for_session_halt(missed_agent_id, missed_count)
        self.state_name = "PAUSED"
        for item_queue in (self.frame_queue, self.policy_queue):
            while True:
                try:
                    item_queue.get_nowait()
                except queue.Empty:
                    break
                item_queue.task_done()

    def request_resume(self) -> None:
        if self.state_handler is not None and hasattr(self.state_handler, "resume_session"):
            self.state_handler.resume_session("operator_resume")
            self.state_name = self.state_handler.state
            return True
        return False

    def _poll_party_bus(self) -> None:
        if self.party_bus is None:
            return
        try:
            message = self.party_bus.receive(timeout=0.0)
        except TimeoutError:
            return
        self.party_bus.handle_control(message, self)

    def _publish_heartbeat(self) -> None:
        if self.party_bus is not None:
            self.party_bus.publish_heartbeat()

    def tick(self) -> dict[str, Any]:
        """Execute one perception → policy → action loop iteration."""
        tick_id = self._next_tick_id()
        started = time.perf_counter()
        self._poll_party_bus()
        self._publish_heartbeat()

        if self.session_cap is not None and self.session_cap.expired():
            self.state_name = "STOPPED"

        if self.state_name == "PAUSED":
            payload = {
                "tick_id": tick_id,
                "state": self.state_name,
                "frame_count": 0,
                "status": "paused",
                "action": None,
                "latency_ms": (time.perf_counter() - started) * 1000,
            }
            self._log_tick(tick_id, payload)
            return payload

        frame = self._pop_frame()
        result = self._pop_policy_result()
        if frame is None and result is None:
            if self.state_name in {"PAUSED", "DEAD", "RETURNING", "STOPPED"}:
                payload = {"tick_id": tick_id, "state": self.state_name, "frame_count": 0, "status": "safe", "action": None,
                           "latency_ms": (time.perf_counter() - started) * 1000}
                self._log_tick(tick_id, payload)
                return payload
            action = Action(action_type="wait", duration=0.0)
            if self.hsl is not None:
                try:
                    self.hsl.dispatch_action(action, session_id=self.session_id, sessions_db=self.db)
                except Exception:
                    logger.exception("HSL dispatch failed during idle tick %s", tick_id)
            tick_payload = {
                "tick_id": tick_id,
                "state": self.state_name,
                "frame_count": 0,
                "status": "idle",
                "action": action,
                "queue_state": {
                    "frame_queue_size": self.frame_queue.qsize(),
                    "policy_queue_size": self.policy_queue.qsize(),
                    "frame_queue_dropped": self.frame_queue.dropped_frames,
                    "policy_queue_dropped": self.policy_queue.dropped_results,
                },
                "latency_ms": (time.perf_counter() - started) * 1000,
            }
            self._log_tick(tick_id, tick_payload)
            return tick_payload

        if result is None:
            if frame is not None:
                self._task_done(self.frame_queue, frame)
            payload = {"tick_id": tick_id, "state": self.state_name, "frame_count": 0, "status": "awaiting_inference", "action": None, "latency_ms": (time.perf_counter() - started) * 1000}
            self._log_tick(tick_id, payload)
            return payload

        if frame is None:
            self._task_done(self.policy_queue, result)
            payload = {"tick_id": tick_id, "state": self.state_name, "frame_count": 0, "status": "correlation_mismatch", "action": None, "latency_ms": (time.perf_counter() - started) * 1000}
            self._log_tick(tick_id, payload)
            return payload

        if result._frame_id not in (None, frame.frame_id):
            self._task_done(self.frame_queue, frame)
            self._task_done(self.policy_queue, result)
            payload = {"tick_id": tick_id, "state": self.state_name, "frame_count": 0, "status": "correlation_mismatch", "action": None, "latency_ms": (time.perf_counter() - started) * 1000}
            self._log_tick(tick_id, payload)
            return payload

        self._task_done(self.frame_queue, frame)
        if self.db is not None and self.session_id is not None and frame is not None:
            try:
                self.db.append_event(self.session_id, "agent", "frame_captured", {"tick_id": tick_id, "frame_source": frame.source})
            except Exception:
                logger.exception("frame logging failed during tick %s", tick_id)

        try:
            action = self.state_handler(result, self.state_name)
        except Exception:
            logger.exception("state handler failed during tick %s", tick_id)
            action = None
        if action is None:
            if self.state_name in {"PAUSED", "DEAD", "RETURNING", "STOPPED"}:
                self._task_done(self.policy_queue, result)
                payload = {"tick_id": tick_id, "state": self.state_name, "frame_count": 1, "status": "safe", "action": None,
                           "latency_ms": (time.perf_counter() - started) * 1000}
                self._log_tick(tick_id, payload)
                return payload
            action = Action(action_type="wait", duration=0.0)

        if self.hsl is not None:
            try:
                self.hsl.dispatch_action(action, session_id=self.session_id, sessions_db=self.db)
            except Exception:
                logger.exception("HSL dispatch failed during tick %s", tick_id)
        self._task_done(self.policy_queue, result)

        # Preserve the state that evaluated this frame in the tick payload.
        evaluated_state = self.state_name
        next_state = self._transition_state(evaluated_state, action)
        self.state_name = next_state

        elapsed_ms = (time.perf_counter() - started) * 1000
        payload = {
            "tick_id": tick_id,
            "state": evaluated_state,
            "frame_count": 1,
            "action": action,
            "status": "completed",
            "queue_state": {
                "frame_queue_size": self.frame_queue.qsize(),
                "policy_queue_size": self.policy_queue.qsize(),
                "frame_queue_dropped": self.frame_queue.dropped_frames,
                "policy_queue_dropped": self.policy_queue.dropped_results,
            },
            "latency_ms": elapsed_ms,
            "capture_latency_budget_ms": self.capture_latency_budget_ms,
        }

        self._log_tick(tick_id, payload)
        return payload

    def run(self, *, duration: float | None = None, tick_interval: float = 0.1, max_ticks: int | None = None) -> list[dict[str, Any]]:
        """Run the loop for a period or a fixed number of ticks."""
        ticks: list[dict[str, Any]] = []
        started = time.monotonic()
        tick_count = 0
        workers = [worker for worker in (self.capture, self.inference) if worker is not None]
        for worker in workers:
            if not worker.is_alive():
                worker.start()

        try:
            while True:
                if max_ticks is not None and tick_count >= max_ticks:
                    break
                if duration is not None and (time.monotonic() - started) >= duration:
                    break
                ticks.append(self.tick())
                tick_count += 1
                if tick_interval > 0:
                    time.sleep(tick_interval)
        finally:
            for worker in reversed(workers):
                stop = getattr(worker, "stop", None)
                if stop is not None:
                    stop()

        return ticks


__all__ = ["AgentLoop"]
