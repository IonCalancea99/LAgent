# Story 9.3: Deterministic Quest FSM & Positive Objective Verification

---
baseline_commit: 67173eef8f54656f1b173e4aa302e573c99eb5ec
---

Status: done

## Story

As Ion, I want a bounded quest FSM that advances only on positive objective verification, so that the agent cannot drift, loop, or claim completion without evidence.

## Acceptance Criteria

1. The FSM starts in a known state and uses explicit states for discovery, navigation, interaction, verification, retry, pause, complete, and safe stop as applicable.
2. An objective advances only after positive evidence from perception, quest state, or the validated resource contract. Timer-only or stale evidence cannot advance it.
3. Timeout, ambiguity, failed navigation, and failed interaction consume a configured retry budget; exhaustion produces a terminal safe-stop reason.
4. Duplicate or stale objective events are ignored, and each transition logs objective index, state, retries, reason, and terminal result.

## Tasks / Subtasks

- [x] Implement agent-local quest state and deterministic transition rules in `lagent/agent/quest/fsm.py` and `state.py`. (AC: 1, 2)
- [x] Add positive-verification and retry gates driven by the canonical contract. (AC: 2, 3)
- [x] Emit structured events through the existing session event path. (AC: 4)
- [x] Test happy path, blocked progression, retry exhaustion, duplicate events, and stale events in `tests/test_story_9_3_quest_fsm.py`. (AC: 1-4)

## Dev Notes

Keep quest logic inside the Agent process and do not bypass lifecycle boundaries. Reuse shared contracts and SQLite telemetry; do not embed FSM decisions in the orchestrator or perception layer. Architecture: AD-4, AD-9, AD-12. Dependencies: Stories 9.1-9.2 and Story 4.1.

## References

- [Planning story](../planning-artifacts/stories/9-3-deterministic-quest-fsm-positive-objective-verification.md)
- [Epic definition](../planning-artifacts/epics.md)

## Dev Agent Record

### Completion Notes List

- Promoted as an implementation-ready Epic 9 artifact.
- Added monotonic quest events and explicit discovery, navigation, interaction, verification, retry, complete, paused, and safe-stop states.
- Objective progression now requires current-objective `found` evidence; stale, duplicate, timer-only, and ambiguous events cannot advance.
- Validation: 5/5 Story 9.3 tests and 27/27 Epic 9 tests through Story 9.3 pass.

### File List

- lagent/agent/quest/__init__.py
- lagent/agent/quest/fsm.py
- lagent/agent/quest/state.py
- tests/test_story_9_3_quest_fsm.py

## Change Log

- 2026-08-27: Implemented deterministic quest FSM, bounded retries, event ordering, and transition telemetry.
