from lagent.agent.lifecycle import (
    DeathRecoveryController,
    InventoryReturnController,
    SessionCapController,
    detect_lifecycle_signal,
)
from lagent.agent.prophet import ProphetBuffCycleFSM
from lagent.common import AgentProfile, Detection, GameState, PartyState, PerceptionResult


class DB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_lifecycle_signals_are_normalized():
    clock = Clock()
    result = PerceptionResult(detections=[Detection(class_name="death_screen", confidence=.9, bbox_xyxy=(0, 0, 1, 1))])

    signal = detect_lifecycle_signal(result, clock=clock)

    assert signal.name == "death_detected"
    assert signal.timestamp == 0.0


def test_death_recovery_is_idempotent_and_resumes_saved_state():
    clock = Clock()
    db = DB()
    recovery = DeathRecoveryController(
        profile={"recovery": {"actions": [{"action_type": "key_press", "key": "enter"}]}},
        session_id="s1", db=db, clock=clock,
    )

    assert recovery.begin("FIGHTING") is True
    assert recovery.begin("FIGHTING") is False
    assert recovery.next_action().key == "enter"
    assert recovery.next_action() is None
    assert recovery.complete() == "FIGHTING"
    assert len([event for event in db.events if event[2] == "death_detected"]) == 1


def test_inventory_return_authorizes_only_configured_dispositions():
    db = DB()
    controller = InventoryReturnController(
        profile={"inventory": {"deposit": ["ore"], "drop": ["junk"]}}, session_id="s1", db=db,
    )

    assert controller.begin() is True
    assert controller.begin() is False
    assert controller.dispose_loot("ore") == "deposit"
    assert controller.dispose_loot("junk") == "drop"
    assert controller.dispose_loot("unknown") == "retain"


def test_session_cap_is_monotonic_and_idempotent():
    clock = Clock()
    db = DB()
    cap = SessionCapController(10.0, clock=clock, session_id="s1", db=db)
    assert cap.expired() is False
    clock.now = 10.0
    assert cap.expired() is True
    assert cap.expired() is True
    assert len([event for event in db.events if event[2] == "session_cap_reached"]) == 1


def test_prophet_keeps_pending_buff_until_safety_check_passes():
    clock = Clock()
    profile = AgentProfile(
        name="prophet",
        skill_key_bindings={"haste": "2"},
        buff_timer_durations={"haste": 10.0},
        retry_interval=1.0,
    )
    peer = [PartyState(fsm_state="PULLING", hp_percent=100, mp_percent=100, position=(0, 0), heartbeat_timestamp=0)]

    def state_provider(_):
        return GameState(hp_percent=100, mp_percent=100, character_position=(0, 0), ui_mode="combat",
                         peer_party_state=peer[0])

    fsm = ProphetBuffCycleFSM(profile, state_provider, clock=clock)
    assert fsm(PerceptionResult(), "IDLE").action_type == "wait"
    clock.now = 10.0
    # Timer expires, setting pending buff
    assert fsm(PerceptionResult(), "IDLE").action_type == "wait"
    # Safety check fails because peer is PULLING, deferring cast until 11.0
    assert fsm(PerceptionResult(), "BUFFING").action_type == "wait"
    clock.now = 11.0
    peer[0] = PartyState(fsm_state="IDLE", hp_percent=100, mp_percent=100, position=(0, 0), heartbeat_timestamp=0)
    assert fsm(PerceptionResult(), "BUFFING").key == "2"
    assert fsm.next_state == "IDLE"