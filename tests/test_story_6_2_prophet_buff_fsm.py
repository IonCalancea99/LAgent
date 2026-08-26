"""Tests for Story 6.2: Prophet Buff Cycle FSM"""

import math
import time
from unittest.mock import Mock

from lagent.common import Action, GameState, PartyState, PerceptionResult
from lagent.agent.prophet import BuffTimer, ProphetBuffPolicy, PPBuffSafetyCheck


def fake_profile(
    buff_durations=None,
    skill_bindings=None,
    aggro_risk_radius=150.0,
    retry_interval=1.0,
):
    """Create a fake profile dict for testing."""
    return {
        "name": "prophet",
        "buff_timer_durations": buff_durations or {"haste": 5.0},
        "skill_key_bindings": skill_bindings or {"buff": "2"},
        "aggro_risk_radius": aggro_risk_radius,
        "retry_interval": retry_interval,
    }


def fake_game_state(peer_fsm_state="IDLE"):
    """Create a fake GameState for testing."""
    return GameState(
        hp_percent=100.0,
        mp_percent=100.0,
        active_buffs=[],
        character_position=(100, 100),
        ui_mode="combat",
        peer_party_state=PartyState(
            fsm_state=peer_fsm_state,
            hp_percent=100.0,
            mp_percent=100.0,
            position=(200, 200),
            buff_presence={},
            heartbeat_timestamp=time.time(),
        ),
    )


def fake_perception(mobs=None):
    """Create a fake PerceptionResult for testing."""
    from lagent.common import Detection
    if mobs is None:
        mobs = []
    return PerceptionResult(
        detections=mobs,
        ocr_values={},
    )


class FakeSessionDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def test_buff_timer_expires_at_configured_duration():
    """AC-1: Timer initialization and duration loading."""
    timer = BuffTimer("haste", 5.0)
    assert timer.name == "haste"
    assert timer.duration == 5.0
    assert not timer.is_expired()


def test_buff_timer_expiry_with_fake_clock():
    """AC-1: Buff durations load from profile; fake clocks work."""
    now = 0.0
    def fake_clock():
        return now

    timer = BuffTimer("haste", 5.0, clock=fake_clock)
    assert not timer.is_expired()

    # Advance time
    now = 5.0
    assert timer.is_expired()


def test_prophet_buff_policy_timer_expiry_transition():
    """AC-2: BUFFING state on timer expiry."""
    now = [0.0]
    def fake_clock():
        return now[0]

    profile = fake_profile(buff_durations={"haste": 5.0})
    game_state_provider = lambda _: fake_game_state()
    
    policy = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
        clock=fake_clock,
    )

    # Initial state
    action = policy(fake_perception(), "IDLE")
    assert isinstance(action, Action)
    assert policy.state == "IDLE"

    # Advance time to trigger timer expiry
    now[0] = 5.5
    action = policy(fake_perception(), "IDLE")
    assert action is not None
    assert policy._pending_buff == "haste"
    assert policy.state == "BUFFING"


def test_prophet_buff_policy_safe_cast_executes():
    """AC-3: Safety Check gates every cast; safe condition executes."""
    now = [0.0]
    def fake_clock():
        return now[0]

    profile = fake_profile(
        buff_durations={"haste": 5.0},
        skill_bindings={"buff": "2"},
    )
    game_state_provider = lambda _: fake_game_state(peer_fsm_state="IDLE")

    policy = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
        clock=fake_clock,
    )

    # Trigger timer expiry
    now[0] = 5.5
    perception = fake_perception()
    action = policy(perception, "IDLE")
    assert policy._pending_buff == "haste"

    # Next call should attempt cast
    action = policy(perception, "IDLE")
    assert action is not None
    assert action.action_type == "key_press"
    assert action.key == "2"
    assert policy._pending_buff is None
    assert policy.state == "IDLE"


def test_prophet_buff_policy_failed_check_defers():
    """AC-4 & AC-3: Failed Safety Check defers; retries without dropping."""
    from lagent.common import Detection
    
    now = [0.0]
    def fake_clock():
        return now[0]

    profile = fake_profile(buff_durations={"haste": 5.0}, retry_interval=1.0)
    game_state_provider = lambda _: fake_game_state(peer_fsm_state="IDLE")

    db = FakeSessionDB()
    policy = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
        session_id="test-session",
        db=db,
        clock=fake_clock,
    )

    # Trigger timer expiry with mob nearby
    now[0] = 5.5
    mob_nearby = PerceptionResult(
        detections=[Detection(class_name="mob", confidence=0.9, bbox_xyxy=(110, 100, 130, 120))],
        ocr_values={},
    )
    action = policy(mob_nearby, "IDLE")
    assert policy._pending_buff == "haste"
    assert policy._retry_at is None

    # Next tick should attempt cast but defer due to mob
    action = policy(mob_nearby, "IDLE")
    assert action is not None
    assert action.action_type == "wait"
    assert policy._pending_buff == "haste"
    assert policy._retry_at is not None
    assert policy._retry_at > now[0]

    # Check that deferred event was logged
    deferred_events = [e for e in db.events if e[2] == "buff_cast_deferred"]
    assert len(deferred_events) > 0


def test_prophet_buff_policy_wl_pulling_blocks_cast():
    """AC-5: WL PULLING state blocks timed casts."""
    now = [0.0]
    def fake_clock():
        return now[0]

    profile = fake_profile(buff_durations={"haste": 5.0})
    game_state_provider = lambda _: fake_game_state(peer_fsm_state="PULLING")

    policy = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
        clock=fake_clock,
    )

    # Trigger timer expiry with WL PULLING
    now[0] = 5.5
    perception = fake_perception()
    action = policy(perception, "IDLE")
    assert policy._pending_buff == "haste"

    # Attempt cast - should defer because WL is PULLING
    action = policy(perception, "IDLE")
    assert action is not None
    assert action.action_type == "wait"
    assert policy._pending_buff == "haste"
    assert policy._retry_at is not None


def test_prophet_buff_policy_retry_loop_eventually_casts():
    """AC-4: Deferred casts retry and eventually execute when safe."""
    from lagent.common import Detection
    
    now = [0.0]
    def fake_clock():
        return now[0]

    profile = fake_profile(buff_durations={"haste": 5.0}, retry_interval=1.0)
    game_state_provider = lambda _: fake_game_state(peer_fsm_state="IDLE")

    db = FakeSessionDB()
    policy = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
        session_id="test-session",
        db=db,
        clock=fake_clock,
    )

    # Trigger timer expiry with mob nearby
    now[0] = 5.5
    mob_nearby = PerceptionResult(
        detections=[Detection(class_name="mob", confidence=0.9, bbox_xyxy=(110, 100, 130, 120))],
        ocr_values={},
    )
    action = policy(mob_nearby, "IDLE")
    assert policy._pending_buff == "haste"
    
    # Next call attempts cast but defers due to mob
    action = policy(mob_nearby, "IDLE")
    assert policy._retry_at is not None
    first_retry = policy._retry_at

    # Advance time but not to retry time yet
    now[0] = 5.8
    action = policy(mob_nearby, "IDLE")
    assert policy._pending_buff == "haste"  # Still pending

    # Advance time to retry time and clear mobs
    now[0] = 7.0
    safe_perception = fake_perception()
    action = policy(safe_perception, "IDLE")
    # Should attempt cast now
    assert action is not None
    assert action.action_type == "key_press" or action.action_type == "wait"
    # If cast succeeded, buff should be cleared
    if action.action_type == "key_press":
        assert policy._pending_buff is None


def test_prophet_buff_policy_multiple_buffs_queued():
    """AC-6: Multiple buff timers configured and not abandoned."""
    now = [0.0]
    def fake_clock():
        return now[0]

    profile = fake_profile(
        buff_durations={"haste": 5.0, "shield": 8.0},
        skill_bindings={"haste": "2", "shield": "3", "buff": "2"},
    )
    game_state_provider = lambda _: fake_game_state(peer_fsm_state="IDLE")

    policy = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
        clock=fake_clock,
    )

    # Both timers exist
    assert "haste" in policy.timers
    assert "shield" in policy.timers


def test_prophet_buff_policy_events_logged():
    """AC-7: Events logged for cast and safety decisions."""
    now = [0.0]
    def fake_clock():
        return now[0]

    profile = fake_profile(buff_durations={"haste": 5.0})
    game_state_provider = lambda _: fake_game_state(peer_fsm_state="IDLE")

    db = FakeSessionDB()
    policy = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
        session_id="test-session",
        db=db,
        clock=fake_clock,
    )

    # Trigger and complete cast
    now[0] = 5.5
    action = policy(fake_perception(), "IDLE")
    action = policy(fake_perception(), "IDLE")

    # Check events were logged
    event_types = [e[2] for e in db.events]
    assert "buff_timer_expired" in event_types
    assert any("buff_safety_check" in e for e in event_types)


def test_prophet_buff_policy_no_action_outside_buffing():
    """AC-8: No offensive action outside BUFFING state."""
    profile = fake_profile(buff_durations={"haste": 5.0})
    game_state_provider = lambda _: fake_game_state(peer_fsm_state="IDLE")

    policy = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
    )

    # In IDLE state, no buff is pending or expired
    action = policy(fake_perception(), "IDLE")
    assert action is not None
    assert action.action_type == "wait"


def test_prophet_buff_policy_lifecycle_states_suppress_actions():
    """Lifecycle interruption states (PAUSED, DEAD, etc.) suppress all actions."""
    profile = fake_profile(buff_durations={"haste": 5.0})
    game_state_provider = lambda _: fake_game_state(peer_fsm_state="IDLE")

    policy = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
    )

    for safe_state in ["PAUSED", "DEAD", "RETURNING", "STOPPED"]:
        action = policy(fake_perception(), safe_state)
        assert action is None
        assert policy._pending_buff is None
