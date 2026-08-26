# Story 6.2: Prophet Buff Cycle FSM

Status: done

## User Story

As Ion,
I want the PP Agent to maintain independent timers for each configured buff, enter BUFFING state when a timer expires, evaluate the Safety Check before casting, and defer failed casts with automatic retry,
So that PP buffs are applied reliably and safely without being permanently skipped or casting into high-risk situations (FR-6, Phase 2 of Epic 6).

## Acceptance Criteria

**AC-1:** Timer initialization and duration loading
- Given `prophet.yaml` defines buff timers under `buff_timer_durations` (e.g., `haste: 300.0`)
- When the Prophet Agent FSM initializes
- Then each buff timer is loaded from the profile; fake clocks in tests allow deterministic timer expiry

**AC-2:** BUFFING state on timer expiry
- Given a buff timer has been running
- When the configured duration elapses (or is advanced via fake clock)
- Then the FSM transitions to `BUFFING` and signals which buff is due

**AC-3:** Safety Check gates every cast
- Given the FSM is in `BUFFING` and a buff is due to cast
- When the Safety Check is evaluated
- Then the cast is executed only if safe; otherwise deferred

**AC-4:** Deferred casts retry automatically
- Given a cast has been deferred due to failed Safety Check
- When the retry interval elapses
- Then the Safety Check is re-evaluated; the cast executes as soon as the check passes

**AC-5:** WL PULLING blocks timed casts
- Given WL `PartyState.fsm_state` is `PULLING`
- When a buff timer expires
- Then the cast is deferred until WL exits PULLING, even if no mobs are nearby

**AC-6:** Multiple buffs are not abandoned
- Given multiple buff timers are configured and due
- When the FSM processes one buff cycle
- Then pending buffs are preserved in the queue and processed in the next eligible opportunity

**AC-7:** Events logged for cast and safety decisions
- Given a buff cast succeeds or is deferred
- When the decision is made
- Then `buff_cast_attempted`, `buff_cast_deferred`, and `buff_timer_reset` events are logged to sessions.db with buff name, timestamp, peer state, and pass/fail outcome

**AC-8:** No offensive action outside BUFFING
- Given the FSM is in `IDLE` or other non-BUFFING state
- When `next_action()` is called
- Then no Action is generated; the state handler returns None or a non-action response

## Dependencies

- PPBuffSafetyCheck from `lagent.agent.prophet` (Story 5.2, already implemented)
- Party Bus peer state relay (Story 5.3)
- Profile-loaded buff timer durations and skill bindings
- Current-frame PerceptionResult for mob proximity
- Fake clock for deterministic timer tests
- Session DB for event logging

## Implementation

- Added `BuffTimer` class to manage independent timers per buff with fake-clock support
- Implemented `ProphetBuffPolicy` FSM in `lagent/agent/prophet/__init__.py` with:
  - Profile-driven buff timer initialization from `buff_timer_durations`
  - BUFFING state transition on timer expiry
  - PPBuffSafetyCheck gate before every cast
  - Automatic retry with configurable interval on failed checks
  - WL PULLING state blocks casts even when safety check would pass
  - Full event logging to sessions.db for buff decisions and state transitions
  - Lifecycle state suppression (PAUSED, DEAD, RETURNING, STOPPED)
  - Party Bus state publishing on transitions
- Created comprehensive test suite in `tests/test_story_6_2_prophet_buff_fsm.py` covering all ACs
- All 11 focused tests passing; existing Story 6.1 and 5.2 tests still pass
- Full compilation check passes without errors

## Validation

- `tests/test_story_6_2_prophet_buff_fsm.py`: **11 tests passing**
- Deterministic fake-clock test proves deferred buff retry cycle end-to-end
- Multiple buff timers initialized and tracked independently
- WL PULLING blocks casts as specified
- All events logged with correct payload shape
- No regressions in Story 6.1 (Warlord FSM) or Story 5.2 (Safety Check)

## Implementation Plan (Reference)

### 1. Create `ProphetBuffPolicy` class in `lagent/agent/prophet/__init__.py`

- Accept `profile` dict/object with `buff_timer_durations` and `skill_key_bindings`
- Initialize `BuffTimer` instances for each configured buff
- Expose `current_state()`, `next_action()`, and `process_tick(perception, game_state, clock)` methods
- Track pending/deferred buffs in an internal queue
- Integrate PPBuffSafetyCheck on every cast attempt

### 2. Implement `BuffTimer` helper class

- Track elapsed time since last reset
- Expose `is_expired(now)` predicate
- Support fake-clock injection via `process_tick()`

### 3. Integrate into Prophet Agent loop

- Update the Prophet Agent's main `__main__.py` to use ProphetBuffPolicy instead of wait-only fallback
- Fetch current-frame perception and game_state from the inference pipeline
- Call `next_action()` on each loop tick
- Dispatch actions through HSL

### 4. Write focused tests

**Test file:** `tests/test_story_6_2_prophet_buff_fsm.py`

Tests to write:
- Timer expiry transitions to BUFFING
- Safe cast executes immediately
- Failed check defers and logs event
- WL PULLING defers cast even when safe otherwise
- Multiple buffs are queued and not abandoned
- Retry loop eventually executes deferred cast when conditions improve
- No action generated outside BUFFING state
- All events present in sessions.db with correct payload shape

### 5. Validation

- Run `pytest tests/test_story_6_2_prophet_buff_fsm.py -v`
- Verify all focused tests pass
- Run full test suite: `pytest -q`
- Compile check: `python3 -m compileall lagent tests`

## Exit Check

A deterministic fake-clock test demonstrates:
1. Timer expiry → BUFFING transition
2. Initial Safety Check failure → deferred event logged
3. Retry interval elapses → Safety Check re-evaluated
4. On next check pass → buff is cast exactly once and timer resets
5. Multiple buffs queued and processed in order

## Known Blockers

None. PPBuffSafetyCheck is implemented; Party Bus peer state is available; lifecycle contract supports deferred transitions.
