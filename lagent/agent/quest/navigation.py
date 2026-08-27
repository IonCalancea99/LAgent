"""Bounded resource-driven quest navigation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping

from lagent.common import Action, QuestResource


class NavigationStatus(str, Enum):
    READY = "ready"
    MOVING = "moving"
    RETRY = "retry"
    ARRIVED = "arrived"
    SAFE_STOP = "safe_stop"


@dataclass(frozen=True)
class Waypoint:
    name: str
    expected_area: str
    action: Action
    expected_npc: str | None = None


class QuestNavigator:
    """Execute a validated route through HSL and verify every waypoint."""

    def __init__(
        self,
        resource: QuestResource,
        waypoints: Mapping[str, Waypoint],
        *,
        hsl: Any,
        session_id: str | None = None,
        db: Any | None = None,
        objective_index: int = 0,
        clock: Callable[[], float] = time.monotonic,
        waypoint_timeout: float | None = None,
    ) -> None:
        self.resource = resource
        self.waypoints = waypoints
        self.hsl = hsl
        self.session_id = session_id
        self.db = db
        self.objective_index = objective_index
        self.clock = clock
        self.waypoint_timeout = waypoint_timeout if waypoint_timeout is not None else resource.timeouts.get("travel", 30.0)
        self.retries_remaining = resource.retries.get("travel", 0)
        self.current_waypoint_index = 0
        self.status = NavigationStatus.READY
        self.failure_reason: str | None = None
        self._started_at: float | None = None

        if not resource.navigation_route:
            self._set_invalid_route("missing_route_metadata")
        elif any(name not in waypoints for name in resource.navigation_route):
            self._set_invalid_route("incomplete_route_metadata")

    @property
    def current_waypoint(self) -> Waypoint | None:
        if self.current_waypoint_index >= len(self.resource.navigation_route):
            return None
        return self.waypoints.get(self.resource.navigation_route[self.current_waypoint_index])

    def _set_invalid_route(self, reason: str) -> None:
        self.status = NavigationStatus.SAFE_STOP
        self.failure_reason = reason
        self._log_failure(reason, terminal=True)

    def _log_failure(self, reason: str, *, terminal: bool) -> None:
        if self.db is None or self.session_id is None:
            return
        waypoint = self.current_waypoint
        self.db.append_event(
            self.session_id,
            "agent.quest",
            "quest_navigation_failure",
            {
                "quest_id": self.resource.quest_id,
                "objective_index": self.objective_index,
                "route": list(self.resource.navigation_route),
                "waypoint": waypoint.name if waypoint is not None else None,
                "reason": reason,
                "retries_remaining": self.retries_remaining,
                "terminal": terminal,
            },
        )

    def _fail(self, reason: str) -> bool:
        self.retries_remaining = max(0, self.retries_remaining - 1)
        terminal = self.retries_remaining == 0
        logged_reason = f"{reason}_retry_exhausted" if terminal else reason
        self.failure_reason = logged_reason
        self.status = NavigationStatus.SAFE_STOP if terminal else NavigationStatus.RETRY
        self._started_at = None
        self._log_failure(logged_reason, terminal=terminal)
        return True

    def dispatch_current(self) -> Action | None:
        """Dispatch the current resource-selected waypoint through HSL."""

        if self.status in {NavigationStatus.SAFE_STOP, NavigationStatus.ARRIVED}:
            return None
        waypoint = self.current_waypoint
        if waypoint is None:
            self._set_invalid_route("incomplete_route_metadata")
            return None
        self.hsl.dispatch_action(waypoint.action)
        self.status = NavigationStatus.MOVING
        self.failure_reason = None
        self._started_at = self.clock()
        return waypoint.action

    def verify_position(self, *, area: str | None, npc: str | None = None, ambiguous: bool = False) -> bool:
        """Advance only after matching the expected area and final target NPC."""

        if self.status is not NavigationStatus.MOVING:
            return False
        waypoint = self.current_waypoint
        if waypoint is None:
            return False
        if ambiguous:
            self._fail("ambiguous_map")
            return False
        if area != waypoint.expected_area:
            self._fail("inconsistent_route_state")
            return False
        if waypoint.expected_npc is not None and (npc or "").casefold() != waypoint.expected_npc.casefold():
            self._fail("npc_not_found")
            return False

        self.current_waypoint_index += 1
        self._started_at = None
        self.failure_reason = None
        if self.current_waypoint_index == len(self.resource.navigation_route):
            self.status = NavigationStatus.ARRIVED
        else:
            self.status = NavigationStatus.READY
        return True

    def check_timeout(self) -> bool:
        if self.status is not NavigationStatus.MOVING or self._started_at is None:
            return False
        if self.clock() - self._started_at <= self.waypoint_timeout:
            return False
        return self._fail("waypoint_timeout")

    def report_stuck(self) -> bool:
        if self.status is not NavigationStatus.MOVING:
            return False
        return self._fail("route_stuck")