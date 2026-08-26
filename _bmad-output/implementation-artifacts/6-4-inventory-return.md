# Story 6.4: Inventory-Full Detection and Town Return

Status: done

## User Story

As Ion,
I want the WL Agent to detect full inventory from perception/YOLO/OCR signals, suspend combat, execute configured town navigation and deposit/drop rules, and resume combat when ready,
So that WL never discards loot without an authorized rule and can return autonomously from farming runs with full inventory management (FR-17, Phase 4 of Epic 6).

## Acceptance Criteria

**AC-1:** Inventory-full detection from normalized signals
- Given a PerceptionResult contains inventory-full detections or OCR values (e.g., "inventory_full", "full_inventory")
- When the Agent processes perception
- Then `detect_lifecycle_signal()` returns a `LifecycleSignal` with name "inventory_full" and current timestamp

**AC-2:** WL transitions to RETURNING and suspends combat
- Given inventory-full is detected in any combat state (IDLE, PULLING, FIGHTING, LOOTING, BUFFING)
- When the FSM processes the signal
- Then WL state transitions to RETURNING; the current session context is preserved for resumption

**AC-3:** Town navigation executed through HSL
- Given WL is in RETURNING state and the profile has configured return actions
- When the Agent ticks
- Then each return action (e.g., "key_press:t", movement, navigate to town) is returned via `next_action()` and dispatched through HSL
- And actions are emitted in configured order until town handling completes

**AC-4:** Deposit and drop rules are honored
- Given return actions complete and WL is in town
- When loot disposition is evaluated
- Then for each item in inventory:
  - If a matching deposit rule exists (e.g., "materials": "deposit"), the item is deposited
  - If a matching drop rule exists (e.g., "junk": "drop"), the item is dropped
  - If no rule matches, the item is retained and a warning/event is logged

**AC-5:** PP does not cast while WL is RETURNING
- Given WL is in RETURNING state
- When PP evaluates buff timers
- Then PP Safety Check defers all casts
- And no offensive actions are emitted (enforced by ProphetBuffPolicy's PAUSED/DEAD/RETURNING/STOPPED suppression)

**AC-6:** Resume combat after town return
- Given town handling is complete (all actions dispatched)
- When `next_tick()` is called
- Then WL transitions to IDLE and combat resumes from that state

**AC-7:** Inventory-full detection is idempotent
- Given inventory-full has been detected and town return is in progress
- When duplicate inventory-full frames or multiple Party Bus messages arrive
- Then the return sequence is not repeated; state remains RETURNING until completion

**AC-8:** All loot dispositions logged and no silent discard
- Given deposit and drop rules are evaluated
- When each disposition decision is made
- Then `inventory_return_action` event logged with item name, rule type, and action taken
- And any item without a matching rule triggers a warning event and is retained

## Dependencies

- `detect_lifecycle_signal()` and `InventoryReturnController` from `lagent.agent.lifecycle` (already exists)
- Perception fixtures with inventory-full detections
- Party Bus peer state relay (Story 5.3)
- Profile-configured return and deposit/drop rules
- Current-frame PerceptionResult
- Session DB for event logging

## Implementation Plan

### 1. Wire inventory-full detection into WarlordCombatFSM

- Detect inventory_full signal alongside death signal in perception
- On detection: transition to RETURNING, call `InventoryReturnController.begin()`
- Log inventory_detected event with snapshot

### 2. Dispatch return and disposition actions from Warlord FSM

- While in RETURNING state, query `return_controller.next_action()` each tick
- Return action from FSM until `return_controller.next_action()` returns None
- Then call `return_controller.complete()` to transition back to IDLE

### 3. Verify PP defers during RETURNING

- ProphetBuffPolicy already suppresses actions in RETURNING state
- Verify Party Bus publishes WL RETURNING state so PP observes it

### 4. Write focused tests

**Test file:** `tests/test_story_6_4_inventory_return.py`

Tests to write:
- Inventory-full signal detection from perception
- WL RETURNING transition and context preservation
- Return action sequence dispatched in order
- Idempotent inventory return (duplicate signals don't repeat sequence)
- Deposit/drop rule enforcement (authorized items dropped, unauthorized retained with warning)
- PP defers casts while WL is RETURNING
- Resume combat after return (IDLE state)
- All events logged with correct payload shape

### 5. Validation

- Run `pytest tests/test_story_6_4_inventory_return.py -v`
- Run existing tests: `pytest tests/test_story_6_1_warlord_combat.py tests/test_story_6_2_prophet_buff_fsm.py tests/test_story_6_3_death_recovery.py -v` (no regressions)
- Run full suite: `pytest -q`
- Compile check: `python3 -m compileall lagent tests`

## Exit Check

A deterministic two-agent harness with fake perception and fake clock demonstrates:
1. WL detects full inventory and transitions to RETURNING
2. Context is preserved for resumption
3. Return action sequence is dispatched in order through HSL
4. PP observes RETURNING state and defers all casts
5. Deposit/drop rules are honored; unauthorized items retained with logged warnings
6. WL resumes IDLE after return
7. All events logged with correct payloads
8. Duplicate inventory-full signals don't repeat return sequence

## Known Blockers

None. All infrastructure present (lifecycle.py, Party Bus, HSL dispatch, rule evaluation framework).
