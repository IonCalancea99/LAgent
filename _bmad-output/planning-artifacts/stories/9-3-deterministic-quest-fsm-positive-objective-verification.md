---
storyId: 9.3
epic: "Epic 9: Quest Mode"
title: "Deterministic Quest FSM & Positive Objective Verification"
status: ready-for-dev
---

# Story 9.3: Deterministic Quest FSM & Positive Objective Verification

## User Story

As Ion,
I want a bounded quest FSM that advances only on positive objective verification,
so that the agent cannot drift, loop, or claim quest completion without clear evidence from perception and object state.

## Acceptance Criteria

### Criterion 1: The quest FSM has deterministic states

**Given** the quest session starts
**When** the FSM initializes
**Then** it enters a known initial state such as `DISCOVERING`, `NAVIGATING`, `INTERACTING`, `VERIFYING`, `COMPLETE`, or `SAFE_STOP`

**Given** the objective is complete or evidence is ambiguous
**When** the evaluator runs
**Then** the FSM moves to a terminal state with a specific reason, not an implicit or silent success

### Criterion 2: Objective advancement requires positive verification

**Given** a quest step is ready to advance
**When** the agent evaluates the objective result
**Then** it advances to the next step only after explicit verification from perception, quest state, or a validated resource contract

**Given** the objective remains unverified after a timeout or retry limit
**When** the step is evaluated
**Then** the quest enters `SAFE_STOP` with the right failure reason and the session is not allowed to continue blindly

### Criterion 3: Retries are bounded and logged

**Given** a navigation or interaction attempt fails
**When** retries are consumed
**Then** the next step is blocked by a bounded safety gate and the failure is logged with the associated objective index and retry count

**Given** a quest outcome is repeated or stale
**When** the FSM processes it
**Then** duplicate or old events are ignored and cannot advance the objective state

## Dependencies

- Story 9.1 quest resource contract and validation.
- Story 9.2 perception fixtures and objective detection rules.
- Story 4.1 Agent base loop and runtime event flow.

## Developer Context

The core risk in questing is invalid advancement. Unlike fishing or combat, a quest cannot simply keep trying until time runs out; it must move through objective states with evidence-backed decision gates. This FSM should be small and explicit, with a positive verification gate before each transition.

Keep the quest FSM local to the agent and avoid embedding quest logic into the orchestration layer. The model should support both successful completion and safe stop, not only a happy path. Use the quest contract to define objective order, allowed actions, timeout limits, and terminal states.

## Technical Requirements

- Implement a deterministic objective state machine with bounded retry and verification checks.
- Ensure objective transitions are gated by positive evidence and not timer-only completion.
- Add structured quest events to telemetry for objective index, state, retries, failure reason, and terminal result.
- Support `COMPLETE`, `SAFE_STOP`, `PAUSED`, and `RETRYING` terminal or intermediate states as needed.

## Testing Requirements

- Unit test valid state transitions for a known quest sequence.
- Unit test blocked progression when the objective remains unverified.
- Unit test retry exhaustion and terminal state creation.
- Unit test duplicate or stale objective events do not advance the quest.

## Architecture Compliance

- AD-4: Quest FSM remains within the Agent process and does not bypass lifecycle boundaries.
- AD-9: quest state is recorded to the shared SQLite session event log.
- AD-12: the shared contract is used for cross-module communication; the quest FSM does not reach into unrelated runtime code.

## File Structure

Expected implementation surfaces: `lagent/agent/quest/fsm.py`, `lagent/agent/quest/state.py`, and tests under `tests/test_story_9_3_quest_fsm.py`.

## Completion Status

Ready for development.

## Change Log

- 2026-08-26: Story created from Epic 9 requirement and sprint proposal.
