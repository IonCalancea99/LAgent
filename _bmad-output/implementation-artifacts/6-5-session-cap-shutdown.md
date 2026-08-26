# Story 6.5: Session Cap and Clean Shutdown

Status: done

## User Story

As Ion,
I want the system to enforce a configurable session duration cap, cleanly shut down at expiry with WL navigating to a safe location and PP performing a final buff cycle, and both agents halting safely without unsafe residual actions,
So that farming sessions never run past the configured limit and the session ends in a clean, logged, auditable state (FR-18, Phase 5 of Epic 6).

## Acceptance Criteria

**AC-1:** Session cap initialized at session start
- Given a WL Agent is created with a configured session_cap duration
- When the Agent's FSM is instantiated
- Then a SessionCapController is initialized with the cap duration; cap is monotonic

**AC-2:** Cap expiry is checked at every loop boundary
- Given a session has been running
- When the elapsed time reaches or exceeds the configured cap duration
- Then the SessionCapController.expired() returns True
- And WL FSM checks `cap.expired()` before selecting next action

**AC-3:** WL transitions to STOPPED on cap expiry
- Given session cap is reached
- When the WL FSM processes the next action selection
- Then WL transitions to STOPPED state immediately; all combat and recovery actions are suppressed

**AC-4:** No combat actions after cap expiry
- Given WL has reached the session cap
- When `next_action()` is called
- Then no pull, fight, loot, or any offensive action is returned
- And only safe final actions (if configured) or None are returned

**AC-5:** PP halts safely without offensive actions
- Given WL is in STOPPED state
- When PP evaluates buff timers or actions
- Then PP Safety Check defers all casts (ProphetBuffPolicy's STOPPED suppression)
- And no offensive actions are emitted

**AC-6:** Cap shutdown is idempotent
- Given the session cap has been reached and shutdown mode entered
- When duplicate cap-reached signals or additional ticks arrive
- Then the shutdown state is not re-entered; state remains STOPPED and no duplicate shutdown events are logged

**AC-7:** All cap shutdown events logged
- Given session cap shutdown is complete
- When the cap expiry occurs
- Then `session_cap_reached` event is logged with elapsed_seconds
- And WL transitions to STOPPED with `cap_shutdown_initiated` reason
- And all final state transitions are logged

**AC-8:** Session end states clean and logged
- Given shutdown is complete
- When the session ends
- Then final state logged with `ended_at` timestamp
- And session marked as completed with reason "session_cap_reached"

## Dependencies

- `SessionCapController` from `lagent.agent.lifecycle` (already implemented)
- WL FSM with cap check on each tick
- PP Safety Check defers actions in STOPPED state (automatic via suppression)
- Session DB for event logging
- Monotonic clock for cap enforcement

## Implementation Plan

### 1. Integrate SessionCapController into WarlordCombatFSM

- Initialize SessionCapController in FSM constructor with configured cap duration
- Check `cap.expired()` at the beginning of `__call__` before processing actions
- If cap is reached, transition to STOPPED and suppress all actions

### 2. Suppress actions in STOPPED state

- Add STOPPED to the lifecycle suppression check or handle explicitly
- Verify no combat actions are dispatched
- Return None or safe actions only

### 3. Wire PP suppression in STOPPED state

- ProphetBuffPolicy already suppresses actions in STOPPED state
- Verify Party Bus publishes WL STOPPED state so PP observes it

### 4. Write focused tests

**Test file:** `tests/test_story_6_5_session_cap_shutdown.py`

Tests to write:
- Session cap initialized and monotonic
- Cap expiry returns True at configured duration
- WL transitions to STOPPED on cap expiry
- No combat actions after STOPPED
- PP defers all casts while WL is STOPPED
- Idempotent shutdown (duplicate signals don't re-trigger)
- All events logged with correct shape
- Session end states complete and auditable

### 5. Validation

- Run `pytest tests/test_story_6_5_session_cap_shutdown.py -v`
- Run existing tests: all previous Story 6 tests (no regressions)
- Run full suite: `pytest -q`
- Compile check: `python3 -m compileall lagent tests`

## Exit Check

A deterministic two-agent harness with fake perception, fake clock, and session cap demonstrates:
1. Cap initialized at session start
2. Cap expiry is detected exactly at configured duration
3. WL transitions to STOPPED and emits no combat actions
4. PP observes STOPPED state and defers all casts
5. All events logged with correct payloads
6. Session end state is clean and auditable

## Implementation

- Integrated `SessionCapController` into `WarlordCombatFSM` with profile, parameter, and default duration support.
- Checked cap expiry at every FSM tick before lifecycle or combat action selection.
- Transitioned WL to `STOPPED` once the cap is reached and suppressed subsequent actions idempotently.
- Preserved PP suppression through the existing `STOPPED` lifecycle state handling.
- Allowed inventory-return completion to resume IDLE combat evaluation on the same tick.
- Added focused deterministic tests covering cap timing, shutdown, suppression, idempotence, and event logging.

## Known Blockers

None. All deterministic acceptance tests pass.

## Notes

- Session cap is a global constraint: both WL and PP must halt at cap expiry
- Shutdown must be clean: no orphaned actions, no state corruption
- This story completes Epic 6 when combined with 6.1-6.4
