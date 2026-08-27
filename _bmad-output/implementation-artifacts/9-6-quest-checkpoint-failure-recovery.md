# Story 9.6: Quest Checkpoint, Failure, and Lifecycle Recovery

---
baseline_commit: 67173eef8f54656f1b173e4aa302e573c99eb5ec
---

Status: done

## Story

As Ion, I want quest progress checkpointed only at verified objective boundaries, so that restart, death, disconnect, or shutdown resumes safely or stops without corrupting quest state.

## Acceptance Criteria

1. Completing an objective persists objective index, status, verification source, and session identity in a durable checkpoint before the next objective begins.
2. Restart/recovery resumes only from a valid verified checkpoint; interruption before a checkpoint requires operator intervention or safe stop.
3. Death, disconnect, and process restart use existing lifecycle semantics and never continue from ambiguous state.
4. Timeout, route, perception, and retry failures log objective index, retry count, reason, and last verified evidence.

## Tasks / Subtasks

- [x] Implement checkpoint persistence and validation in `lagent/agent/quest/checkpoint.py`. (AC: 1, 2)
- [x] Integrate checkpoint restore with existing lifecycle and death-recovery paths. (AC: 2, 3)
- [x] Emit traceable structured failure records through the session database. (AC: 4)
- [x] Test objective checkpointing, restart, pre-checkpoint interruption, and death recovery in `tests/test_story_9_6_quest_recovery.py`. (AC: 1-4)

## Dev Notes

Checkpoint only verified boundaries. Keep state agent-owned and scoped to the active session; do not create a parallel state store or bypass SQLite. Architecture: AD-4, AD-6, AD-9. Dependencies: Stories 9.1 and 9.3, Epic 6.

## References

- [Planning story](../planning-artifacts/stories/9-6-quest-checkpoint-failure-and-lifecycle-recovery.md)
- [Epic definition](../planning-artifacts/epics.md)

## Dev Agent Record

### Completion Notes List

- Promoted as an implementation-ready Epic 9 artifact.
- Added SQLite event-backed verified objective checkpoints and fresh-process reconstruction.
- Added lifecycle recovery decisions that ignore ambiguous mid-objective state and trace failures to the last positive evidence.
- Validation: 6/6 Story 9.6 tests and 44/44 Epic 9 tests through Story 9.6 pass.

### File List

- lagent/agent/lifecycle.py
- lagent/agent/quest/__init__.py
- lagent/agent/quest/checkpoint.py
- lagent/common/types.py
- tests/test_story_9_6_quest_recovery.py

## Change Log

- 2026-08-27: Implemented durable verified checkpoints, lifecycle restore decisions, and traceable quest failures.
