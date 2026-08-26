import pytest

from lagent.agent.capture import Frame, FrameQueue
from lagent.agent.inference import PolicyQueue
from lagent.agent.loop import AgentLoop
from lagent.agent.warlord import WarlordCombatFSM
from lagent.common import Detection, PerceptionResult
from lagent.hsl import HSL


class FakeDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


class FakePartyBus:
    def __init__(self):
        self.states = []

    def publish_state(self, state):
        self.states.append(state)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def perception(*classes):
    return PerceptionResult(
        detections=[
            Detection(class_name=name, confidence=0.9, bbox_xyxy=bbox)
            for name, bbox in classes
        ]
    )


@pytest.fixture
def profile():
    return {
        "fsm_bindings": {
            "idle": {},
            "pulling": {},
            "fighting": {},
            "looting": {"loot_timeout": 2.0},
        },
        "skill_key_bindings": {
            "pull": "7",
            "aoe": "8",
            "loot": "f",
        },
    }


def test_warlord_completes_pull_fight_loot_cycle(profile):
    db = FakeDB()
    bus = FakePartyBus()
    clock = FakeClock()
    fsm = WarlordCombatFSM(profile=profile, session_id="s1", db=db, party_bus=bus, clock=clock)

    assert fsm(perception(), "IDLE").action_type == "wait"
    assert fsm.state == "IDLE"

    pull = fsm(perception(("mob", (400, 400, 440, 440))), "IDLE")
    assert (pull.action_type, pull.key) == ("key_press", "7")
    assert fsm.next_state == "PULLING"

    fight = fsm(perception(("mob", (495, 495, 505, 505))), "PULLING")
    assert (fight.action_type, fight.key) == ("key_press", "8")
    assert fsm.next_state == "FIGHTING"

    loot = fsm(perception(), "FIGHTING")
    assert (loot.action_type, loot.key) == ("key_press", "f")
    assert fsm.next_state == "LOOTING"

    done = fsm(perception(), "LOOTING")
    assert done.action_type == "wait"
    assert fsm.next_state == "IDLE"
    transitions = [event for event in db.events if event[2] == "state_transition"]
    assert [(event[3]["from"], event[3]["to"]) for event in transitions] == [
        ("IDLE", "PULLING"),
        ("PULLING", "FIGHTING"),
        ("FIGHTING", "LOOTING"),
        ("LOOTING", "IDLE"),
    ]
    assert [state["fsm_state"] for state in bus.states] == ["PULLING", "FIGHTING", "LOOTING", "IDLE"]


def test_loot_timeout_returns_to_idle(profile):
    clock = FakeClock()
    fsm = WarlordCombatFSM(profile=profile, clock=clock)
    fsm(perception(("loot", (100, 100, 120, 120))), "LOOTING")
    clock.now = 2.1

    action = fsm(perception(("loot", (100, 100, 120, 120))), "LOOTING")

    assert action.action_type == "wait"
    assert fsm.next_state == "IDLE"


def test_lifecycle_states_emit_no_combat_action(profile):
    fsm = WarlordCombatFSM(profile=profile)
    result = perception(("mob", (400, 400, 440, 440)))

    for state in ("PAUSED", "DEAD", "RETURNING", "STOPPED"):
        assert fsm(result, state) is None


def test_loop_dispatches_warlord_action_through_hsl(profile):
    fsm = WarlordCombatFSM(profile=profile)
    frames = FrameQueue(maxsize=1)
    policies = PolicyQueue(maxsize=1)
    frames.put_nowait(Frame("win", [], 1, "test", 0.0))
    policies.put_nowait(perception(("mob", (400, 400, 440, 440))))
    actions = []
    hsl = HSL(mode="shadow")
    hsl.dispatch_action = lambda action, **kwargs: actions.append(action)

    loop = AgentLoop(
        frame_queue=frames,
        policy_queue=policies,
        state_handler=fsm,
        hsl=hsl,
        state_name="IDLE",
        profile=profile,
    )

    loop.tick()

    assert [(action.action_type, action.key) for action in actions] == [("key_press", "7")]
    assert loop.state_name == "PULLING"