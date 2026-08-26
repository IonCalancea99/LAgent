---
storyId: 6.2
epic: "Epic 6: Combat Mode & Session Lifecycle"
title: "Prophet Buff Cycle FSM — Timer-Driven Buffing"
status: ready
---

# Story 6.2: Prophet Buff Cycle FSM — Timer-Driven Buffing

## User Story

As Ion,
I want the PP Agent to manage buff timers independently and enter BUFFING state to cast each buff on timer expiry, with all casts gated by Safety Check,
So that WL maintains full buffs throughout the session without Ion's involvement (FR-5 PP Combat, FR-6 buff cycle).

## Acceptance Criteria

### Criterion 1: Buff timer expiry triggers buffing state

**Given** PP buff timers are initialized from `prophet.yaml` on session start
**When** a buff timer expires
**Then** PP transitions from IDLE to BUFFING; the Safety Check is evaluated; if it passes, the buff cast executes via HSL; PP returns to IDLE after casting

### Criterion 2: Safety check defers buff on warlord pull

**Given** PP is mid-BUFFING and WL's `PartyState.fsm_state` changes to PULLING
**When** Safety Check is re-evaluated
**Then** the remaining buff casts are deferred until WL exits PULLING; no partial buff sequence is abandoned without retry

### Criterion 3: Buff cycle events are logged

**Given** a full buff cycle (all timed buffs) has been cast
**When** the session log is inspected
**Then** each buff cast appears as a structured event with timestamp, buff name, and Safety Check pass/fail result

## Dependencies

- Prophet Agent FSM base loop (Story 4.1) with state machine infrastructure
- Party Bus `PartyState` subscription for WL state visibility (Story 5.1)
- PP Buff Safety Check (Story 5.2)
- Agent profile `prophet.yaml` with buff timer durations and skill key bindings per buff
- HSL for buff cast dispatch (Story 3.x)
- Session database event logging
- Buff retry deferred-cast handling from Story 5.2

## Notes

The Prophet buff cycle is independent of combat but coordinated with WL's state via the Party Bus. Each buff is timer-driven and cast on expiry, subject to Safety Check validation. Failed safety checks defer the buff; they never skip it.

## Tasks / Subtasks

- [ ] Initialize buff timers from `prophet.yaml` on session start.
- [ ] Implement timer-expiry detection in the FSM policy loop.
- [ ] Wire Safety Check (Story 5.2) into buff casting.
- [ ] Implement buff cast sequence execution via HSL.
- [ ] Implement deferred-cast retry logic when Safety Check fails.
- [ ] Log buff cast events (attempt, success/deferred, Safety Check reason) to `sessions.db`.
- [ ] Add deterministic FSM tests with timed buff sequences and Safety Check failures.

## Dev Agent Record

### Implementation Plan

- Create `lagent/agent/prophet_fsm.py` with timer-driven state machine.
- Maintain a buff queue with per-buff timers updated each tick.
- On timer expiry, call the Safety Check module; on pass, dispatch via HSL; on fail, schedule retry.
- Log each buff event with timestamp, buff name, and pass/fail reason.
- Create test harness in `tests/test_story_6_2_prophet_buff_fsm.py` with deterministic timer sequences.

### Completion Notes

(Pending implementation)

### File List

(Pending implementation)

## Change Log

- 2026-08-26: Story created from Epic 6 specification.
