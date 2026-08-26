---
storyId: 5.2
epic: "Epic 5: Party Orchestration"
title: "PP Buff Safety Check"
status: backlog
---

# Story 5.2: PP Buff Safety Check

## User Story

As Ion,
I want the PP Agent to evaluate a Safety Check before every timed buff cast, passing only when no mobs are within the configured aggro-risk radius (in pixel coordinates) and WL is not in PULLING state,
So that PP never draws mob aggro by casting at the wrong moment — and if the check fails, the cast is deferred and retried, never silently skipped (FR-6).

## Acceptance Criteria

### Criterion 1: Immediate execution on safe state

**Given** PP buff timer has expired
**When** no mobs are within the pixel-coordinate aggro-risk radius (per AD-10b) and WL `PartyState.fsm_state` is not PULLING
**Then** Safety Check passes; the buff cast is executed immediately

### Criterion 2: Risk radius uses current-frame pixel coordinates

**Given** a current-frame `PerceptionResult` contains mob detections and PP has a current-frame character position
**When** the Safety Check evaluates proximity
**Then** it uses each mob detection's `bbox_xyxy` center and PP's `GameState.character_position`, both in captured-frame pixels with origin top-left; a mob is within the risk radius when Euclidean distance is less than or equal to the configured radius; no game-world coordinates are used

### Criterion 3: WL PULLING fails the state gate

**Given** PP buff timer has expired
**When** WL `PartyState.fsm_state` is `PULLING`
**Then** Safety Check fails even when no mob is currently inside the radius; `FIGHTING` and other non-`PULLING` WL states do not fail the state-only condition

### Criterion 4: Failed checks defer and retry without silent skip

**Given** PP buff timer has expired
**When** a mob is detected within the aggro-risk radius in the current frame
**Then** Safety Check fails; the retry timer starts at the time of the failed check; the buff cast is deferred by the configured retry interval; a `buff_cast_deferred` event records the failed condition and next eligible timestamp; PP continues normal non-cast policy-loop work while waiting

### Criterion 5: Re-evaluation is repeated until safe

**Given** Safety Check has failed repeatedly
**When** the retry interval elapses
**Then** the check is re-evaluated; the cast executes as soon as the check passes; the cast is never permanently skipped

## Dependencies

- Current-frame perception results and mob `bbox_xyxy` center extraction
- `GameState.character_position` in captured-frame pixel space
- WL peer state `fsm_state` from Party Bus
- ICC buff-timer architecture and retry timing
- Session event logging for `buff_cast_deferred`

## Notes

The Safety Check must be deterministic and non-destructive: it evaluates only the current frame plus peer state, never mutates the underlying `GameState`, and always defers instead of dropping a buff attempt. This keeps PP behavior safe even when aggro risk spikes during WL pull transitions.

## Tasks / Subtasks

- [ ] Define and configure aggro-risk radius and retry-interval policy constants.
- [ ] Add Safety Check gate before each timed buff cast using mob proximity and WL `PULLING` state.
- [ ] Defer failed casts with exact retry timestamps and session events.
- [ ] Keep PP on its normal loop while waiting; never permanently skip a valid buff opportunity.
- [ ] Add tests covering safe pass, WL PULLING fail, radius fail, and retry loop.

## Dev Agent Record

### Implementation Plan

- Reuse current-frame `PerceptionResult` bounding boxes and `GameState.character_position` from the capture frame coordinate system.
- Evaluate both conditions in order: exact-radius aggro risk and WL `PULLING` state gate.
- If either fails, schedule the retry using the configured interval and log a `buff_cast_deferred` event with failure reasons and next eligibility time.

### Completion Notes

- This story remains in backlog until the PP buff gating logic is implemented and proven in both pass/fail/retry scenarios.

## Change Log

- 2026-08-26: Updated story to match the final Safety Check contract and retry semantics after the epic-wide requirement refresh.
