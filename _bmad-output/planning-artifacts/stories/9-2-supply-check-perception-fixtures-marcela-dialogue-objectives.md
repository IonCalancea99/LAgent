---
storyId: 9.2
epic: "Epic 9: Quest Mode"
title: "Supply Check Perception Fixtures for Marcela, Dialogue, Objectives, and Completion"
status: ready-for-dev
---

# Story 9.2: Supply Check Perception Fixtures for Marcela, Dialogue, Objectives, and Completion

## User Story

As Ion,
I want a deterministic perception harness for the Marcela quest,
so that the agent can recognize NPCs, quest text, dialogue options, and completion markers from the same cues it will see in live play.

## Acceptance Criteria

### Criterion 1: Objective and NPC markers are identifiable

**Given** the quest quest log and targeted NPC are visible in the game viewport
**When** the GPU inference and OCR pipeline runs on those frames
**Then** it produces a positive detection for `marcela`, a quest objective label or text block, and any required interaction prompt or dialogue trigger

**Given** the target area is empty, blurred, or missing the expected NPC
**When** the perception layer is called
**Then** it returns `not_found` or `ambiguous` rather than a false positive, so downstream quest logic can halt safely

### Criterion 2: Dialogue options are readable and stable

**Given** the dialogue UI is open near the quest NPC
**When** OCR and label extraction run
**Then** the agent can distinguish the correct response option from distractor text and record the raw text values for the selected option

**Given** dialogue text is partially occluded or the OCR confidence is too low
**When** the perception result is evaluated
**Then** the quest FSM marks the state as `verify_failed` and does not select a dialogue choice without positive validation

### Criterion 3: Completion signals are explicit

**Given** the quest objective is completed
**When** the final framed state is evaluated
**Then** the perception pipeline yields a completion signal consistent with the canonical quest completion contract, including a positive objective transition and a safe terminal condition

**Given** the completion signal is missing or inconsistent
**When** the objective is checked
**Then** the agent remains in the objective verification state until a strong evidence signal exists

## Dependencies

- Epic 2 Perception Pipeline and OCR inference path.
- Story 9.1 quest contract definition and normalized objective fields.
- Existing object label and OCR model training patterns from Epic 7.

## Developer Context

Questing is perception-heavy because objective advancement must be based on evidence, not timers. Build a fixture set built around the Marcela/Supply Check quest using the same repository conventions as other inference tests: deterministic replay frames, OCR text fixtures, objective snapshots, and a small set of negative cases.

The goal is to validate the contract before wiring the FSM. The quest-specific perception data should be narrow and explicit: NPC recognition, dialogue option text, objective/prompt text, and completion acknowledgment. Do not broaden this story to generic NPC recognition or broad world-state parsing.

## Technical Requirements

- Create fixture coverage for reached NPC, dialogue prompt, response selection, and quest completion.
- Include at least one failure/ambiguous case for each major perception class.
- Ensure perception values map cleanly to the canonical quest objective contract from Story 9.1.
- Keep the output contract deterministic and testable without live game access.

## Testing Requirements

- Test zero-false-positive detection for missing NPC or blocked dialogue.
- Test OCR extraction of the Marcela dialogue options and objective text.
- Test quest-completion detection with both valid and invalid evidence states.
- Add fixture replay tests that verify the same quest state is recognized consistently across repeated inputs.

## Architecture Compliance

- AD-2: all quest perception remains in the GPU server and inference path.
- AD-10: perception contracts stay centralized and authoritative.
- AD-12: no quest logic is embedded into OCR or YOLO model classes.

## File Structure

Expected implementation surfaces: `lagent/gpu_server/quest_fixture.py`, `models/quest/` or equivalent fixture labels, and tests under `tests/test_story_9_2_supply_check_perception.py`.

## Completion Status

Ready for development.

## Change Log

- 2026-08-26: Story created from Epic 9 requirement and sprint proposal.
