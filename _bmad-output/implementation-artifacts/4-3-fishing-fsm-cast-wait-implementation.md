# Story 4.3 Implementation Summary: Fishing FSM — Cast and Wait States

## Overview

Story 4.3 implements the first half of the Fishing Mode FSM with deterministic state transitions: **IDLE → CASTING → WAITING**, plus timeout handling and safe halt support. This lays the groundwork for the full fishing loop in Story 4.4.

---

## Acceptance Criteria & Implementation

### AC-1: Idle-to-Cast-to-Wait Flow

**Requirement:** Given the Agent is in IDLE with Fishing Mode profile loaded, when FSM tick runs, then transition to CASTING, execute rod cast key via HSL, transition to WAITING.

**Implementation:**

1. **FishingFSM State Handler** (`lagent/agent/fishing_fsm.py`)
   - `IDLE` state: Returns `Action(action_type="key_press", key=cast_key)` 
   - `CASTING` state: Returns `Action(action_type="wait", duration=0.5)` for cast animation
   - `WAITING` state: Returns `Action(action_type="wait", duration=wait_remaining)` until timeout

2. **FSM Bindings** (`profiles/fishing.yaml`)
   ```yaml
   fsm_bindings:
     idle:
       next: casting
       cast_key: "2"
     casting:
       next: waiting
       cast_duration: 0.5
     waiting:
       next: idle
       wait_timeout: 10.0
   ```

3. **AgentLoop State Transitions** (`lagent/agent/loop.py`)
   - Added `_transition_state(from_state, action)` method
   - After each tick's HSL dispatch, checks FSM bindings for next state
   - Logs state transitions to sessions_db
   - Automatically transitions: IDLE → CASTING → WAITING in successive ticks

**Data Flow:**
```
Tick 1: IDLE state → IDLE action (cast key) → [log tick] → [transition to CASTING]
Tick 2: CASTING state → CASTING action (wait 0.5s) → [log tick] → [transition to WAITING]
Tick 3+: WAITING state → WAITING action (wait N seconds) → [log tick] → [stay WAITING or timeout]
```

---

### AC-2: Timeout Returns to Idle Cleanly

**Requirement:** Given FSM in WAITING, when no bite event within timeout, then transition to IDLE cleanly, log timeout event, next tick begins new cast cycle.

**Implementation:**

1. **Timeout Tracking** (`fishing_fsm.py`)
   ```python
   if state_name == "WAITING":
       if self.wait_started_at is None:
           self.wait_started_at = time.time()
       
       elapsed = time.time() - self.wait_started_at
       remaining = self.wait_timeout - elapsed
       
       if remaining <= 0:
           # Timeout: return to IDLE
           self._log_event("timeout", {"wait_timeout": self.wait_timeout, "elapsed": elapsed})
           self.wait_started_at = None
           return Action(action_type="wait", duration=0.0)
   ```

2. **Event Logging**
   - FSM calls `self._log_event("timeout", {...})` when timeout occurs
   - Event stored in `sessions_db` for operational review
   - Next tick: AgentLoop transitions WAITING → IDLE via profile bindings

3. **Timeout Signal**
   - FSM returns `wait(duration=0.0)` to signal timeout condition
   - AgentLoop recognizes this and transitions state normally
   - No explicit "return to IDLE" call needed—automatic via profile

---

### AC-3: Safe Halt During Active Cast or Wait

**Requirement:** Given FSM in CASTING or WAITING, when session halt signal received, then abandon current state safely, transition to stopped state, produce no further input.

**Implementation:**

1. **Halt Signal Handler** (`fishing_fsm.py`)
   ```python
   def handle_halt(self) -> None:
       """AC-3: Handle halt signal. Abandon current state safely."""
       logger.info("Fishing FSM halt signal received at state %s", self.state)
       self._log_event("halt", {"reason": "user_interrupt"})
       self.halted = True
       self.state = "STOPPED"
   ```

2. **Stopped State Behavior**
   ```python
   if self.halted or state_name == "STOPPED":
       logger.debug("FSM in STOPPED state; no action produced")
       return None
   ```
   - In `STOPPED`, FSM returns `None` (not an Action)
   - AgentLoop converts `None` to `wait(duration=0.0)` (safe idle)
   - No further input produced; state machine halted

3. **External Integration**
   - Session controller can call `fsm.handle_halt()` to trigger halt
   - Halt event logged immediately
   - Example: `if user_interrupt_signal: fsm.handle_halt()`

---

## Key Design Decisions

### 1. **Profile-Based State Transitions**
- FSM bindings defined in YAML (not hardcoded)
- AgentLoop reads bindings and transitions automatically
- Enables hot-reload and per-class customization

### 2. **Timeout Tracking in FSM**
- FSM maintains `wait_started_at` timestamp
- Returns `wait(duration=0.0)` as timeout signal
- Loop recognizes and transitions naturally
- Avoids callback complexity

### 3. **DB Event Logging**
- State transitions, timeouts, and halts logged to `sessions_db`
- Provides audit trail for debugging and analysis
- Tick payloads include FSM state for full context

### 4. **Safe Halt via State Machine**
- Halt signal sets `halted=True` and transitions to `STOPPED`
- `STOPPED` state explicitly returns `None` (no action)
- Prevents accidental action dispatch after halt

---

## File Structure

```
lagent/
  agent/
    fishing_fsm.py              # FishingFSM class (134 lines)
    loop.py                     # Modified with _transition_state() 
    __init__.py                 # Exports FishingFSM

profiles/
  fishing.yaml                  # Fishing profile with FSM bindings

tests/
  test_story_4_3_fishing.py     # 9 acceptance criteria tests (274 lines)

validate_story_4_3.py           # Validation script (260 lines)
```

---

## Testing

### Unit Tests (`test_story_4_3_fishing.py`)
1. `test_idle_to_casting_to_waiting_flow()` — AC-1: state transitions
2. `test_wait_state_timeout_returns_to_idle_cleanly()` — AC-2: timeout handling
3. `test_safe_halt_during_casting_or_waiting()` — AC-3: halt signal
4. `test_casting_executes_rod_cast_key_sequence_via_hsl()` — AC-1 detail: HSL dispatch
5. `test_fishing_fsm_state_transitions_via_loop()` — AC-1 integration: loop transitions
6. `test_timeout_event_logged_when_wait_exceeds_threshold()` — AC-2 detail: event logging
7. `test_fishing_fsm_transitions_idle_to_casting_to_waiting_to_idle_cycle()` — Full cycle

### Validation Script (`validate_story_4_3.py`)
- Imports and instantiation checks
- AC-1, AC-2, AC-3 acceptance criteria verification
- Fishing profile validation
- AgentLoop state transition testing
- Database logging integration

**Run validation:** `python3 validate_story_4_3.py`

---

## Dependencies & Prerequisites

- **Pydantic v2.11+** — For Action/PerceptionResult validation
- **PyYAML** — For profile loading
- **lagent.common** — Action, PerceptionResult types
- **lagent.agent.loop** — AgentLoop with state transition support
- **lagent.hsl** — HSL for key dispatch

---

## Integration with Story 4.4

Story 4.3 provides the deterministic baseline (cast → wait → timeout) that Story 4.4 extends with:
- Tension detection (YOLO-based bite event)
- Reel execution (REELING state)
- Reel completion → IDLE transition

The FSM structure and bindings remain compatible; 4.4 adds new states and transitions without changing the 4.3 logic.

---

## Logging & Observability

### Event Types Logged
- `state_transition` — FSM state change
- `timeout` — Timeout event with elapsed time
- `halt` — Halt signal with reason
- `tick` — Full tick payload (already in Story 4.1)

### Example Event Log
```json
{
  "session_id": "session-1",
  "source": "fsm",
  "type": "state_transition",
  "payload": {"from": "IDLE", "to": "CASTING", "state": "IDLE"}
}
{
  "session_id": "session-1",
  "source": "fsm",
  "type": "timeout",
  "payload": {"wait_timeout": 10.0, "elapsed": 10.05, "state": "WAITING"}
}
{
  "session_id": "session-1",
  "source": "fsm",
  "type": "halt",
  "payload": {"reason": "user_interrupt", "state": "CASTING"}
}
```

---

## Phase 1 Gate Criteria

Story 4.3 directly supports the Phase 1 gate requirement:
> "Missed bite returns to idle cleanly" (FR-25 partial)

**Verification:**
- ✅ IDLE → CASTING → WAITING flow works
- ✅ Timeout logic returns cleanly to IDLE
- ✅ No error state entered on timeout
- ✅ Session events logged for operational review
- ✅ Safe halt prevents further action

---

## Future Enhancements (Story 4.4+)

- Tension detection via YOLO (bite event)
- Reel execution state and key sequence
- Reel completion detection
- Fatigue integration (breaks during long sessions)
- Recording mode for training data collection
