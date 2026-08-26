---
storyId: 5.3
epic: "Epic 5: Party Orchestration"
title: "Orchestrator Heartbeat Monitor & Session Halt"
status: backlog
---

# Story 5.3: Orchestrator Heartbeat Monitor & Session Halt

## User Story

As Ion,
I want the Party Orchestrator to monitor heartbeat messages from both agents and trigger a session halt on both when either agent misses N consecutive heartbeats,
So that a stuck or crashed agent never leaves the other agent running unmonitored against the live game (FR-13, FR-14).

## Acceptance Criteria

### Criterion 1: Heartbeat tracking does not halt healthy sessions

**Given** both agents are running and publishing heartbeats piggybacked on their Party Bus PUB messages
**When** the Orchestrator's SUB sockets receive heartbeats
**Then** the Orchestrator records the last-seen timestamp per agent from receipt time and no halt is triggered while each heartbeat arrives before `HEARTBEAT_INTERVAL * HEARTBEAT_MISSED_COUNT`

### Criterion 2: Missed heartbeat halts both agents

**Given** one agent stops publishing (process killed or hung)
**When** N consecutive heartbeat intervals (configurable, default 3) pass without a message
**Then** the Orchestrator emits one `session_halt` control message with `reason: heartbeat_missed`, `missed_agent_id`, and `missed_count`; logs `heartbeat_missed` and `session_halt` events to `sessions.db`; both agents capture their current FSM state, enter latched `PAUSED`, cancel pending actions, and produce no further OS input

### Criterion 3: Recovery does not auto-resume

**Given** a halted session is recovered (agent restarted and heartbeats resume)
**When** the Orchestrator detects resumed heartbeats
**Then** the Orchestrator logs `party_bus_reconnected` with both agents' health status, but does not automatically resume input; only after both agents are healthy and an explicit `session_resume` control message with `{session_id, reason: "operator_resume", agent_ids}` is received do agents restore the FSM state captured at halt, log `session_resume`, and continue

### Criterion 4: Orchestrator does not restart processes during a halt

**Given** the Orchestrator has emitted a halt for a missed heartbeat
**When** a single agent process is still running
**Then** the Orchestrator signals both agents and does not restart either process; process restart, if needed, remains an explicit Tray/UI operation before the resume protocol

## Dependencies

- Party Bus heartbeat message contract on the existing agent PUB endpoint
- Orchestrator SUB monitoring for both agent endpoints
- Session DB event logging for `heartbeat_missed`, `session_halt`, `party_bus_reconnected`, and `session_resume`
- Agent pause/restore state handling and explicit operator resume path
- Control endpoint for `session_halt` and `session_resume` commands

## Notes

The Orchestrator is not a gameplay authority; it is the fail-safe monitor. Heartbeat loss triggers a coordinated, no-input pause on both agents, and recovery requires an explicit operator action before either agent resumes its pre-halt FSM state.

## Tasks / Subtasks

- [ ] Add heartbeat timestamp tracking in the Orchestrator per agent.
- [ ] Trigger `session_halt` after `HEARTBEAT_INTERVAL * HEARTBEAT_MISSED_COUNT` without auto-resume.
- [ ] Emit and persist `heartbeat_missed`, `session_halt`, `party_bus_reconnected`, and `session_resume` events.
- [ ] Ensure both agents latch `PAUSED` and restore their captured pre-halt state only on explicit resume.
- [ ] Validate missed-heartbeat and resume flows with deterministic tests.

## Dev Agent Record

### Implementation Plan

- Treat the Orchestrator as the only authority for declaring a halt after heartbeat loss.
- Record heartbeat receipt time and compare against `HEARTBEAT_INTERVAL * HEARTBEAT_MISSED_COUNT` before raising a halt.
- Keep pause semantics consistent with the shared contract: latch state, cancel pending action, and require explicit operator resume.

### Completion Notes

- This story remains in backlog until the heartbeat monitor and halt/resume control flow are implemented end-to-end and verified on both healthy and failed-agent scenarios.

## Change Log

- 2026-08-26: Updated story to reflect the final orchestrator contract: heartbeat monitoring on the Party Bus, fail-safe pause, and operator-only resume.
