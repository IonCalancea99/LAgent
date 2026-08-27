# Story 9.8: Shadow-Mode & Live Supply Check Acceptance Fixture

---
baseline_commit: 67173eef8f54656f1b173e4aa302e573c99eb5ec
---

Status: done

## Story

As Ion, I want a deterministic acceptance fixture for the Marcela/Supply Check quest, so that shadow mode proves the full evidence path before a live session can complete it automatically.

## Acceptance Criteria

1. Shadow replay covers the full bounded flow for a level-3 Orc Fighter in Kamael village, including objective sequence, navigation, Marcela interaction, dialogue, and completion, without OS input.
2. Missing or ambiguous evidence keeps replay in retry or safe stop and never claims success.
3. Live completion is gated behind a passing shadow validation using the same contract, profile, retry limits, and lifecycle safeguards.
4. Final success requires explicit objective and completion evidence; stale snapshots, timers, or default state are never sufficient. Objective-level events are deterministic and reviewable.

## Tasks / Subtasks

- [x] Build the end-to-end Supply Check replay fixture and harness. (AC: 1, 2)
- [x] Add a live-completion gate tied to deterministic shadow validation. (AC: 3)
- [x] Verify session telemetry contains each objective transition and terminal result. (AC: 4)
- [x] Test successful and failing shadow replay, blocked live acceptance, stale evidence, and full event trace in `tests/test_story_9_8_quest_acceptance.py`. (AC: 1-4)

## Dev Notes

This is the proving story for the narrow V1 quest slice, not a generic quest framework. Shadow mode must remain free of OS input, and live execution must retain safe-stop and retry boundaries. Architecture: AD-3, AD-6, AD-9. Dependencies: Stories 9.1-9.7, Epic 3 shadow mode, existing lifecycle safeguards.

## References

- [Planning story](../planning-artifacts/stories/9-8-shadow-mode-and-live-supply-check-acceptance-fixture.md)
- [Epic definition](../planning-artifacts/epics.md)

## Dev Agent Record

### Completion Notes List

- Promoted as an implementation-ready Epic 9 artifact.
- Added tracked level-3 Orc Fighter/Kamael Village fixture and an end-to-end harness using real perception, FSM, navigation, interaction, checkpoint, telemetry, and shadow HSL components.
- Added exact contract/profile fingerprint gating for live attempts and fail-closed stale, ambiguous, missing, and incomplete evidence paths.
- Validation: 5/5 Story 9.8 tests and 54/54 complete Epic 9 tests pass; touched modules compile and editor diagnostics are clean. Full repository suite: 313 passed, 1 skipped, 14 unrelated environment/pre-existing failures.

### File List

- lagent/agent/quest/__init__.py
- lagent/agent/quest/acceptance.py
- lagent/agent/quest/fixtures/supply_check_acceptance.json
- tests/test_story_9_8_quest_acceptance.py

## Change Log

- 2026-08-27: Implemented deterministic full-flow shadow acceptance and exact-contract live quest gating.
