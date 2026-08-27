# Story 9.5: Marcela Interaction & Dialogue Selection with Bounded Retries

---
baseline_commit: 67173eef8f54656f1b173e4aa302e573c99eb5ec
---

Status: done

## Story

As Ion, I want Marcela interaction and dialogue selection explicitly validated and bounded, so that the agent never chooses a wrong option or loops on a stale conversation state.

## Acceptance Criteria

1. Interaction is dispatched only after positive Marcela identity and interaction-prompt evidence; missing evidence produces `npc_not_found` or `interaction_timeout`.
2. A dialogue option is selected only when NPC identity, objective text, and resource-defined choice match with sufficient OCR confidence. Ambiguous choices produce no action.
3. Interaction and dialogue retries obey the quest deadline and retry cap, preserving session ID and objective trace; exhaustion safely stops with an actionable reason.
4. State transitions and failure reasons are written to existing telemetry.

## Tasks / Subtasks

- [x] Implement targeted interaction validation in `lagent/agent/quest/interactions.py`. (AC: 1)
- [x] Implement resource-backed dialogue matching in `lagent/agent/quest/dialogue.py`. (AC: 2)
- [x] Integrate bounded retries and FSM verification gates. (AC: 3, 4)
- [x] Test successful choice, absent NPC, low-confidence/ambiguous options, and retry exhaustion in `tests/test_story_9_5_quest_interaction.py`. (AC: 1-4)

### Review Findings

- [x] [Review][Patch] `DialogueSelector.select()` indexed `resource.objective_sequence[objective_index]` without a bounds check, risking an uncaught `IndexError` instead of a safe ambiguous-dialogue failure (AC 2, 3) [lagent/agent/quest/dialogue.py] — fixed: added a bounds guard returning `DialogueMatch(None, "objective_index_out_of_range")`.
- [x] [Review][Patch] `QuestInteractionController.begin_interaction()` indexed `resource.objective_sequence[self.objective_index]` without a bounds check, risking an uncaught `IndexError` instead of a safe-stop failure (AC 1, 3) [lagent/agent/quest/interactions.py] — fixed: added a bounds guard returning a `objective_index_out_of_range` failure outcome.

## Dev Notes

All input actions stay within approved HSL dispatch and safety timing rules. Never guess from partial OCR or default to the first dialogue option. Architecture: AD-4, AD-9, AD-11. Dependencies: Stories 9.1-9.3.

## References

- [Planning story](../planning-artifacts/stories/9-5-marcela-interaction-and-dialogue-selection-with-bounded-retries.md)
- [Epic definition](../planning-artifacts/epics.md)

## Dev Agent Record

### Completion Notes List

- Promoted as an implementation-ready Epic 9 artifact.
- Added explicit Marcela/prompt gates and exact resource-backed dialogue matching tied to current objective OCR.
- Added HSL-only interaction/click dispatch, quest deadline, retry exhaustion, FSM-compatible outcomes, and trace telemetry.
- Validation: 5/5 Story 9.5 tests and 38/38 Epic 9 tests through Story 9.5 pass.

### File List

- lagent/agent/quest/__init__.py
- lagent/agent/quest/dialogue.py
- lagent/agent/quest/interactions.py
- lagent/common/types.py
- lagent/gpu_server/quest_fixture.py
- tests/test_story_9_5_quest_interaction.py

## Change Log

- 2026-08-27: Implemented validated Marcela interaction, exact dialogue matching, bounded retries, and telemetry.
