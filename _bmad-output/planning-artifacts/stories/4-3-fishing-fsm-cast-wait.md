---
storyId: 4.3
epic: "Epic 4: Fishing Mode"
title: "Fishing FSM — Cast and Wait States"
status: draft
---

# Story 4.3: Fishing FSM — Cast and Wait States

## User Story

As Ion,
I want the Fishing Mode FSM to implement IDLE → CASTING → WAITING states where the bot casts the fishing rod and waits for a bite event,
So that the first half of the fishing loop runs autonomously and timeouts return cleanly to IDLE (FR-25 partial).

## Acceptance Criteria

### Criterion 1: Idle-to-cast-to-wait flow

**Given** the Agent is in the IDLE state with the Fishing Mode profile loaded
**When** the FSM tick runs
**Then** the Agent transitions to CASTING; the rod cast key sequence is executed via HSL; the FSM transitions to WAITING

### Criterion 2: Timeout returns to idle cleanly

**Given** the FSM is in the WAITING state
**When** no bite event is detected within the configured timeout
**Then** the FSM transitions back to IDLE cleanly; the timeout event is logged; the next tick begins a new cast cycle

### Criterion 3: Safe halt during active cast or wait

**Given** the FSM is in CASTING or WAITING
**When** a session halt signal is received
**Then** the current state is abandoned safely; the Agent transitions to a stopped state and produces no further input

## Dependencies

- Fishing Mode profile bindings and timing thresholds
- HSL execution path for cast key sequence
- State transition logic and session halt handling
- Session DB logging for timeout and halt events

## Notes

This story provides the deterministic baseline for the full cast/wait/reel loop. It deliberately excludes tension detection and reel execution from the acceptance criteria so the loop can be validated before the Phase 1 gate is closed.
