"""Tests for Story 4.3: Fishing FSM — Cast and Wait States."""

import time

from lagent.agent.fishing_fsm import FishingFSM
from lagent.agent.loop import AgentLoop
from lagent.agent.capture import Frame, FrameQueue
from lagent.agent.inference import PolicyQueue
from lagent.common import Action, PerceptionResult
from lagent.hsl import HSL


class MockDB:
    """Mock sessions database for testing."""

    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def test_idle_to_casting_to_waiting_flow():
    """AC-1: Idle-to-cast-to-wait flow with FSM transitions."""
    db = MockDB()
    fsm = FishingFSM(cast_key="2", session_id="session-1", db=db)
    
    frame_queue = FrameQueue(maxsize=2)
    frame_queue.put_nowait(Frame("win", [1, 2, 3], 1, "src", time.time()))
    policy_queue = PolicyQueue(maxsize=2)
    policy_queue.put_nowait(PerceptionResult(ocr_values={"hp": "99%"}))

    hsl_calls = []
    def mock_dispatch_action(action, **kwargs):
        hsl_calls.append(action)
    
    hsl = HSL(mode="shadow")
    hsl.dispatch_action = mock_dispatch_action

    # Fishing profile with FSM bindings
    fishing_profile = {
        "fsm_bindings": {
            "IDLE": {"next": "CASTING", "cast_key": "2"},
            "CASTING": {"next": "WAITING", "cast_duration": 0.5},
            "WAITING": {"next": "IDLE", "wait_timeout": 10.0},
        },
    }

    # AC-1: Start in IDLE state
    loop = AgentLoop(
        frame_queue=frame_queue,
        policy_queue=policy_queue,
        state_handler=fsm,
        hsl=hsl,
        state_name="IDLE",
        profile=fishing_profile,
        session_id="session-1",
        db=db,
    )

    # First tick: IDLE → CASTING
    tick1 = loop.tick()
    
    # Verify IDLE state produced cast key press action
    assert len(hsl_calls) == 1
    assert hsl_calls[0].action_type == "key_press"
    assert hsl_calls[0].key == "2"
    assert tick1["state"] == "IDLE"  # Tick reports current state before transition
    
    # Verify state was transitioned to CASTING for next tick
    assert loop.state_name == "CASTING"
    
    # Verify FSM transition was logged
    transition_events = [e for e in db.events if e[2] == "state_transition"]
    assert len(transition_events) == 1
    assert transition_events[0][3]["from"] == "IDLE"
    assert transition_events[0][3]["to"] == "CASTING"


def test_wait_state_timeout_returns_to_idle_cleanly():
    """AC-2: Timeout returns to idle cleanly."""
    db = MockDB()
    fsm = FishingFSM(cast_key="2", wait_timeout=0.2, session_id="session-1", db=db)
    
    result = PerceptionResult(ocr_values={"hp": "99%"})
    
    # First call: start waiting
    action1 = fsm(result, "WAITING")
    assert action1.action_type == "wait"
    assert action1.duration > 0  # Waiting duration
    
    # Wait for timeout to elapse
    time.sleep(0.25)
    
    # Second call after timeout: should signal timeout
    action2 = fsm(result, "WAITING")
    assert action2.action_type == "wait"
    assert action2.duration == 0.0  # Timeout signal
    
    # Verify timeout event logged
    timeout_events = [e for e in db.events if e[2] == "timeout"]
    assert len(timeout_events) == 1
    assert timeout_events[0][3]["wait_timeout"] == 0.2


def test_safe_halt_during_casting_or_waiting():
    """AC-3: Safe halt during active cast or wait."""
    db = MockDB()
    fsm = FishingFSM(cast_key="2", wait_timeout=10.0, session_id="session-1", db=db)
    
    result = PerceptionResult(ocr_values={"hp": "99%"})
    
    # Start in CASTING state
    action1 = fsm(result, "CASTING")
    assert action1 is not None
    
    # AC-3: Trigger halt signal
    fsm.handle_halt()
    assert fsm.halted is True
    assert fsm.state == "STOPPED"
    
    # Verify halt event logged
    halt_events = [e for e in db.events if e[2] == "halt"]
    assert len(halt_events) == 1
    assert halt_events[0][3]["reason"] == "user_interrupt"
    
    # After halt, FSM produces no action (safely abandoned)
    action_after_halt = fsm(result, "STOPPED")
    assert action_after_halt is None


def test_casting_executes_rod_cast_key_sequence_via_hsl():
    """AC-1 detail: Rod cast key sequence executed via HSL."""
    db = MockDB()
    fsm = FishingFSM(cast_key="2", session_id="session-1", db=db)
    
    frame_queue = FrameQueue(maxsize=2)
    frame_queue.put_nowait(Frame("win", [1, 2, 3], 1, "src", time.time()))
    policy_queue = PolicyQueue(maxsize=2)
    policy_queue.put_nowait(PerceptionResult(ocr_values={"hp": "99%"}))

    hsl_calls = []
    def mock_dispatch_action(action, **kwargs):
        hsl_calls.append(action)
    
    hsl = HSL(mode="shadow")
    hsl.dispatch_action = mock_dispatch_action

    loop = AgentLoop(
        frame_queue=frame_queue,
        policy_queue=policy_queue,
        state_handler=fsm,
        hsl=hsl,
        state_name="IDLE",
        profile={"skill_timing": {"cast": {"mean": 0.2, "std": 0.05}}},
        session_id="session-1",
        db=db,
    )

    tick = loop.tick()
    
    # Verify HSL received the cast key press
    assert len(hsl_calls) == 1
    cast_action = hsl_calls[0]
    assert cast_action.action_type == "key_press"
    assert cast_action.key == "2"


def test_fishing_fsm_state_transitions_via_loop():
    """Integration: FSM state transitions logged and verified."""
    db = MockDB()
    fsm = FishingFSM(cast_key="2", wait_timeout=10.0, session_id="session-1", db=db)
    
    frame_queue = FrameQueue(maxsize=2)
    frame_queue.put_nowait(Frame("win", [1, 2, 3], 1, "src", time.time()))
    policy_queue = PolicyQueue(maxsize=2)
    policy_queue.put_nowait(PerceptionResult(ocr_values={"hp": "99%"}))

    hsl = HSL(mode="shadow")
    
    fishing_profile = {
        "fsm_bindings": {
            "IDLE": {"next": "CASTING"},
            "CASTING": {"next": "WAITING"},
            "WAITING": {"next": "IDLE"},
        },
    }
    
    loop = AgentLoop(
        frame_queue=frame_queue,
        policy_queue=policy_queue,
        state_handler=fsm,
        hsl=hsl,
        state_name="IDLE",
        profile=fishing_profile,
        session_id="session-1",
        db=db,
    )

    tick = loop.tick()
    
    # Verify tick was logged
    tick_events = [e for e in db.events if e[2] == "tick"]
    assert len(tick_events) == 1
    assert tick_events[0][3]["state"] == "IDLE"
    
    # Verify state transitioned
    assert loop.state_name == "CASTING"


def test_timeout_event_logged_when_wait_exceeds_threshold():
    """AC-2 detail: Timeout event logged."""
    db = MockDB()
    fsm = FishingFSM(cast_key="2", wait_timeout=0.1, session_id="session-1", db=db)
    
    result = PerceptionResult(ocr_values={"hp": "99%"})
    
    # Start waiting
    action1 = fsm(result, "WAITING")
    assert action1.action_type == "wait"
    assert action1.duration > 0  # Still waiting
    
    # Simulate timeout elapsed
    time.sleep(0.15)
    
    # Next action after timeout
    action2 = fsm(result, "WAITING")
    assert action2.action_type == "wait"
    assert action2.duration == 0.0  # Timeout signal
    
    # Verify timeout event was logged
    timeout_events = [e for e in db.events if e[2] == "timeout"]
    assert len(timeout_events) == 1
    assert "elapsed" in timeout_events[0][3]


def test_fishing_fsm_transitions_idle_to_casting_to_waiting_to_idle_cycle():
    """AC-1 & AC-2 integration: Full fishing cycle with timeout."""
    db = MockDB()
    fsm = FishingFSM(cast_key="2", wait_timeout=0.2, session_id="session-1", db=db)
    
    fishing_profile = {
        "fsm_bindings": {
            "IDLE": {"next": "CASTING"},
            "CASTING": {"next": "WAITING"},
            "WAITING": {"next": "IDLE"},
        },
    }
    
    # Tick 1: IDLE → CASTING (cast)
    action1 = fsm(PerceptionResult(), "IDLE")
    assert action1.action_type == "key_press"
    assert action1.key == "2"
    
    # Tick 2: CASTING → WAITING
    action2 = fsm(PerceptionResult(), "CASTING")
    assert action2.action_type == "wait"
    assert action2.duration == 0.5  # Cast animation
    
    # Tick 3-5: WAITING → wait for bite
    time.sleep(0.05)
    action3 = fsm(PerceptionResult(), "WAITING")
    assert action3.action_type == "wait"
    assert action3.duration > 0  # Still waiting
    
    # Tick N: WAITING → timeout → IDLE
    time.sleep(0.2)
    action_timeout = fsm(PerceptionResult(), "WAITING")
    assert action_timeout.action_type == "wait"
    assert action_timeout.duration == 0.0  # Timeout signal
    
    # Verify timeout was logged
    timeout_events = [e for e in db.events if e[2] == "timeout"]
    assert len(timeout_events) == 1
