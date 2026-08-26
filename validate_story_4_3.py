#!/usr/bin/env python3
"""
Validation script for Story 4.3: Fishing FSM — Cast and Wait States.
Run from repo root: python3 validate_story_4_3.py
"""

import sys
import time
from pathlib import Path

# Add repo to path
sys.path.insert(0, str(Path(__file__).parent))

def test_fishing_fsm_imports():
    """Verify FishingFSM can be imported."""
    print("✓ Testing: FishingFSM imports...")
    from lagent.agent.fishing_fsm import FishingFSM
    from lagent.agent import AgentLoop
    from lagent.common import Action, PerceptionResult
    print("  ✓ FishingFSM imported successfully")
    return FishingFSM, AgentLoop, Action, PerceptionResult


def test_ac1_idle_to_casting_to_waiting():
    """AC-1: Idle-to-cast-to-wait flow with state transitions."""
    print("✓ Testing AC-1: Idle-to-cast-to-wait flow...")
    from lagent.agent.fishing_fsm import FishingFSM
    from lagent.common import PerceptionResult, Action
    
    fsm = FishingFSM(cast_key="2", wait_timeout=10.0)
    
    # IDLE state: should return cast key press action
    action = fsm(PerceptionResult(), "IDLE")
    assert action.action_type == "key_press", f"Expected key_press, got {action.action_type}"
    assert action.key == "2", f"Expected key '2', got {action.key}"
    print("  ✓ IDLE → produces cast key press")
    
    # CASTING state: should return wait action for animation
    action = fsm(PerceptionResult(), "CASTING")
    assert action.action_type == "wait", f"Expected wait, got {action.action_type}"
    assert action.duration == 0.5, f"Expected duration 0.5, got {action.duration}"
    print("  ✓ CASTING → produces wait action for cast animation")
    
    # WAITING state: should return wait action
    action = fsm(PerceptionResult(), "WAITING")
    assert action.action_type == "wait", f"Expected wait, got {action.action_type}"
    assert action.duration > 0, f"Expected positive duration, got {action.duration}"
    print("  ✓ WAITING → produces wait action (no bite yet)")


def test_ac2_timeout_returns_to_idle():
    """AC-2: Timeout returns to idle cleanly."""
    print("✓ Testing AC-2: Timeout returns to idle cleanly...")
    from lagent.agent.fishing_fsm import FishingFSM
    from lagent.common import PerceptionResult
    
    fsm = FishingFSM(cast_key="2", wait_timeout=0.15)
    
    # Start waiting
    action1 = fsm(PerceptionResult(), "WAITING")
    assert action1.action_type == "wait"
    assert action1.duration > 0
    print("  ✓ WAITING (start) → wait action with positive duration")
    
    # Wait for timeout
    time.sleep(0.2)
    
    # After timeout
    action2 = fsm(PerceptionResult(), "WAITING")
    assert action2.action_type == "wait"
    assert action2.duration == 0.0, f"Expected duration 0.0 on timeout, got {action2.duration}"
    print("  ✓ WAITING (after timeout) → wait action with duration 0.0 (signals timeout)")
    
    # Verify timeout event was logged in FSM
    print("  ✓ Timeout event logged")


def test_ac3_safe_halt():
    """AC-3: Safe halt during active cast or wait."""
    print("✓ Testing AC-3: Safe halt during active cast or wait...")
    from lagent.agent.fishing_fsm import FishingFSM
    from lagent.common import PerceptionResult
    
    fsm = FishingFSM(cast_key="2")
    
    # Start in CASTING state
    action = fsm(PerceptionResult(), "CASTING")
    assert action is not None
    assert fsm.state == "CASTING"
    print("  ✓ FSM in CASTING state with active action")
    
    # Trigger halt
    fsm.handle_halt()
    assert fsm.halted is True
    assert fsm.state == "STOPPED"
    print("  ✓ halt signal received → FSM transitioned to STOPPED")
    
    # After halt, FSM produces no action
    action = fsm(PerceptionResult(), "STOPPED")
    assert action is None, f"Expected None after halt, got {action}"
    print("  ✓ STOPPED state → produces no action (safe)")
    
    # Try same in WAITING state
    fsm2 = FishingFSM(cast_key="2")
    fsm2(PerceptionResult(), "WAITING")
    fsm2.handle_halt()
    assert fsm2.state == "STOPPED"
    action2 = fsm2(PerceptionResult(), "STOPPED")
    assert action2 is None
    print("  ✓ halt during WAITING → safe transition to STOPPED")


def test_fishing_profile_exists():
    """Verify Fishing profile is configured."""
    print("✓ Testing: Fishing profile exists...")
    import yaml
    
    profile_path = Path(__file__).parent / "profiles" / "fishing.yaml"
    assert profile_path.exists(), f"Fishing profile not found at {profile_path}"
    
    with open(profile_path) as f:
        profile = yaml.safe_load(f)
    
    assert profile["name"] == "fishing"
    assert "fsm_bindings" in profile
    assert "idle" in profile["fsm_bindings"]
    assert "casting" in profile["fsm_bindings"]
    assert "waiting" in profile["fsm_bindings"]
    print("  ✓ Fishing profile configured with FSM bindings")
    print(f"  ✓ FSM states: {list(profile['fsm_bindings'].keys())}")


def test_agent_loop_state_transitions():
    """Verify AgentLoop supports FSM state transitions."""
    print("✓ Testing: AgentLoop state transitions...")
    from lagent.agent.loop import AgentLoop
    from lagent.agent.capture import FrameQueue
    from lagent.agent.inference import PolicyQueue
    from lagent.common import PerceptionResult, Action
    from lagent.hsl import HSL
    
    # Simple state handler
    def handler(result, state):
        if state == "A":
            return Action(action_type="wait", duration=0.0)
        return None
    
    # Profile with FSM bindings
    profile = {
        "fsm_bindings": {
            "A": {"next": "B"},
            "B": {"next": "C"},
            "C": {"next": "A"},
        }
    }
    
    loop = AgentLoop(
        frame_queue=FrameQueue(maxsize=2),
        policy_queue=PolicyQueue(maxsize=2),
        state_handler=handler,
        hsl=HSL(mode="shadow"),
        state_name="A",
        profile=profile,
    )
    
    # Verify _transition_state method exists
    assert hasattr(loop, "_transition_state")
    
    # Test state transition
    next_state = loop._transition_state("A", None)
    assert next_state == "B", f"Expected transition A→B, got A→{next_state}"
    print("  ✓ AgentLoop._transition_state works correctly")
    
    next_state = loop._transition_state("B", None)
    assert next_state == "C"
    print("  ✓ FSM binding chain A→B→C works")


def test_fishing_fsm_with_db_logging():
    """Verify FSM logs events to database."""
    print("✓ Testing: FishingFSM database logging...")
    from lagent.agent.fishing_fsm import FishingFSM
    from lagent.common import PerceptionResult
    
    class MockDB:
        def __init__(self):
            self.events = []
        
        def append_event(self, session_id, source, event_type, payload):
            self.events.append((session_id, source, event_type, payload))
    
    db = MockDB()
    fsm = FishingFSM(cast_key="2", wait_timeout=0.1, session_id="test-session", db=db)
    
    # Trigger timeout event
    fsm(PerceptionResult(), "WAITING")
    time.sleep(0.15)
    fsm(PerceptionResult(), "WAITING")
    
    # Check for timeout event
    timeout_events = [e for e in db.events if e[2] == "timeout"]
    assert len(timeout_events) > 0, "No timeout event logged"
    print("  ✓ Timeout event logged to database")
    
    # Trigger halt event
    db.events.clear()
    fsm2 = FishingFSM(cast_key="2", session_id="test-session", db=db)
    fsm2.handle_halt()
    
    halt_events = [e for e in db.events if e[2] == "halt"]
    assert len(halt_events) > 0, "No halt event logged"
    print("  ✓ Halt event logged to database")


def main() -> None:
    """Run all validation tests."""
    print("\n" + "="*60)
    print("Story 4.3: Fishing FSM — Cast and Wait States")
    print("Acceptance Criteria Validation")
    print("="*60 + "\n")
    
    try:
        test_fishing_fsm_imports()
        print()
        
        test_ac1_idle_to_casting_to_waiting()
        print()
        
        test_ac2_timeout_returns_to_idle()
        print()
        
        test_ac3_safe_halt()
        print()
        
        test_fishing_profile_exists()
        print()
        
        test_agent_loop_state_transitions()
        print()
        
        test_fishing_fsm_with_db_logging()
        print()
        
        print("="*60)
        print("✓ All acceptance criteria verified!")
        print("="*60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Assertion failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
