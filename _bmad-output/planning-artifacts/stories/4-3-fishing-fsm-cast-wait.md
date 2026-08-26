---
storyId: 4.3
epic: "Epic 4: Fishing Mode"
title: "Fishing FSM — Cast and Wait States"
status: in-progress
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

## Review Findings

**Code Review — Story 4.3 (2026-08-26)**
Generated from Blind Hunter + Edge Case Hunter + Acceptance Auditor layers.
**Status: PATCHES APPLIED ✓**

### Decisions Resolved

- [x] [Review][Decision] **State Name Case Convention** — Resolved: Normalized all state names to UPPERCASE (IDLE, CASTING, WAITING, STOPPED) in both FishingFSM and profile bindings.

- [x] [Review][Decision] **Halt Signal Integration** — Resolved: Implemented callback/signal handler pattern via `AgentLoop.request_halt()` method. Session layer calls this method to propagate halt to FSM.

### Patches Applied ✓

- [x] [Review][Patch] **State Validation & Silent Failures** [loop.py:106-109, fishing_fsm.py:159-161] — Applied. Added validation for missing profile.fsm_bindings with warning; invalid state names now raise ValueError; object bindings supported via getattr().

- [x] [Review][Patch] **Wait Timer Corruption Across State Transitions** [fishing_fsm.py:113-148] — Applied. Detect fresh entry to WAITING state and reset wait_started_at when transitioning from other states. Timer no longer corrupted on re-entry.

- [x] [Review][Patch] **Halt Is Irreversible & Lacks Guard** [fishing_fsm.py:83] — Applied. Added idempotency guard in handle_halt() to detect and log duplicate halt attempts.

- [x] [Review][Patch] **Negative Duration Action Parameter** [fishing_fsm.py:140-150] — Applied. Clamped remaining time to non-negative with `max(0.0, ...)` before calculating action duration.

- [x] [Review][Patch] **Missing Future Import for PEP 604** [fishing_fsm.py:1] — Applied. Added `from __future__ import annotations` at top of file.

- [x] [Review][Patch] **Exception Swallowing in Logging** [fishing_fsm.py:71-73, loop.py:160-162] — Applied. Distinguish recoverable vs fatal errors: (IOError, OSError, PermissionError) raise; others warn and continue.

- [x] [Review][Patch] **Profile Object Binding Not Handled** [loop.py:107-109] — Applied. Added getattr() path for object-based bindings in addition to dict path.

### Deferred

- [x] [Review][Defer] **Timeout Action Ambiguity** — Deferred: Return value `Action(wait, 0.0)` ambiguous to caller. Design issue, defer to architecture review.
- [x] [Review][Defer] **Floating Point Precision** — Deferred: Very small timeouts < 0.01s can timeout spuriously. Unlikely in production, defer to performance tuning phase.
- [x] [Review][Defer] **Unused Profile Parameter** — Deferred: Constructor accepts profile but never uses it. Planned for future use.

## Notes

This story provides the deterministic baseline for the full cast/wait/reel loop. It deliberately excludes tension detection and reel execution from the acceptance criteria so the loop can be validated before the Phase 1 gate is closed.
