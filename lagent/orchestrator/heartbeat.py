"""Heartbeat health monitor for agent Party Bus publishers."""

import logging
import time

from lagent.common.transport import HEARTBEAT_INTERVAL, HEARTBEAT_MISSED_COUNT


class HeartbeatMonitor:
    def __init__(self, agent_ids, interval=HEARTBEAT_INTERVAL, missed_count=HEARTBEAT_MISSED_COUNT, logger=None):
        self.last_seen = {agent_id: None for agent_id in agent_ids}
        self.interval = interval
        self.missed_count = missed_count
        self.logger = logger or logging.getLogger(__name__)

    def observe(self, agent_id: str, timestamp: float | None = None) -> None:
        if agent_id in self.last_seen:
            self.last_seen[agent_id] = timestamp or time.time()

    def check(self, now: float | None = None) -> list[str]:
        now = now or time.time()
        warnings = []
        for agent_id, last_seen in self.last_seen.items():
            if last_seen is not None and now - last_seen >= self.interval * self.missed_count:
                self.logger.warning("heartbeat missed: agent_id=%s", agent_id)
                warnings.append(agent_id)
        return warnings