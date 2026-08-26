---
storyId: 6.1
epic: "Epic 6: Combat Mode & Session Lifecycle"
title: "Warlord Combat FSM — Pull, Fight, Loot"
status: ready
---

# Story 6.1: Warlord Combat FSM — Pull, Fight, Loot

## User Story

As Ion,
I want the Warlord Agent to implement IDLE → PULLING → FIGHTING → LOOTING FSM states driven by PerceptionResult detections,
So that the WL autonomously executes the pull-AoE-loot combat cycle and the BC Policy module selects within-state action sequences (FR-5 WL Combat).

## Acceptance Criteria

### Criterion 1: Mob detection triggers pull transition

**Given** the WL Agent is in IDLE and a mob detection appears in the mob_area ROI
**When** the FSM evaluates the transition condition
**Then** WL transitions to PULLING; the BC Policy module for PULLING selects and executes the pull skill sequence via HSL

### Criterion 2: Melee range triggers fighting transition

**Given** WL is in PULLING and the mob reaches melee range (detection position shifts to center frame)
**When** the transition condition is met
**Then** WL transitions to FIGHTING; the AoE skill rotation BC Policy executes

### Criterion 3: Mob clear triggers loot transition

**Given** WL is in FIGHTING and all mob detections are gone (mob_area ROI clear)
**When** the transition condition is met
**Then** WL transitions to LOOTING; loot key sequence executes; WL returns to IDLE after loot window closes or timeout
**And** each FSM transition is written to `sessions.db` events table within one decision cycle

## Dependencies

- Warlord Agent FSM base loop (Story 4.1) with state machine infrastructure
- BC Policy module for action selection within each FSM state
- PerceptionResult containing mob detections with position and confidence
- Agent profile `warlord.yaml` with pull skill key binding, AoE rotation sequence, loot key, and transition confidence thresholds
- HSL for action dispatch (Story 3.x)
- Session database event logging

## Notes

The Warlord Combat FSM is the core loop for combat farming. Transitions are driven by detection conditions and mob positioning heuristics (melee range detection via bbox proximity). Each FSM state has a corresponding BC Policy selector that produces the in-state action sequence.

## Tasks / Subtasks

- [ ] Define IDLE, PULLING, FIGHTING, LOOTING FSM states with transition guards.
- [ ] Implement mob detection condition (presence + confidence threshold in mob_area ROI).
- [ ] Implement melee-range detection condition (bbox center proximity to frame center).
- [ ] Implement mob-clear condition (no detections in mob_area for timeout window).
- [ ] Wire BC Policy selection into each state handler.
- [ ] Log FSM transitions to `sessions.db` events table.
- [ ] Add deterministic FSM tests with seeded mob detection sequences.
- [ ] Validate loot window timeout handling.

## Dev Agent Record

### Implementation Plan

- Create `lagent/agent/combat_fsm.py` with the state machine class extending the base loop FSM.
- Define transition conditions as detection-based guards and bbox-proximity heuristics.
- Wire BC Policy `select_action()` into each state handler for in-state action selection.
- Log each transition as an event in `sessions.db` via the session logger.
- Create deterministic test harness in `tests/test_story_6_1_warlord_combat.py` that replays mob detection sequences and validates state transitions.

### Completion Notes

(Pending implementation)

### File List

(Pending implementation)

## Change Log

- 2026-08-26: Story created from Epic 6 specification.
