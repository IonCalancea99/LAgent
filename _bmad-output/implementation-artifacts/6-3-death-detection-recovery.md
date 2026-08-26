# Story 6.3: Death Detection and Full Party Recovery

Status: done

## Implementation

- Integrated death signal detection into WarlordCombatFSM using `detect_lifecycle_signal()` from lifecycle module
- Wired DeathRecoveryController into FSM for idempotent respawn sequence management
- Added DEAD state handling that dispatches configured recovery actions through HSL
- Recovery actions sourced from `profile.recovery.actions` and executed in order
- Full party coordination: PP Safety Check defers all casts while WL is DEAD (automatic via DEAD state suppression)
- State snapshot and resumption: pre-death FSM state saved and restored after recovery completes
- Recovery timing tracked with budget enforcement (≤60 seconds logged and accessible for monitoring)
- All events logged to sessions.db: death_detected, recovery_action, recovery_complete with full payloads
- Idempotent recovery: duplicate death signals don't restart the sequence

## Validation

- `tests/test_story_6_3_death_recovery.py`: **13 tests passing**
- Death detection from YOLO (class_name: "death") and OCR (ocr_values: {"death": ...})
- WL transitions to DEAD and saves pre-death state from any combat state
- Respawn sequence dispatched in order; idempotent (no double-execution on duplicate signals)
- Recovery timing within/exceeding 60-second budget correctly logged
- PP defers casts while WL is DEAD (verified through cross-agent safety check)
- No combat actions emitted during recovery
- Deterministic cycle: death → DEAD → respawn actions → resume pre-death state
- No regressions in Story 6.1 or 6.2 tests

## Implementation Plan (Reference)

As Ion,
I want the WL Agent to detect death from perception/YOLO/UI signals, transition to DEAD, execute respawn and recovery actions, coordinate PP rebuffing, and return to the pre-death FSM state,
So that WL can recover autonomously from party wipes with full party coordination and a bounded 60-second recovery window (FR-16, Phase 3 of Epic 6).

## Acceptance Criteria

**AC-1:** Death detection from normalized signals
- Given a PerceptionResult contains death-related detections or OCR values (e.g., "death", "dead", "death_screen")
- When the Agent processes perception
- Then `detect_lifecycle_signal()` returns a `LifecycleSignal` with name "death_detected" and current timestamp

**AC-2:** WL transitions to DEAD and saves pre-death state
- Given death is detected in any combat state (IDLE, PULLING, FIGHTING, LOOTING, BUFFING)
- When the FSM processes the signal
- Then WL state transitions to DEAD; the pre-death state (PULLING/FIGHTING/LOOTING) is snapshot and preserved for resumption

**AC-3:** Respawn sequence dispatched through HSL
- Given WL is in DEAD state and the profile has configured respawn actions
- When the Agent ticks
- Then each respawn action (e.g., "key_press:enter", movement) is returned via `next_action()` and dispatched through HSL
- And actions are emitted in configured order until the respawn sequence completes

**AC-4:** PP does not cast while WL is DEAD
- Given WL is in DEAD state
- When PP evaluates buff timers
- Then PP Safety Check defers all casts and PP remains waiting
- And no offensive actions are emitted (enforced by ProphetBuffPolicy's PAUSED/DEAD/RETURNING/STOPPED suppression)

**AC-5:** Full party recovery is idempotent
- Given death has been detected and logged
- When duplicate death frames or multiple Party Bus messages arrive
- Then the respawn sequence is not repeated; the state remains DEAD until recovery is explicitly complete

**AC-6:** Recovery completion and state resumption
- Given the respawn sequence is complete and WL has navigated to the recovery position
- When `recovery.complete()` is called
- Then WL returns to the pre-death FSM state (PULLING, FIGHTING, LOOTING, or IDLE as configured)
- And the resumed state is published over Party Bus

**AC-7:** Recovery timing is tracked and logged
- Given recovery begins and completes
- When elapsed time is calculated
- Then `recovery_complete` event includes elapsed_seconds, within_budget (≤60s), and resumed_state
- And recovery exceeding 60 seconds is logged as a failed/over-budget event

**AC-8:** No unsafe actions during recovery
- Given WL is DEAD or any recovery state
- When AgentLoop requests `next_action()`
- Then only respawn/recovery actions are returned; no combat actions are emitted

## Dependencies

- `detect_lifecycle_signal()` and `DeathRecoveryController` from `lagent.agent.lifecycle` (already implemented)
- Perception fixtures with death detections
- Party Bus peer state relay (Story 5.3)
- Profile-configured respawn actions
- Current-frame PerceptionResult and GameState
- Session DB for event logging

## Implementation Plan

### 1. Wire death detection into WarlordCombatFSM

- Import `detect_lifecycle_signal()` from lifecycle
- On every FSM call, check for death signal in perception
- On detection: transition to DEAD, call `DeathRecoveryController.begin(prior_state)`
- Log death_detected event with snapshot

### 2. Dispatch recovery actions from Warlord FSM

- While in DEAD state, query `recovery.next_action()` each tick
- Return action from FSM until `recovery.next_action()` returns None
- Then call `recovery.complete()` to transition back to pre-death state

### 3. Coordinate PP during recovery

- ProphetBuffPolicy already suppresses actions in DEAD state
- Verify Party Bus publishes WL DEAD state so PP observes it
- Verify PP waits for Safety Check to defer all buff casts while WL is DEAD

### 4. Write focused tests

**Test file:** `tests/test_story_6_3_death_recovery.py`

Tests to write:
- Death signal detection from perception
- WL DEAD transition and state snapshot
- Respawn action sequence dispatched in order
- Idempotent recovery (duplicate signals don't repeat sequence)
- Recovery completion and state resumption
- PP defers casts while WL is DEAD (cross-agent verification)
- Recovery timing within 60-second budget
- No combat actions emitted during DEAD state

### 5. Validation

- Run `pytest tests/test_story_6_3_death_recovery.py -v`
- Run `pytest tests/test_story_6_1_warlord_combat.py tests/test_story_6_2_prophet_buff_fsm.py -v` (no regressions)
- Run full suite: `pytest -q`
- Compile check: `python3 -m compileall lagent tests`

## Exit Check

A deterministic two-agent harness with fake perception and fake clock demonstrates:
1. WL detects death and transitions to DEAD
2. Pre-death state is captured
3. Respawn sequence is dispatched in order through HSL
4. PP observes DEAD state and defers all casts
5. Recovery completes within budget
6. WL resumes pre-death state
7. All events logged with correct payloads
8. Duplicate death signals don't repeat respawn

## Known Blockers

None. All infrastructure present (lifecycle.py, Party Bus, HSL dispatch).
