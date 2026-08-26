"""Heartbeat health monitor for agent Party Bus publishers."""

import logging
import time

from lagent.common.transport import HEARTBEAT_INTERVAL, HEARTBEAT_MISSED_COUNT


class HeartbeatMonitor:
    def __init__(
        self,
        agent_ids,
        interval=HEARTBEAT_INTERVAL,
        missed_count=HEARTBEAT_MISSED_COUNT,
        logger=None,
        session_id=None,
        session_db=None,
        control_publisher=None,
        clock=time.time,
    ):
        self.last_seen = {agent_id: None for agent_id in agent_ids}
        self.interval = interval
        self.missed_count = missed_count
        self.logger = logger or logging.getLogger(__name__)
        self.session_id = session_id
        self.session_db = session_db
        self.control_publisher = control_publisher
        self.clock = clock
        self.halted = False
        self._reconnected_logged = False

    def _log_event(self, event_type, payload):
        if self.session_db is not None and self.session_id is not None:
            self.session_db.append_event(self.session_id, "orchestrator.heartbeat", event_type, payload)

    def _healthy(self, now):
        return all(last_seen is not None and now - last_seen < self.interval * self.missed_count for last_seen in self.last_seen.values())

    def observe(self, agent_id: str, timestamp: float | None = None) -> None:
        if agent_id in self.last_seen:
            self.last_seen[agent_id] = self.clock() if timestamp is None else timestamp
            if self.halted and self._healthy(self.clock()) and not self._reconnected_logged:
                health = {key: self._healthy_agent(key, self.clock()) for key in self.last_seen}
                self._log_event("party_bus_reconnected", {"agent_health": health})
                self._reconnected_logged = True

    def observe_message(self, message: dict, received_at: float | None = None) -> None:
        if message.get("type") == "heartbeat":
            self.observe(message.get("agent_id", ""), received_at)

    def _healthy_agent(self, agent_id, now):
        last_seen = self.last_seen[agent_id]
        return last_seen is not None and now - last_seen < self.interval * self.missed_count

    def check(self, now: float | None = None) -> list[str]:
        now = self.clock() if now is None else now
        if self.halted:
            return []
        warnings = []
        for agent_id, last_seen in self.last_seen.items():
            if last_seen is not None and now - last_seen >= self.interval * self.missed_count:
                self.logger.warning("heartbeat missed: agent_id=%s", agent_id)
                warnings.append(agent_id)
        if warnings:
            missed_agent_id = warnings[0]
            payload = {
                "reason": "heartbeat_missed",
                "missed_agent_id": missed_agent_id,
                "missed_count": self.missed_count,
            }
            self._log_event("heartbeat_missed", payload)
            control = {"type": "session_halt", "payload": {"session_id": self.session_id, **payload}}
            if self.control_publisher is not None:
                self.control_publisher(control)
            self._log_event("session_halt", payload)
            self.halted = True
            self._reconnected_logged = False
        return warnings

    def resume(self, control: dict) -> bool:
        payload = control.get("payload", control)
        if (
            self.halted
            and payload.get("session_id") == self.session_id
            and payload.get("reason") == "operator_resume"
            and set(payload.get("agent_ids", [])) == set(self.last_seen)
            and self._healthy(self.clock())
        ):
            self._log_event("session_resume", payload)
            self.halted = False
            self._reconnected_logged = False
            return True
        return False