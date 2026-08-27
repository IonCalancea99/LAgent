# Story 9.4: Resource-Driven Kamael Village Navigation & Stuck Detection

---
baseline_commit: 67173eef8f54656f1b173e4aa302e573c99eb5ec
---

Status: done

## Story

As Ion, I want the Kamael village route driven by quest metadata with explicit stuck detection, so that the agent reaches Marcela without wandering or following stale movement instructions.

## Acceptance Criteria

1. The selected quest route executes as a bounded sequence of validated waypoints and actions from the resource contract, not a hardcoded single-purpose script.
2. Missing or incomplete route metadata fails closed. Waypoint timeout, missing NPC, ambiguous map evidence, and inconsistent route state produce explicit failure reasons.
3. Reroutes/retries are allowed only within configured limits; exhaustion enters safe stop and records objective and route context in session telemetry.
4. The agent verifies the expected area/NPC before transitioning to interaction.

## Tasks / Subtasks

- [x] Implement route resolution and waypoint execution in `lagent/agent/quest/navigation.py`. (AC: 1, 4)
- [x] Add timeout, stuck, NPC-not-found, and retry-budget handling. (AC: 2, 3)
- [x] Keep movement inside approved HSL dispatch and existing safety timing boundaries. (AC: 1-3)
- [x] Test valid route, absent metadata, waypoint timeout, ambiguity, and failure logging in `tests/test_story_9_4_quest_navigation.py`. (AC: 1-4)

## Dev Notes

This is a bounded route representation, not a generic world-graph planner. Quest navigation remains agent-local and uses existing lifecycle/recovery semantics. Architecture: AD-4, AD-11, AD-12. Dependencies: Stories 9.1-9.2 and Epic 6.

## References

- [Planning story](../planning-artifacts/stories/9-4-resource-driven-kamael-village-navigation-and-stuck-detection.md)
- [Epic definition](../planning-artifacts/epics.md)

## Dev Agent Record

### Completion Notes List

- Promoted as an implementation-ready Epic 9 artifact.
- Added injected waypoint resolution and bounded route execution through the approved HSL dispatch boundary.
- Added area/NPC verification, timeout, ambiguity, inconsistent-state, stuck, retry-exhaustion, and route-context telemetry handling.
- Validation: 6/6 Story 9.4 tests and 33/33 Epic 9 tests through Story 9.4 pass.

### File List

- lagent/agent/quest/__init__.py
- lagent/agent/quest/navigation.py
- tests/test_story_9_4_quest_navigation.py

## Change Log

- 2026-08-27: Implemented resource-driven bounded navigation, HSL dispatch, verification, and stuck recovery.
