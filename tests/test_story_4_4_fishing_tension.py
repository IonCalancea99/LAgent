"""Tests for Story 4.4: Fishing FSM tension detection and reel."""

from lagent.agent.fishing_fsm import FishingFSM
from lagent.agent.capture import Frame, FrameQueue
from lagent.agent.inference import PolicyQueue
from lagent.agent.loop import AgentLoop
from lagent.common import Detection, PerceptionResult
from lagent.hsl import HSL


class MockDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def test_tension_detection_reels_and_returns_to_idle():
    db = MockDB()
    fsm = FishingFSM(
        reel_key="3",
        session_id="session-1",
        db=db,
        clock=lambda: 100.0,
    )
    tension = PerceptionResult(
        detections=[Detection(class_name="tension_indicator", confidence=0.85, bbox_xyxy=(1, 2, 3, 4))]
    )

    waiting_action = fsm(tension, "WAITING")

    assert waiting_action.action_type == "wait"
    assert fsm.next_state == "REELING"
    assert waiting_action.duration == 0.0

    reel_action = fsm(tension, "REELING")

    assert reel_action.action_type == "key_press"
    assert reel_action.key == "3"
    assert fsm.next_state == "IDLE"
    tension_events = [event for event in db.events if event[2] == "tension_detected"]
    assert len(tension_events) == 1
    assert tension_events[0][3]["confidence"] == 0.85
    assert tension_events[0][3]["tension_window"] == 0.0


def test_reel_action_is_dispatched_through_hsl():
    fsm = FishingFSM(reel_key="3")
    frame_queue = FrameQueue(maxsize=2)
    policy_queue = PolicyQueue(maxsize=2)
    frame_queue.put_nowait(Frame("win", [1, 2, 3], 1, "src", 1.0))
    policy_queue.put_nowait(
        PerceptionResult(
            detections=[Detection(class_name="tension_indicator", confidence=0.85, bbox_xyxy=(1, 2, 3, 4))]
        )
    )
    hsl_calls = []
    hsl = HSL(mode="shadow")
    hsl.dispatch_action = lambda action, **kwargs: hsl_calls.append(action)
    loop = AgentLoop(
        frame_queue=frame_queue,
        policy_queue=policy_queue,
        state_handler=fsm,
        hsl=hsl,
        state_name="REELING",
        profile={"fsm_bindings": {"REELING": {"next": "IDLE"}}},
    )

    loop.tick()

    assert len(hsl_calls) == 1
    assert hsl_calls[0].action_type == "key_press"
    assert hsl_calls[0].key == "3"


def test_low_confidence_tension_times_out_and_logs_missed_bite():
    db = MockDB()
    current_time = [10.0]
    fsm = FishingFSM(
        wait_timeout=5.0,
        session_id="session-1",
        db=db,
        clock=lambda: current_time[0],
    )
    low_confidence = PerceptionResult(
        detections=[Detection(class_name="tension_indicator", confidence=0.79, bbox_xyxy=(1, 2, 3, 4))]
    )

    fsm(low_confidence, "WAITING")
    current_time[0] = 15.1
    timeout_action = fsm(low_confidence, "WAITING")

    assert timeout_action.duration == 0.0
    assert fsm.next_state == "IDLE"
    missed_events = [event for event in db.events if event[2] == "missed_tension"]
    assert len(missed_events) == 1
    assert missed_events[0][3]["confidence"] == 0.79
    assert missed_events[0][3]["timeout"] is True


def test_seeded_replay_is_deterministic():
    sequence = [
        ("IDLE", 0.0, 0.0),
        ("CASTING", 0.1, 0.0),
        ("WAITING", 0.2, 0.81),
        ("REELING", 0.3, 0.81),
        ("IDLE", 0.4, 0.0),
        ("CASTING", 0.5, 0.0),
        ("WAITING", 0.6, 0.80),
        ("REELING", 0.7, 0.80),
    ]

    def replay():
        db = MockDB()
        fsm = FishingFSM(session_id="session-1", db=db, clock=lambda: 1.0)
        actions = []
        transitions = []
        for state, _, confidence in sequence:
            result = PerceptionResult(
                detections=(
                    [Detection(class_name="tension_indicator", confidence=confidence, bbox_xyxy=(1, 2, 3, 4))]
                    if confidence
                    else []
                )
            )
            action = fsm(result, state)
            actions.append((action.action_type, action.key, action.duration))
            transitions.append(fsm.next_state)
        return actions, transitions

    assert replay() == replay()