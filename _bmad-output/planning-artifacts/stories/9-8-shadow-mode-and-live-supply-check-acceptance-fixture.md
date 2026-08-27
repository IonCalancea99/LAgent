---
storyId: 9.8
epic: "Epic 9: Quest Mode"
title: "Shadow-Mode & Live Supply Check Acceptance Fixture"
status: ready-for-dev
---

# Story 9.8: Shadow-Mode & Live Supply Check Acceptance Fixture

## User Story

As Ion,
I want a proven acceptance fixture for the Marcela/Supply Check quest,
so that it is validated in deterministic shadow mode before any live session is allowed to complete the quest automatically.

## Acceptance Criteria

### Criterion 1: Shadow mode replays the full quest flow

**Given** a deterministic quest replay is loaded
**When** the Agent runs in shadow mode
**Then** it executes the same objective sequence, navigation path, and NPC interaction flow without generating OS input

**Given** a quest frame sequence is ambiguous or missing required evidence
**When** the replay is processed
**Then** the quest remains in a safe stop or retry state and does not claim success without verification

### Criterion 2: Live acceptance is gated behind deterministic pass

**Given** the shadow-mode replay passes all quest fixture checks
**When** the live session is initiated
**Then** the quest can be attempted under the same bounded rules, profile configuration, and session lifecycle safeguards

**Given** the live run fails a step that shadow mode validates as coverage-critical
**When** the failure is observed
**Then** the live system does not continue to completion and the operator is left with an actionable safe-stop state

### Criterion 3: Completion is accepted only with evidence

**Given** the final objective is reached
**When** the completion event is emitted
**Then** the success condition is backed by objective verification and not by a timer or a stale state snapshot

**Given** the quest ends without completion evidence
**When** the final state is evaluated
**Then** it is not treated as success and remains in a failed or safe-stop state

## Dependencies

- Stories 9.1–9.7 for contract, perception, FSM, route, interaction, recovery, and status projection.
- Epic 3 Shadow Mode and event replay infrastructure.
- Existing session lifecycle safeguards and telemetry flow.

## Developer Context

This is the proving story for Epic 9. The quest should pass a deterministic, replay-based harness before a live quest is allowed to complete. This is critical because quest behavior is stateful and highly sensitive to timing, route ambiguity, and erroneous NPC or dialogue recognition.

The acceptance path should be narrow and specific: the Supply Check quest, starting from Marcela in Kamael village, using a level-3 Orc Fighter. It is not a generic quest rule or broad world traversal story. The live version must remain safe by default and should only succeed when the same evidence path is verified in shadow mode.

## Technical Requirements

- Implement deterministic replay fixtures for the Marcela/Supply Check quest flow.
- Gate live quest completion behind successful shadow-mode validation.
- Keep all quest evidence and objective transitions traceable in session telemetry.
- Ensure the live attempt never bypasses the safe-stop and retry boundaries.

## Testing Requirements

- Test complete shadown-mode replay success and failure cases.
- Test live acceptance is blocked when the replay or validation contract is not met.
- Test quest completion requires explicit evidence and is not accepted on stale or default state.
- Test a full quest run logs objective-level state changes and completion/failure events deterministically.

## Architecture Compliance

- AD-3: shadow-mode remains a safe replay mechanism without generating OS input.
- AD-6: lifecycle and session safeguards remain intact during live quest trials.
- AD-9: quest success and failure data remain in the session event log for review.

## File Structure

Expected implementation surfaces: replay harness and acceptance tests under `tests/test_story_9_8_quest_acceptance.py`, plus any quest-specific fixtures under `recordings/` or `data/` as required.

## Completion Status

Ready for development.

## Change Log

- 2026-08-26: Story created from Epic 9 requirement and sprint proposal.
