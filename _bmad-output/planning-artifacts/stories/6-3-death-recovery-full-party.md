---
storyId: 6.3
epic: "Epic 6: Combat Mode & Session Lifecycle"
title: "Death Detection & Full Party Recovery"
status: ready
---

# Story 6.3: Death Detection & Full Party Recovery

## User Story

As Ion,
I want both agents to detect the death state, execute the respawn and rebuff sequence, and resume their prior FSM states — completing the full party recovery within 60 seconds,
So that the session continues automatically after a party wipe without Ion's intervention (FR-16).

## Acceptance Criteria

### Criterion 1: Death state detection transitions to DEAD state

**Given** WL Agent detects the death state (death screen detection via YOLO in PerceptionResult)
**When** the FSM evaluates the GameState
**Then** WL transitions to DEAD; the respawn key sequence executes; WL navigates to the buff restoration position

### Criterion 2: PP rebuffs after WL respawn

**Given** WL has respawned and reached the buff spot
**When** PP Agent detects WL's `PartyState` has transitioned from DEAD to a recoverable state
**Then** PP casts the full buff cycle on WL; upon completion, both agents resume their pre-death FSM states

### Criterion 3: Recovery completes within 60 seconds

**Given** the death event was detected
**When** full party recovery completes
**Then** elapsed time from death detection to both agents active is ≤60 seconds; the death event and recovery sequence are logged to `sessions.db` with timestamps

## Dependencies

- Warlord and Prophet Agent FSM base loops (Story 4.1) with state machine infrastructure
- Party Bus `PartyState` subscription for coordinated death detection (Story 5.1)
- Warlord Combat FSM (Story 6.1) for prior state capture
- Prophet Buff Cycle FSM (Story 6.2) for buff cycle execution
- YOLO death screen detection in the perception pipeline (Story 2.3)
- Agent profiles with respawn key sequence and buff restoration position
- HSL for action dispatch (Story 3.x)
- Session database event logging

## Notes

Death recovery is a coordinated, two-phase sequence: (1) WL detects death, respawns, and moves to buff spot; (2) PP detects the recovery state and executes a full buff cycle. Both agents then resume their pre-death FSM states (e.g., return to FIGHTING if they were in combat). The 60-second SLA ensures the session recovery is faster than a typical human player wipe recovery.

## Tasks / Subtasks

- [ ] Add DEAD FSM state to Warlord FSM with respawn sequence and buff-spot navigation.
- [ ] Implement death screen detection condition in PerceptionResult pipeline.
- [ ] Capture pre-death FSM state when death is detected.
- [ ] Implement Prophet rebuff cycle triggered by WL `PartyState.fsm_state` recovery.
- [ ] Restore pre-death FSM states for both agents after rebuff cycle completes.
- [ ] Log death event and recovery sequence with timestamps to `sessions.db`.
- [ ] Validate 60-second SLA with end-to-end recovery tests.

## Dev Agent Record

### Implementation Plan

- Add DEAD state to `lagent/agent/combat_fsm.py` with respawn action and buff-spot navigation.
- Implement death detection condition in the perception pipeline; add `death_detected` to `PerceptionResult`.
- Capture and store `prior_fsm_state` when transitioning to DEAD.
- Implement recovery state polling in Prophet FSM: monitor WL `PartyState.fsm_state` for recovery.
- Upon recovery signal, execute full buff cycle in Prophet FSM.
- Restore both agents to their captured pre-death states.
- Log recovery events with elapsed time.
- Create end-to-end test in `tests/test_story_6_3_death_recovery.py` with death and recovery sequences.

### Completion Notes

(Pending implementation)

### File List

(Pending implementation)

## Change Log

- 2026-08-26: Story created from Epic 6 specification.
