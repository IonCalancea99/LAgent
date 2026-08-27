# Story 9.1: Lineage Resource Adapter & Validated Quest State/Profile Contract

Status: done

## Story

As Ion, I want quest metadata parsed and validated from the selected Lineage resource before any objective executes, so that the agent acts only on a verified quest contract.

## Acceptance Criteria

1. A valid resource is translated into canonical `QuestResource`, `ObjectiveStep`, `DialogueChoice`, and `QuestCheckpoint` models containing quest identity, starting NPC, ordered objectives, dialogue choices, completion indicators, route, timeouts, retries, and safe-stop conditions.
2. Missing, malformed, unknown, or unsupported resource values raise a typed validation error and prevent quest execution; no action is emitted from partial data.
3. Quest-enabled profile validation is additive and preserves existing fishing/combat profiles. An unknown quest or NPC enters an actionable safe-stop state.
4. Runtime code consumes only the canonical contract, keeping provider payload parsing isolated so provider format changes do not alter the FSM.

## Tasks / Subtasks

- [x] Define canonical quest models and validation errors in `lagent/common/types.py` or the established shared-types module. (AC: 1, 2)
- [x] Add isolated provider adapter and profile/schema validation under `lagent/agent/quest/`. (AC: 2-4)
- [x] Add a bounded Marcela/Supply Check resource fixture without hardcoding a generic quest engine. (AC: 1, 4)
- [x] Add tests for valid parsing, malformed order, missing fields, unsupported targets, and backwards-compatible profiles. (AC: 1-4)

### Review Findings

- [x] [Review][Patch] `QuestResourceAdapter.validate_resource` let a pydantic `ValidationError` (e.g. negative `timeout_seconds`/`retry_limit`) escape uncaught instead of the contracted `QuestResourceValidationError`, breaking the fail-closed guarantee (AC 2) [lagent/agent/quest/adapter.py] — fixed: wrapped `ObjectiveStep`/`QuestResource` construction and re-raise as `QuestResourceValidationError`.

## Dev Notes

Keep external data at the adapter boundary. Fail closed on unknown keys, missing objectives, invalid ordering, and unmappable values. Quest state remains agent-owned; use existing Pydantic and profile-loading conventions and the shared contract rather than ad hoc dictionaries.

Expected surfaces: `lagent/common/types.py`, `lagent/agent/quest/adapter.py`, `lagent/agent/quest/schema.py`, profile validation, and `tests/test_story_9_1_quest_resource_adapter.py`.

Dependencies: Epic 1 profile validation, Epic 2 perception, Story 4.2 startup identification. Architecture: AD-4, AD-12, AD-13.

## References

- [Planning story](../planning-artifacts/stories/9-1-lineage-resource-adapter-and-validated-quest-state-contract.md)
- [Epic definition](../planning-artifacts/epics.md)
- [Sprint change proposal](../planning-artifacts/sprint-change-proposal-2026-08-26.md)

## Dev Agent Record

### Completion Notes List

- Ultimate context engine analysis completed; implementation artifact promoted from the approved Epic 9 planning scope.
- Existing canonical resource adapter, quest/profile validation, and acceptance tests verified during Epic 9 implementation.
- Compact profile normalization repaired; validation: 5/5 Story 9.1 tests pass as part of the 54/54 Epic 9 suite.

### File List

- lagent/agent/quest/__init__.py
- lagent/agent/quest/adapter.py
- lagent/agent/quest/schema.py
- lagent/common/__init__.py
- lagent/common/types.py
- tests/test_story_9_1_quest_resource_adapter.py

## Change Log

- 2026-08-27: Reconciled verified Story 9.1 implementation and compact quest-profile normalization for review.
