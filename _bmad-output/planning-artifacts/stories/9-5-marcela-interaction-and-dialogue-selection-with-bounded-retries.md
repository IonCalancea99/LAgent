---
storyId: 9.5
epic: "Epic 9: Quest Mode"
title: "Marcela Interaction & Dialogue Selection with Bounded Retries"
status: ready-for-dev
---

# Story 9.5: Marcela Interaction & Dialogue Selection with Bounded Retries

## User Story

As Ion,
I want the NPC interaction and dialogue step to be explicitly bounded and validated,
so that the agent only engages Marcela with the correct quest option and never loops forever on a stale conversation state.

## Acceptance Criteria

### Criterion 1: Interaction is targeted and verified

**Given** the Agent reaches Marcela
**When** the interaction step begins
**Then** it only issues the interaction action for the expected NPC and confirms the NPC identity before the dialogue selection is attempted

**Given** the NPC is not visible or the interaction prompt is absent
**When** the interaction check is performed
**Then** the step fails with a positive `npc_not_found` or `interaction_timeout` reason and the quest enters the bounded retry path

### Criterion 2: Dialogue selection is evidence-based

**Given** the dialogue UI is open
**When** the agent evaluates response options
**Then** only the validated quest option is chosen, and that choice is tied to the objective text, NPC identity, and quest resource value

**Given** the choice is ambiguous or the OCR confidence is below threshold
**When** the dialogue response is determined
**Then** no dialogue action is sent and the system records a verification failure instead of guessing

### Criterion 3: Retry budget is enforced

**Given** the NPC interaction or dialogue selection fails due to timeout, ambiguity, or unrecognized prompt
**When** the retry limit is reached
**Then** the quest stops safely and logs the final interaction failure reason with the objective index and player state

**Given** the quest remains in a recoverable state before the retry cap
**When** a retry is attempted
**Then** the retry is bounded by the quest profile deadline and preserves the same session ID and objective trace

## Dependencies

- Story 9.1 quest contract and validation.
- Story 9.2 perception fixtures for dialogue and NPC recognition.
- Story 9.3 FSM verification gates.

## Developer Context

This story is where the quest becomes operationally real: the agent must interact with the NPC and choose the correct conversation option. The risk is not only missing the NPC; it is choosing a wrong option from a mutable or OCR-ambiguous dialogue screen. The design should therefore require positive matching against the quest resource and objective text before any response action is emitted.

Interaction should be bounded by the quest contract, not by a generic endless loop. If the required state is not found, the agent must stop or retry within the configured cap and record the cause cleanly.

## Technical Requirements

- Validate NPC identity before interaction dispatch.
- Select dialogue choices only after objective text and NPC contract match.
- Enforce retry limits and emit safe-stop reasons on exhaustion.
- Record interaction state transitions and failure reasons in telemetry.

## Testing Requirements

- Test successful Marcela interaction and valid dialogue choice selection.
- Test interaction failure when NPC is absent or not recognized.
- Test ambiguous dialogue options produce no action and a verification failure.
- Test retry exhaustion logs the final failure and transitions to a safe stop.

## Architecture Compliance

- AD-11: all interaction actions must remain within approved HSL dispatch and safety timing rules.
- AD-4: the state machine owns objective transitions and prevents silent guessing.
- AD-9: all interaction outcomes are logged to the shared session database.

## File Structure

Expected implementation surfaces: `lagent/agent/quest/interactions.py`, `lagent/agent/quest/dialogue.py`, and tests under `tests/test_story_9_5_quest_interaction.py`.

## Completion Status

Ready for development.

## Change Log

- 2026-08-26: Story created from Epic 9 requirement and sprint proposal.
