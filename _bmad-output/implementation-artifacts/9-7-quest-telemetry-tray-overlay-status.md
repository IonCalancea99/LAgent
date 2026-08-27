# Story 9.7: Quest Telemetry & Tray/Overlay Status

---
baseline_commit: 67173eef8f54656f1b173e4aa302e573c99eb5ec
---

Status: done

## Story

As Ion, I want quest progress and failure state visible in the existing tray and overlay, so that I can monitor the active objective without guessing whether the session is still running.

## Acceptance Criteria

1. An active quest projection shows quest name, current objective, objective index, and running/paused/complete/failed status.
2. Safe-stop states show concise operator-readable reasons such as `npc_not_found`, `route_stuck`, or `retry_limit_reached`; completion preserves the final objective index.
3. No-quest and new-session views clear prior quest text. Duplicate or stale events from older sessions cannot overwrite current state.
4. UI remains a read-only projection of existing session telemetry and does not own quest decisions.

## Tasks / Subtasks

- [x] Extend the existing telemetry model/projection with quest fields and event ordering. (AC: 1, 3)
- [x] Render compact quest summary and failure reason in tray and overlay surfaces. (AC: 1, 2)
- [x] Add tests for active, idle, complete, failure, stale, and duplicate events in `tests/test_story_9_7_quest_status_projection.py`. (AC: 1-4)

## Dev Notes

Reuse Epic 8 tray/overlay lifecycle and session DB as the source of truth. Do not add a quest state file or move FSM logic into UI. Architecture: AD-5, AD-9, AD-12. Dependencies: Stories 9.3 and 9.6, Epic 8.

## References

- [Planning story](../planning-artifacts/stories/9-7-quest-telemetry-and-tray-overlay-status.md)
- [Epic definition](../planning-artifacts/epics.md)

## Dev Agent Record

### Completion Notes List

- Promoted as an implementation-ready Epic 9 artifact.
- Added session-scoped monotonic quest event projection with active, paused, complete, failed, and cleared states.
- Added shared compact formatting to tray and overlay while preserving UI read-only ownership.
- Validation: 5/5 Story 9.7 tests, 10 passed/1 skipped UI compatibility tests, and 49/49 Epic 9 tests through Story 9.7 pass.

### File List

- lagent/agent/quest/checkpoint.py
- lagent/agent/quest/fsm.py
- lagent/ui/overlay.py
- lagent/ui/telemetry.py
- lagent/ui/tray.py
- tests/test_story_9_7_quest_status_projection.py

## Change Log

- 2026-08-27: Implemented ordered quest telemetry projection and compact tray/overlay status rendering.
