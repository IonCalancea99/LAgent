"""Tests for Story 6.5: Session Cap and Clean Shutdown"""

from lagent.common import PerceptionResult, Detection
from lagent.agent.lifecycle import SessionCapController
from lagent.agent.warlord import WarlordCombatFSM
from lagent.agent.prophet import ProphetBuffPolicy


def fake_profile():
    """Create a fake profile."""
    return {
        "name": "warlord",
        "roi_positions": {},
        "fsm_bindings": {
            "pulling": {"frame_center": (500, 500), "melee_tolerance": 75.0},
            "looting": {"loot_timeout": 5.0},
        },
        "skill_key_bindings": {"pull": "1", "aoe": "2", "loot": "3"},
        "buff_timer_durations": {},
        "recovery": {"actions": []},
        "inventory": {"return_actions": []},
        "aggro_risk_radius": 150.0,
        "retry_interval": 1.0,
    }


def fake_perception(mobs=False):
    """Create a fake PerceptionResult."""
    detections = []
    if mobs:
        detections = [Detection(class_name="mob", confidence=0.9, bbox_xyxy=(400, 400, 600, 600))]
    return PerceptionResult(detections=detections, ocr_values={})


class FakeSessionDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def test_session_cap_initialized_monotonic():
    """AC-1: Session cap initialized and is monotonic."""
    cap = SessionCapController(duration=10.0)
    assert cap.duration == 10.0
    assert cap.reached is False


def test_session_cap_expiry_at_configured_duration():
    """AC-2: Cap expiry is checked and returns True at configured duration."""
    now = [0.0]
    def fake_clock():
        return now[0]
    
    cap = SessionCapController(duration=10.0, clock=fake_clock)
    
    # Before expiry
    assert cap.expired() is False
    
    # At expiry
    now[0] = 10.0
    assert cap.expired() is True
    
    # Subsequent calls remain expired (idempotent)
    now[0] = 20.0
    assert cap.expired() is True


def test_warlord_transitions_to_stopped_on_cap_expiry():
    """AC-3: WL transitions to STOPPED on session cap expiry."""
    now = [0.0]
    def fake_clock():
        return now[0]
    
    profile = fake_profile()
    db = FakeSessionDB()
    
    wl = WarlordCombatFSM(
        profile=profile,
        session_id="test-session",
        db=db,
        session_cap_duration=10.0,
        clock=fake_clock,
    )
    
    # Before cap - should pull mobs
    action = wl(fake_perception(mobs=True), "IDLE")
    assert action is not None
    
    # At cap - should transition to STOPPED
    now[0] = 10.0
    action = wl(fake_perception(mobs=True), "IDLE")
    assert action is None
    assert wl.state == "STOPPED"


def test_no_combat_actions_after_cap_expiry():
    """AC-4: No combat actions after session cap."""
    now = [0.0]
    def fake_clock():
        return now[0]
    
    profile = fake_profile()
    
    wl = WarlordCombatFSM(
        profile=profile,
        session_cap_duration=5.0,
        clock=fake_clock,
    )
    
    # Advance past cap
    now[0] = 6.0
    
    # Transition to STOPPED first, then verify repeated ticks remain inert.
    action = wl(fake_perception(mobs=True), "IDLE")
    assert action is None
    assert wl.state == "STOPPED"
    for _ in range(3):
        action = wl(fake_perception(mobs=True), "STOPPED")
        assert action is None


def test_pp_halts_when_wl_is_stopped():
    """AC-5: PP halts safely in STOPPED state."""
    import time
    from lagent.common import GameState, PartyState
    
    profile = {
        "name": "prophet",
        "buff_timer_durations": {"haste": 1.0},
        "skill_key_bindings": {"buff": "2"},
        "aggro_risk_radius": 150.0,
        "retry_interval": 1.0,
    }
    game_state_provider = lambda _: GameState(
        hp_percent=100.0,
        mp_percent=100.0,
        active_buffs=[],
        character_position=(100, 100),
        ui_mode="combat",
        peer_party_state=PartyState(
            fsm_state="STOPPED",  # WL is STOPPED
            hp_percent=100.0,
            mp_percent=100.0,
            position=(0, 0),
            buff_presence={},
            heartbeat_timestamp=time.time(),
        ),
    )
    
    pp = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
    )
    
    # PP in STOPPED state should suppress actions
    action = pp(PerceptionResult(detections=[], ocr_values={}), "STOPPED")
    assert action is None


def test_session_cap_idempotent():
    """AC-6: Session cap shutdown is idempotent."""
    now = [0.0]
    def fake_clock():
        return now[0]
    
    profile = fake_profile()
    db = FakeSessionDB()
    
    wl = WarlordCombatFSM(
        profile=profile,
        session_id="test-session",
        db=db,
        session_cap_duration=5.0,
        clock=fake_clock,
    )
    
    # Advance past cap
    now[0] = 6.0
    
    # First call - transitions to STOPPED
    action1 = wl(fake_perception(), "IDLE")
    assert action1 is None
    assert wl.state == "STOPPED"
    
    # Second call - already STOPPED, should not re-trigger
    action2 = wl(fake_perception(), "STOPPED")
    assert action2 is None
    assert wl.state == "STOPPED"


def test_session_cap_events_logged():
    """AC-7: Session cap events are logged."""
    now = [0.0]
    def fake_clock():
        return now[0]
    
    profile = fake_profile()
    db = FakeSessionDB()
    
    cap = SessionCapController(
        duration=5.0,
        clock=fake_clock,
        session_id="test-session",
        db=db,
    )
    
    # Before cap
    assert cap.expired() is False
    assert len(db.events) == 0
    
    # At cap - should log event
    now[0] = 5.0
    assert cap.expired() is True
    
    # Check that session_cap_reached event was logged
    cap_events = [e for e in db.events if e[2] == "session_cap_reached"]
    assert len(cap_events) > 0
    payload = cap_events[0][3]
    assert payload["elapsed_seconds"] == 5.0


def test_warlord_cap_reached_event_logged():
    """AC-7: WL logs cap_shutdown_initiated on transition."""
    now = [0.0]
    def fake_clock():
        return now[0]
    
    profile = fake_profile()
    db = FakeSessionDB()
    
    wl = WarlordCombatFSM(
        profile=profile,
        session_id="test-session",
        db=db,
        session_cap_duration=5.0,
        clock=fake_clock,
    )
    
    # Advance past cap
    now[0] = 6.0
    
    # Trigger cap
    wl(fake_perception(), "IDLE")
    
    # Check transition event was logged
    transition_events = [e for e in db.events if e[2] == "state_transition" and e[3].get("reason") == "session_cap_reached"]
    assert len(transition_events) > 0


def test_session_cap_cap_is_enforced():
    """AC-1: Session cap is correctly initialized from profile or parameter."""
    profile = fake_profile()
    profile["session_cap_duration"] = 20.0
    
    wl = WarlordCombatFSM(profile=profile)
    assert wl.session_cap is not None
    assert wl.session_cap.duration == 20.0


def test_session_cap_with_no_duration_creates_default():
    """Session cap with no duration specified uses default."""
    profile = fake_profile()
    
    wl = WarlordCombatFSM(profile=profile)
    assert wl.session_cap is not None
    assert wl.session_cap.duration == 14400.0  # 4 hours default
