"""Acceptance tests for Story 9.4: bounded quest navigation."""

from lagent.agent.quest.navigation import NavigationStatus, QuestNavigator, Waypoint
from lagent.common import Action, ObjectiveStep, QuestResource


class FakeHSL:
    def __init__(self):
        self.actions = []

    def dispatch_action(self, action):
        self.actions.append(action)
        return action


class EventDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def make_resource(route=None, retries=2):
    return QuestResource(
        quest_id="marcela_supply_check",
        quest_name="Supply Check",
        starting_npc="Marcela",
        objective_sequence=[
            ObjectiveStep(order=1, id="talk_marcela", name="Talk", target_npc="Marcela", type="dialogue")
        ],
        navigation_route=["town_square", "marcela_steps"] if route is None else route,
        retries={"travel": retries},
        safe_stop_conditions=["route_stuck", "ambiguous_map"],
    )


def waypoint_map():
    return {
        "town_square": Waypoint(
            name="town_square",
            expected_area="kamael_village_square",
            action=Action(action_type="key_press", key="w"),
        ),
        "marcela_steps": Waypoint(
            name="marcela_steps",
            expected_area="marcela_platform",
            expected_npc="Marcela",
            action=Action(action_type="mouse_move", x=640, y=360),
        ),
    }


def test_valid_resource_route_dispatches_waypoints_through_hsl_and_verifies_npc():
    hsl = FakeHSL()
    navigator = QuestNavigator(make_resource(), waypoint_map(), hsl=hsl)

    first = navigator.dispatch_current()
    assert first.key == "w"
    assert hsl.actions == [first]
    assert navigator.verify_position(area="kamael_village_square") is True

    second = navigator.dispatch_current()
    assert second.action_type == "mouse_move"
    assert navigator.verify_position(area="marcela_platform", npc="Marcela") is True
    assert navigator.status is NavigationStatus.ARRIVED
    assert len(hsl.actions) == 2


def test_missing_or_incomplete_route_metadata_fails_closed_without_dispatch():
    empty_hsl = FakeHSL()
    missing = QuestNavigator(make_resource(route=[]), waypoint_map(), hsl=empty_hsl)
    incomplete = QuestNavigator(make_resource(route=["unknown_waypoint"]), waypoint_map(), hsl=FakeHSL())

    assert missing.status is NavigationStatus.SAFE_STOP
    assert missing.failure_reason == "missing_route_metadata"
    assert incomplete.status is NavigationStatus.SAFE_STOP
    assert incomplete.failure_reason == "incomplete_route_metadata"
    assert missing.dispatch_current() is None
    assert empty_hsl.actions == []


def test_waypoint_timeout_consumes_retry_and_exhaustion_safe_stops():
    now = [0.0]
    navigator = QuestNavigator(
        make_resource(retries=2), waypoint_map(), hsl=FakeHSL(), clock=lambda: now[0], waypoint_timeout=5.0
    )

    navigator.dispatch_current()
    now[0] = 6.0
    assert navigator.check_timeout() is True
    assert navigator.status is NavigationStatus.RETRY
    assert navigator.retries_remaining == 1
    navigator.dispatch_current()
    now[0] = 12.0
    assert navigator.check_timeout() is True
    assert navigator.status is NavigationStatus.SAFE_STOP
    assert navigator.failure_reason == "waypoint_timeout_retry_exhausted"


def test_ambiguous_map_and_inconsistent_route_state_block_progression():
    navigator = QuestNavigator(make_resource(), waypoint_map(), hsl=FakeHSL())
    navigator.dispatch_current()

    assert navigator.verify_position(area=None, ambiguous=True) is False
    assert navigator.current_waypoint_index == 0
    assert navigator.failure_reason == "ambiguous_map"

    navigator.dispatch_current()
    assert navigator.verify_position(area="wrong_area") is False
    assert navigator.current_waypoint_index == 0
    assert navigator.failure_reason == "inconsistent_route_state_retry_exhausted"


def test_missing_expected_npc_never_transitions_to_arrived():
    navigator = QuestNavigator(make_resource(), waypoint_map(), hsl=FakeHSL())
    navigator.dispatch_current()
    navigator.verify_position(area="kamael_village_square")
    navigator.dispatch_current()

    assert navigator.verify_position(area="marcela_platform", npc=None) is False
    assert navigator.status is NavigationStatus.RETRY
    assert navigator.failure_reason == "npc_not_found"


def test_stuck_exhaustion_logs_objective_and_route_context():
    database = EventDB()
    navigator = QuestNavigator(
        make_resource(retries=1),
        waypoint_map(),
        hsl=FakeHSL(),
        session_id="session-9",
        db=database,
        objective_index=0,
    )
    navigator.dispatch_current()

    navigator.report_stuck()

    assert navigator.status is NavigationStatus.SAFE_STOP
    session_id, source, event_type, payload = database.events[-1]
    assert (session_id, source, event_type) == ("session-9", "agent.quest", "quest_navigation_failure")
    assert payload["objective_index"] == 0
    assert payload["route"] == ["town_square", "marcela_steps"]
    assert payload["waypoint"] == "town_square"
    assert payload["reason"] == "route_stuck_retry_exhausted"
    assert payload["terminal"] is True