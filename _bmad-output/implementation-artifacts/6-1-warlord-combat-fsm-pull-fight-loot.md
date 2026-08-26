# Story 6.1: Warlord Combat FSM

Status: done

## Implementation

- Added `lagent.agent.warlord.WarlordCombatFSM`.
- Uses profile-driven pull, AoE, and loot bindings.
- Detects mobs, melee-range evidence, clear mob area, and loot timeout.
- Publishes `PartyState` on transitions and logs structured decisions/transitions.
- Suppresses actions in `PAUSED`, `DEAD`, `RETURNING`, and `STOPPED`.
- Updated `AgentLoop` to normalize lowercase profile state keys and support Epic 6 states.
- Preserved pre-transition state in tick payloads for existing loop consumers.

## Validation

- `tests/test_story_6_1_warlord_combat.py`: passing.
- Deterministic cycle validated: `IDLE -> PULLING -> FIGHTING -> LOOTING -> IDLE`.
- All generated actions are returned as `Action` values for HSL dispatch.
