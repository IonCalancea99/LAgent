---
storyId: 9.1
epic: "Epic 9: Quest Mode"
title: "Lineage Resource Adapter & Validated Quest State/Profile Contract"
status: ready-for-dev
---

# Story 9.1: Lineage Resource Adapter & Validated Quest State/Profile Contract

## User Story

As Ion,
I want the quest metadata to be parsed and validated from the selected Lineage resource before any objective executes,
so that the agent only acts on a verified quest contract instead of guessing at NPCs, dialogue, or completion conditions.

## Acceptance Criteria

### Criterion 1: Resource parsing is fail-closed

**Given** a valid Lineage quest resource is available for the chosen quest
**When** the adapter loads the resource
**Then** it extracts the quest ID, quest name, starting NPC, objective list, available dialogue choices, completion indicators, and retry/time limits into a canonical internal model

**Given** the resource is missing required fields or contains malformed values
**When** the parser validates it
**Then** it raises a `QuestResourceValidationError` or equivalent and blocks quest execution rather than proceeding with partial data

### Criterion 2: Quest state and profile schema are explicit

**Given** the quest profile is loaded
**When** the schema validates the quest configuration
**Then** all required fields exist for `quest_id`, `quest_name`, `starting_npc`, `objective_sequence`, `dialogue_options`, `navigation_route`, `timeouts`, `retries`, and `safe_stop_conditions`

**Given** an unsupported or unknown quest is selected
**When** the config is validated
**Then** the session enters a safe stop state with an actionable reason instead of defaulting to a generic quest loop

### Criterion 3: External data stays outside the runtime contract

**Given** the Lineage resource is fetched from the external provider
**When** the data is normalized
**Then** the runtime only consumes the internal quest contract, not raw web payloads or ad hoc dictionaries

**Given** the external resource format changes
**When** the adapter is updated
**Then** the Agent FSM remains unchanged as long as the canonical quest contract still validates

## Dependencies

- Epic 1 YAML profile validation and shared config schema.
- Epic 2 perception pipeline for objective and NPC evidence.
- Story 4.2 character identification and startup validation.
- `lineage.ru` or equivalent resource source for the target quest metadata.

## Developer Context

The quest capability must be resource-driven but bounded. We are not building a universal quest engine in this sprint; we are defining a strict adapter layer to convert provider data into a small internal contract that the Agent can safely reason about.

Keep the external resource parser isolated at the boundary and fail closed on unknown keys, missing quest steps, or data that cannot be mapped to a verified objective structure. The internal contract should contain only the information the Agent needs for navigation, NPC interaction, dialogue choice, verification, and safe-stop behavior.

Do not allow free-form quest fields in YAML without a schema. Add quest-specific profile entries in a backwards-compatible way so non-quest profiles remain valid and unchanged.

## Technical Requirements

- Define a canonical internal model for `QuestResource`, `ObjectiveStep`, `DialogueChoice`, and `QuestCheckpoint`.
- Validate resource fields before any quest action is emitted.
- Keep the external parser and runtime contract separate, with explicit translation rules.
- Support dynamic discovery for the selected quest route without hardcoding all quest data.
- Preserve existing fishing/combat profile validation and ensure the quest schema is additive, not destructive.

## Testing Requirements

- Unit test valid resource parsing for the Marcela/Supply Check quest.
- Unit test missing required fields and malformed objective order causing validation failure.
- Unit test profile schema acceptance for a quest-enabled profile and rejection for invalid values.
- Test the adapter rejects unknown target NPC or objective before the session begins.

## Architecture Compliance

- AD-4: agent-owned state remains local to the Agent process.
- AD-12: shared types remain centralized and versioned.
- AD-13: quest config remains profile-driven and safe by default.

## File Structure

Expected implementation surfaces: `lagent/common/types.py`, `lagent/agent/quest/adapter.py`, `lagent/agent/quest/schema.py`, and profile validation updates under `profiles/`. Add focused tests under `tests/test_story_9_1_quest_resource_adapter.py`.

## Completion Status

Ready for development.

## Change Log

- 2026-08-26: Story created from Epic 9 requirement and sprint proposal.
