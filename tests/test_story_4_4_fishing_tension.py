"""Tests for Story 4.4: temporal fishing Pump/Reel control."""

import math

import pytest

from lagent.agent.fishing_fsm import FishingFSM
from lagent.agent.capture import Frame, FrameQueue
from lagent.agent.inference import PolicyQueue
from lagent.agent.loop import AgentLoop
from lagent.agent.profile import load_profile
from lagent.common import Detection, PerceptionResult
from lagent.hsl import HSL


class MockDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def tension(width: int, confidence: float = 0.90) -> PerceptionResult:
    return PerceptionResult(
        detections=[
            Detection(
                class_name="tension_indicator",
                confidence=confidence,
                bbox_xyxy=(10, 20, 10 + width, 30),
            )
        ]
    )


def test_rising_fill_reels_once_and_keeps_fight_active():
    db = MockDB()
    fsm = FishingFSM(
        reel_key="3",
        observation_window=3,
        trend_tolerance=0.03,
        action_cooldown=0.0,
        session_id="session-1",
        db=db,
        clock=lambda: 100.0,
    )
    assert fsm(tension(50), "WAITING").action_type == "wait"
    assert fsm(tension(60), "WAITING").action_type == "wait"

    action = fsm(tension(70), "WAITING")

    assert action.action_type == "key_press"
    assert action.key == "3"
    assert fsm.next_state == "WAITING"
    trend_event = [event for event in db.events if event[2] == "tension_trend"][-1]
    assert trend_event[3]["trend"] == "rising"
    assert trend_event[3]["selected_action"] == "reel"


def test_slight_cumulative_regeneration_reels_despite_small_frame_deltas():
    fsm = FishingFSM(observation_window=3, trend_tolerance=0.03, action_cooldown=0.0)
    fsm(tension(100), "WAITING")
    fsm(tension(102), "WAITING")

    action = fsm(tension(104), "WAITING")

    assert action.action_type == "key_press"
    assert action.key == "3"


def test_steady_fill_pumps_once_and_keeps_fight_active():
    fsm = FishingFSM(pump_key="4", observation_window=3, trend_tolerance=0.03, action_cooldown=0.0)
    fsm(tension(100), "WAITING")
    fsm(tension(101), "WAITING")

    action = fsm(tension(99), "WAITING")

    assert action.action_type == "key_press"
    assert action.key == "4"
    assert fsm.next_state == "WAITING"


def test_falling_fill_suppresses_action_until_fresh_stable_window():
    fsm = FishingFSM(observation_window=3, trend_tolerance=0.03, action_cooldown=0.0)
    for width in (50, 60):
        fsm(tension(width), "WAITING")
    assert fsm(tension(70), "WAITING").key == "3"

    falling_actions = [fsm(tension(width), "WAITING") for width in (60, 50, 40)]
    stable_actions = [fsm(tension(width), "WAITING") for width in (40, 40, 40)]

    assert all(action.action_type == "wait" for action in falling_actions)
    assert stable_actions[-1].action_type == "key_press"
    assert stable_actions[-1].key == "4"


def test_insufficient_mixed_and_low_confidence_evidence_waits_without_input():
    fsm = FishingFSM(observation_window=3, trend_tolerance=0.03, wait_timeout=10.0)

    actions = [
        fsm(tension(50), "WAITING"),
        fsm(tension(60), "WAITING"),
        fsm(tension(50), "WAITING"),
        fsm(tension(70, confidence=0.79), "WAITING"),
    ]

    assert all(action.action_type == "wait" for action in actions)
    assert fsm.next_state == "WAITING"


def test_low_confidence_frame_breaks_consecutive_observation_window():
    fsm = FishingFSM(observation_window=3, action_cooldown=0.0)
    fsm(tension(50), "WAITING")
    fsm(tension(60), "WAITING")
    fsm(tension(70, confidence=0.79), "WAITING")

    action = fsm(tension(70), "WAITING")

    assert action.action_type == "wait"
    assert fsm.observed_widths == (70.0,)


def test_action_cooldown_suppresses_an_otherwise_actionable_window():
    now = [10.0]
    fsm = FishingFSM(observation_window=3, action_cooldown=2.0, clock=lambda: now[0])
    for width in (50, 60):
        fsm(tension(width), "WAITING")
    assert fsm(tension(70), "WAITING").action_type == "key_press"

    now[0] = 11.0
    cooldown_actions = [fsm(tension(40), "WAITING") for _ in range(3)]
    now[0] = 12.1
    permitted_actions = [fsm(tension(40), "WAITING") for _ in range(3)]

    assert all(action.action_type == "wait" for action in cooldown_actions)
    assert permitted_actions[-1].key == "4"


def test_seen_gauge_disappearance_completes_fight_after_configured_count():
    db = MockDB()
    fsm = FishingFSM(disappearance_count=2, session_id="session-1", db=db, clock=lambda: 1.0)
    fsm(tension(50), "WAITING")

    first_absence = fsm(PerceptionResult(), "WAITING")
    completion = fsm(PerceptionResult(), "WAITING")

    assert first_absence.duration > 0
    assert completion.duration == 0.0
    assert fsm.next_state == "IDLE"
    assert [event[2] for event in db.events].count("fight_complete") == 1
    assert fsm.observed_widths == ()


def test_uncertain_or_malformed_gauge_evidence_does_not_complete_fight():
    fsm = FishingFSM(disappearance_count=2, action_cooldown=0.0)
    fsm(tension(50), "WAITING")

    low_confidence = tension(50, confidence=0.79)
    malformed = PerceptionResult(
        detections=[Detection(class_name="tension_indicator", confidence=0.95, bbox_xyxy=(10, 20, 10, 30))]
    )

    assert fsm(low_confidence, "WAITING").duration > 0
    assert fsm(malformed, "WAITING").duration > 0
    assert fsm.next_state == "WAITING"


def test_valid_detection_wins_when_higher_confidence_match_is_malformed():
    fsm = FishingFSM(observation_window=3, action_cooldown=0.0)
    result = PerceptionResult(
        detections=[
            Detection(class_name="tension_indicator", confidence=0.99, bbox_xyxy=(10, 20, 10, 30)),
            Detection(class_name="tension_indicator", confidence=0.90, bbox_xyxy=(10, 20, 60, 30)),
        ]
    )

    assert fsm(result, "WAITING").action_type == "wait"
    assert fsm.observed_widths == (50.0,)


def test_reel_action_is_dispatched_through_hsl_without_leaving_waiting():
    fsm = FishingFSM(observation_window=3, action_cooldown=0.0)
    fsm(tension(50), "WAITING")
    fsm(tension(60), "WAITING")
    frame_queue = FrameQueue(maxsize=2)
    policy_queue = PolicyQueue(maxsize=2)
    frame_queue.put_nowait(Frame("win", [1, 2, 3], 1, "src", 1.0))
    policy_queue.put_nowait(tension(70))
    hsl_calls = []
    hsl = HSL(mode="shadow")
    hsl.dispatch_action = lambda action, **kwargs: hsl_calls.append(action)
    loop = AgentLoop(
        frame_queue=frame_queue,
        policy_queue=policy_queue,
        state_handler=fsm,
        hsl=hsl,
        state_name="WAITING",
        profile={"fsm_bindings": {"WAITING": {"next": "WAITING"}}},
    )

    loop.tick()

    assert [(action.action_type, action.key) for action in hsl_calls] == [("key_press", "3")]
    assert loop.state_name == "WAITING"


def test_low_confidence_gauge_times_out_through_missed_tension_path():
    db = MockDB()
    now = [10.0]
    fsm = FishingFSM(
        wait_timeout=5.0,
        session_id="session-1",
        db=db,
        clock=lambda: now[0],
    )
    fsm(tension(50, confidence=0.79), "WAITING")
    now[0] = 15.1

    timeout_action = fsm(tension(50, confidence=0.79), "WAITING")

    assert timeout_action.duration == 0.0
    assert fsm.next_state == "IDLE"
    missed_event = [event for event in db.events if event[2] == "missed_tension"][-1]
    assert missed_event[3]["confidence"] == 0.79
    assert missed_event[3]["timeout"] is True


def test_confident_gauge_arriving_after_wait_deadline_is_a_missed_bite():
    now = [10.0]
    fsm = FishingFSM(wait_timeout=5.0, clock=lambda: now[0])
    fsm(PerceptionResult(), "WAITING")
    now[0] = 15.1

    action = fsm(tension(50), "WAITING")

    assert action.duration == 0.0
    assert fsm.next_state == "IDLE"


def test_seen_gauge_uses_fight_timeout_without_logging_missed_tension():
    db = MockDB()
    now = [10.0]
    fsm = FishingFSM(
        fight_timeout=5.0,
        disappearance_count=10,
        session_id="session-1",
        db=db,
        clock=lambda: now[0],
    )
    fsm(tension(50), "WAITING")
    now[0] = 15.1

    timeout_action = fsm(tension(50), "WAITING")

    assert timeout_action.duration == 0.0
    assert fsm.next_state == "IDLE"
    assert not [event for event in db.events if event[2] == "missed_tension"]
    timeout_event = [event for event in db.events if event[2] == "timeout"][-1]
    assert timeout_event[3]["reason"] == "fight_timeout"


def test_profile_defaults_supply_temporal_policy_and_skill_keys():
    fsm = FishingFSM(profile=load_profile("fishing"))

    assert fsm.pump_key == "4"
    assert fsm.reel_key == "3"
    assert fsm.observation_window == 3
    assert fsm.trend_tolerance == 0.03
    assert fsm.action_cooldown == 0.5
    assert fsm.disappearance_count == 3
    assert fsm.fight_timeout == 30.0


def test_original_positional_constructor_arguments_remain_compatible():
    fsm = FishingFSM("2", "3", 5.0)

    assert fsm.cast_key == "2"
    assert fsm.reel_key == "3"
    assert fsm.wait_timeout == 5.0
    assert fsm.pump_key == "4"


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("trend_tolerance", math.nan),
        ("trend_tolerance", 1.0),
        ("action_cooldown", math.inf),
        ("fight_timeout", math.inf),
    ],
)
def test_invalid_temporal_policy_values_are_rejected(argument, value):
    with pytest.raises(ValueError):
        FishingFSM(**{argument: value})


def test_seeded_replay_is_deterministic():
    sequence = [50, 60, 70, 60, 50, 40, None, None]

    def replay():
        now = [1.0]
        db = MockDB()
        fsm = FishingFSM(
            observation_window=3,
            action_cooldown=0.0,
            disappearance_count=2,
            session_id="session-1",
            db=db,
            clock=lambda: now[0],
        )
        actions = []
        transitions = []
        for width in sequence:
            result = tension(width) if width is not None else PerceptionResult()
            action = fsm(result, "WAITING")
            actions.append((action.action_type, action.key, action.duration))
            transitions.append(fsm.next_state)
            now[0] += 0.1
        return actions, transitions, db.events

    assert replay() == replay()