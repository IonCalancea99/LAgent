import math
import time

from lagent.common import GameState, PartyState, PerceptionResult, Detection


class FakeSessionDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def _make_game_state(*, peer_state: str = "IDLE") -> GameState:
    return GameState(
        hp_percent=90.0,
        mp_percent=80.0,
        active_buffs=["haste"],
        character_position=(100, 100),
        ui_mode="combat",
        peer_party_state=PartyState(
            fsm_state=peer_state,
            hp_percent=80.0,
            mp_percent=70.0,
            position=(200, 200),
            buff_presence={"haste": True},
            heartbeat_timestamp=time.time(),
        ),
    )


def test_pp_buff_safety_check_passes_when_clear_and_not_pulling():
    from lagent.agent.prophet import PPBuffSafetyCheck

    check = PPBuffSafetyCheck(aggro_risk_radius=50.0, retry_interval=1.5)
    state = _make_game_state(peer_state="IDLE")
    perception = PerceptionResult(
        detections=[
            Detection(class_name="mob", confidence=0.9, bbox_xyxy=(1000, 1000, 1010, 1010)),
        ]
    )

    outcome = check.evaluate(state, perception)

    assert outcome["safe"] is True
    assert outcome["reasons"] == []


def test_pp_buff_safety_check_fails_when_wl_is_pulling():
    from lagent.agent.prophet import PPBuffSafetyCheck

    check = PPBuffSafetyCheck(aggro_risk_radius=50.0, retry_interval=1.5)
    state = _make_game_state(peer_state="PULLING")
    perception = PerceptionResult(detections=[])

    outcome = check.evaluate(state, perception)

    assert outcome["safe"] is False
    assert outcome["wl_pulling"] is True
    assert any("wl_pulling" in reason for reason in outcome["reasons"])


def test_pp_buff_safety_check_fails_when_mob_is_within_radius():
    from lagent.agent.prophet import PPBuffSafetyCheck

    check = PPBuffSafetyCheck(aggro_risk_radius=50.0, retry_interval=1.5)
    state = _make_game_state(peer_state="IDLE")
    perception = PerceptionResult(
        detections=[
            Detection(class_name="mob", confidence=0.9, bbox_xyxy=(120, 100, 160, 130)),
        ]
    )

    outcome = check.evaluate(state, perception)

    assert outcome["safe"] is False
    assert outcome["mob_within_radius"] is True
    assert any("aggro_risk_radius" in reason for reason in outcome["reasons"])


def test_pp_buff_safety_check_defers_and_logs_retry_after_failure():
    from lagent.agent.prophet import PPBuffSafetyCheck

    check = PPBuffSafetyCheck(aggro_risk_radius=50.0, retry_interval=1.5)
    state = _make_game_state(peer_state="IDLE")
    perception = PerceptionResult(
        detections=[
            Detection(class_name="mob", confidence=0.9, bbox_xyxy=(120, 100, 160, 130)),
        ]
    )
    db = FakeSessionDB()

    outcome = check.evaluate(state, perception, session_db=db, session_id="session-42")

    assert outcome["safe"] is False
    assert outcome["retry_at"] > time.time()
    assert math.isclose(outcome["retry_at"] - time.time(), 1.5, abs_tol=0.5)
    assert db.events
    assert db.events[0][2] == "buff_cast_deferred"
