---
storyId: 9.6
epic: "Epic 9: Quest Mode"
title: "Quest Checkpoint, Failure, and Lifecycle Recovery"
status: ready-for-dev
---

# Story 9.6: Quest Checkpoint, Failure, and Lifecycle Recovery

## User Story

As Ion,
I want quest progress and failure state to be checkpointed and recoverable,
so that the agent resumes safely from a verified objective or stops cleanly on death, disconnect, or restart without corrupting the quest state.

## Acceptance Criteria

### Criterion 1: Progress is checkpointed at objective boundaries

**Given** a quest objective is verified and completed
**When** the FSM transitions to the next objective
**Then** the checkpoint records the objective index, current objective status, and the verification source in a durable session record

**Given** the session ends or restarts before completion
**When** the quest state is restored
**Then** it resumes only from the last valid checkpoint or requires operator intervention

### Criterion 2: Lifecycle failures are handled safely

**Given** the Agent dies, disconnects, or the process restarts
**When** the quest state is reconstructed
**Then** the system validates whether the last objective completed prior to the interruption and either resumes from that checkpoint or enters a halt state

**Given** the quest cannot be resumed safely
**When** the failure is evaluated
**Then** a safe stop is issued and the session remains bounded without continuing through unknown quest state

### Criterion 3: Quest failure is observable and traceable

**Given** a quest fails due to timeout, route issue, ambiguous perception, or retry exhaustion
**When** the failure is emitted
**Then** the session log includes the failure reason, objective index, retry count, and the last verified evidence state

**Given** a prior objective had already been checkpointed
**When** the failure is reviewed
**Then** the operator can tell exactly where progress stopped without guessing at the last valid state

## Dependencies

- Story 9.1 quest contract and checkpoint schema.
- Story 9.3 quest FSM state transitions and terminal reasons.
- Epic 6 death recovery, shutdown, and lifecycle semantics.

## Developer Context

Questing adds a new failure surface beyond combat: objective continuity across restarts and session interruptions. The safest approach is to checkpoint only at validated objective boundaries so that a trust boundary exists between objective states. This prevents the system from resuming from unverified or ambiguous state.

Do not let the quest path bypass the lifecycle and session safety rules already in place. Recovery is allowed only from a verified checkpoint, and otherwise the quest must halt safely.

## Technical Requirements

- Implement checkpoint persistence at objective boundaries only.
- Allow recovery only from a valid quest checkpoint.
- Emit structured quest failure events with objective index, retries, and verification source.
- Integrate with the current session lifecycle and death-recovery semantics from Epic 6.

## Testing Requirements

- Test checkpoint persistence after objective success.
- Test restart after a confirmed checkpoint resumes from the correct objective.
- Test session interruption before a checkpoint causes safe stop.
- Test death recovery does not continue quest progression from ambiguous state.

## Architecture Compliance

- AD-4: checkpointed quest state remains agent-owned and scoped to the active session.
- AD-9: quest recovery logs remain in the session log and cannot bypass SQLite storage.
- AD-6: all recovery/restart semantics remain bounded and explicit.

## File Structure

Expected implementation surfaces: `lagent/agent/quest/checkpoint.py`, lifecycle integration under `lagent/agent/`, and tests under `tests/test_story_9_6_quest_recovery.py`.

## Completion Status

Ready for development.

## Change Log

- 2026-08-26: Story created from Epic 9 requirement and sprint proposal.
