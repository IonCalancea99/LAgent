---
storyId: 4.4
epic: "Epic 4: Fishing Mode"
title: "Fishing FSM — Tension Detection and Reel"
status: done
---

# Story 4.4: Fishing FSM — Tension Detection and Reel

## User Story

As Ion,
I want the Fishing FSM to detect a fish tension event via YOLO and execute the reel input, completing the full cast-to-reel loop so the bot sustains 1 hour of uninterrupted autonomous fishing,
So that the Phase 1 gate is met and the full end-to-end pipeline is validated on a real use case (FR-25 completion).

## Acceptance Criteria

### Criterion 1: Detect tension and reel successfully

**Given** the FSM is in WAITING state and a tension visual indicator is present in the game frame
**When** the YOLO detection returns a tension class detection above the configured confidence threshold (`>= 0.80`)
**Then** the FSM transitions to REELING; the reel input key sequence is executed via HSL; the FSM returns to IDLE; the confidence score and tension window are logged

### Criterion 2: Full 60-minute loop runs without intervention

**Given** the bot runs the fishing loop for 60 uninterrupted minutes
**When** the session ends
**Then** zero unhandled exceptions have occurred; the session log shows a continuous sequence of cast/wait/reel cycles; no human input was required; this is treated as the end-to-end validation gate for Epic 4 and not as the sole acceptance criterion for the state machine

### Criterion 3: Missed bite returns to idle without error

**Given** a bite event is missed and YOLO confidence stays below threshold during the bite window
**When** the timeout expires in WAITING state
**Then** the FSM returns to IDLE and begins the next cast; no error state is entered; the missed-tension event and timeout are logged for operational review

### Criterion 4: Deterministic replay of seeded frame sequences

**Given** the cast/wait/reel logic is under test in a deterministic harness
**When** a seeded sequence of frame results is replayed
**Then** the resulting state transitions and actions are identical across repeated runs, allowing approval of the runtime implementation before live use

## Dependencies

- YOLO tension detection and confidence thresholding
- Fishing Mode state machine transitions and reel action mapping
- HSL shaping for cast and reel inputs
- Session DB logging of tension confidence, timeouts, and repeated loops

## Notes

This is the Phase 1 gate story for fishing. It should be validated using deterministic seeded replays before live 60-minute runtime confirmation, as recommended by the architecture and implementation-readiness review.

### Review Findings

- [x] [Review][Patch] Wire the fishing FSM, fishing profile selection, and HSL into the runnable agent path.
- [x] [Review][Patch] Verify reel actions are dispatched through HSL in the Story 4.4 integration test.
- [x] [Review][Patch] Expand deterministic replay coverage to repeated cast, wait, tension, reel cycles including the 0.80 threshold boundary.
