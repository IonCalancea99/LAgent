---
storyId: 6.5
epic: "Epic 6: Combat Mode & Session Lifecycle"
title: "Session Cap & Clean Shutdown"
status: ready
---

# Story 6.5: Session Cap & Clean Shutdown

## User Story

As Ion,
I want each session to enforce a configurable maximum duration and execute a clean shutdown sequence — returning both characters to a safe position, completing PP's final buff cycle, and stopping all OS input,
So that sessions end predictably and safely even if Ion walks away and forgets about them (FR-18).

## Acceptance Criteria

### Criterion 1: Session cap timer fires and stops combat

**Given** a session reaches the configured cap (default 4–6 hours)
**When** the cap timer fires — even mid-combat-cycle
**Then** the current combat action is abandoned; WL moves to a safe position before stopping; no further combat actions are taken

### Criterion 2: Final buff cycle and idle state

**Given** the session cap has been reached and WL is in a safe position
**When** PP executes the shutdown buff cycle
**Then** PP casts a final round of buffs; both characters enter an idle standing state; the bot produces no further keyboard or mouse input

### Criterion 3: Shutdown logged with final state

**Given** shutdown completes
**When** `sessions.db` is inspected
**Then** the session record has a `ended_at` timestamp; a `session_cap_shutdown` event is present with the final FSM states of both agents

## Dependencies

- Warlord and Prophet Agent FSM base loops (Story 4.1) with session lifecycle hooks
- Session timer infrastructure in the Orchestrator (Story 1.4)
- Agent profiles with safe-return movement sequence and shutdown safe position
- Prophet Buff Cycle FSM (Story 6.2) for final buff execution
- HSL for action dispatch (Story 3.x)
- Session database with `sessions` table updated with `ended_at` and session cap event logging

## Notes

The session cap is a hard enforcement mechanism to prevent infinite-running sessions and ensure predictable resource usage. When the cap fires, the bot abandons any current action, moves to a safe spot (typically the buff location), executes a final buff cycle on both agents, and stops all input. The session is then marked as cleanly shut down in the database.

## Tasks / Subtasks

- [ ] Implement session cap timer in Orchestrator (started at session begin, fires at configured duration).
- [ ] Emit `session_cap_reached` event from Orchestrator to both agents when cap fires.
- [ ] Add SHUTTING_DOWN FSM state to both Warlord and Prophet FSMs.
- [ ] Implement safe-position return sequence for WL (movement keys via HSL).
- [ ] Implement final buff cycle in PP (full buff set without Safety Check gating).
- [ ] Transition both agents to IDLE after shutdown sequence completes.
- [ ] Update `sessions.db` `sessions` table with `ended_at` timestamp.
- [ ] Log `session_cap_shutdown` event with final FSM states and elapsed session duration.
- [ ] Add deterministic tests validating session cap timer and shutdown sequence.

## Dev Agent Record

### Implementation Plan

- Add session cap timer to `lagent/orchestrator/__main__.py`; emit control event when cap fires.
- Add SHUTTING_DOWN state to both `lagent/agent/combat_fsm.py` and `lagent/agent/prophet_fsm.py`.
- Implement safe-return sequence in Warlord (movement to buff spot via profile-defined keys).
- Implement final buff cycle in Prophet (iterate all buffs, dispatch via HSL without Safety Check filtering).
- Update session close logic to log `ended_at` and `session_cap_shutdown` event.
- Create test in `tests/test_story_6_5_session_cap_shutdown.py` validating cap timer and full shutdown sequence.

### Completion Notes

(Pending implementation)

### File List

(Pending implementation)

## Change Log

- 2026-08-26: Story created from Epic 6 specification.
