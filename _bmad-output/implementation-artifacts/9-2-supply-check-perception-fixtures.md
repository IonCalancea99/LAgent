# Story 9.2: Supply Check Perception Fixtures for Marcela, Dialogue, Objectives, and Completion

---
baseline_commit: 67173eef8f54656f1b173e4aa302e573c99eb5ec
---

Status: done

## Story

As Ion, I want deterministic perception fixtures for the Marcela quest, so that NPCs, quest text, dialogue, and completion cues are recognized from replayable evidence before live play.

## Acceptance Criteria

1. Deterministic fixtures produce positive, contract-compatible evidence for Marcela, the quest objective, interaction prompt, dialogue options, and completion.
2. Empty, blurred, occluded, missing, or low-confidence evidence returns `not_found`, `ambiguous`, or `verify_failed`; it never creates a false positive or selects dialogue.
3. Replaying the same fixture produces the same normalized perception result and records raw OCR text where a dialogue choice is selected.
4. Completion requires a positive objective transition and explicit completion evidence, not a timer or stale snapshot.

## Tasks / Subtasks

- [x] Add replay frames/text fixtures for NPC, objective, dialogue, and completion states. (AC: 1, 3)
- [x] Map inference/OCR output to the Story 9.1 quest evidence contract. (AC: 1, 4)
- [x] Add negative and ambiguous fixtures for each perception class. (AC: 2)
- [x] Add deterministic repeated-replay tests under `tests/test_story_9_2_supply_check_perception.py`. (AC: 1-4)

## Dev Notes

Extend the existing GPU/inference and OCR conventions; do not put quest decisions in model classes. Keep this scope limited to Marcela/Supply Check. Architecture: AD-2, AD-10, AD-12. Dependencies: Epic 2, Story 9.1, Epic 7 model patterns.

Expected surfaces: `lagent/gpu_server/quest_fixture.py`, `models/quest/` or existing fixture location, and focused tests.

## References

- [Planning story](../planning-artifacts/stories/9-2-supply-check-perception-fixtures-marcela-dialogue-objectives.md)
- [Epic definition](../planning-artifacts/epics.md)

## Dev Agent Record

### Completion Notes List

- Promoted as an implementation-ready Epic 9 artifact.
- Added canonical fail-closed quest perception evidence and deterministic Supply Check fixture evaluation.
- Added positive, missing, blurred, occluded, low-confidence, stale-transition, and explicit-completion replay coverage.
- Validation: 17/17 Story 9.2 tests and 22/22 Story 9.1-9.2 quest tests pass. Full suite: 278 passed, 1 skipped, 17 unrelated pre-existing/environment failures.

### File List

- lagent/agent/quest/schema.py
- lagent/common/__init__.py
- lagent/common/types.py
- lagent/gpu_server/quest_fixture.py
- lagent/gpu_server/supply_check_fixtures.json
- tests/test_story_9_2_supply_check_perception.py

## Change Log

- 2026-08-27: Implemented deterministic Supply Check perception fixtures and canonical evidence normalization.
