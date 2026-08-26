---
storyId: 6.4
epic: "Epic 6: Combat Mode & Session Lifecycle"
title: "Inventory-Full Detection & Town Return"
status: ready
---

# Story 6.4: Inventory-Full Detection & Town Return

## User Story

As Ion,
I want the system to detect a full inventory condition and suspend the combat loop, execute a safe return to town, handle loot per configured rules, and resume the farming loop automatically,
So that the session never silently discards loot or requires Ion to manage inventory (FR-17).

## Acceptance Criteria

### Criterion 1: Full inventory detection suspends combat

**Given** the inventory-full visual indicator is detected in the game frame (YOLO or OCR)
**When** the condition is detected during a combat loop
**Then** the combat loop is suspended; WL transitions to a RETURNING state; the town return movement sequence executes

### Criterion 2: Loot rules are applied in town

**Given** WL is in town after inventory-full return
**When** loot rules from the profile are evaluated
**Then** items are deposited or dropped per the configured rules; no item is silently discarded without a profile rule authorizing it

### Criterion 3: Farming loop resumes after inventory handling

**Given** loot handling is complete
**When** the return sequence finishes
**Then** both agents resume the farming loop from IDLE; the inventory return event is logged to `sessions.db`

## Dependencies

- Warlord Combat FSM (Story 6.1) with RETURNING state handling
- Inventory-full visual detection in perception pipeline (YOLO or OCR)
- Agent profile `warlord.yaml` with town-return movement keys/sequence and loot-rule configuration
- PerceptionResult containing inventory status
- HSL for action dispatch (Story 3.x)
- Session database event logging

## Notes

Inventory management is a critical safety constraint: the bot must never drop items silently or discard loot without explicit authorization in the profile. The town-return flow is: detect full inventory → suspend combat → move to town → apply loot rules → resume farming. All loot actions are logged to prevent silent data loss.

## Tasks / Subtasks

- [ ] Add inventory-full detection condition to PerceptionResult (YOLO or OCR detection).
- [ ] Add RETURNING FSM state to Warlord FSM with town-return sequence and loot handling.
- [ ] Implement town return movement dispatch via HSL.
- [ ] Define loot rule schema in agent profile (e.g., "deposit all", "drop rare only").
- [ ] Implement loot rule evaluation and dispatch (drop/deposit) via HSL.
- [ ] Log inventory-full event and all loot actions with item details.
- [ ] Resume both agents to IDLE after return completes.
- [ ] Add deterministic tests with inventory-full scenarios and loot-rule validation.

## Dev Agent Record

### Implementation Plan

- Add `inventory_full` boolean to `PerceptionResult` from detection pipeline.
- Add RETURNING state to `lagent/agent/combat_fsm.py` with town-return sequence and loot handling.
- Implement loot rule matcher and action dispatcher; each rule produces a sequence of drop/deposit keys.
- Log inventory and loot events with rule matched and items affected.
- Create test in `tests/test_story_6_4_inventory_town_return.py` with inventory scenarios and loot-rule coverage.

### Completion Notes

(Pending implementation)

### File List

(Pending implementation)

## Change Log

- 2026-08-26: Story created from Epic 6 specification.
