# Sprint 6 Development Plan: Combat Mode & Session Lifecycle

**Project:** LAgent  
**Date:** 2026-08-26  
**Scope:** Epic 6, Stories 6.1-6.5  
**Implementation mode:** One continuous delivery sequence with a validated checkpoint after each story

## Outcome

Deliver a runnable WL+PP combat session that can:

- execute the Warlord pull, fight, and loot cycle;
- maintain Prophet buffs through timer expiry and the PP Safety Check;
- recover from a party death and resume the pre-death states;
- suspend combat for inventory-full return and configured loot handling; and
- stop at the session cap through a safe, logged shutdown.

The plan assumes the upstream runtime contracts are available: Epic 2 perception results, Epic 3 HSL dispatch, Epic 4 `AgentLoop`/FSM tick orchestration, and Epic 5 Party Bus plus heartbeat halt behavior. Existing incomplete upstream work remains a prerequisite and must be closed before live-session validation.

## Readiness And Guardrails

1. Finish or explicitly test the unfinished upstream paths before starting the Epic 6 implementation pass:
   - Epic 2 stories 2.1-2.5 are currently in `review`.
   - Story 3.4 is currently `in-progress`.
   - Story 4.3 is currently `in-progress`; its timeout-action ambiguity and profile-parameter gap are recorded in `deferred-work.md`.
   - Story 5.2 is currently `in-progress`.
2. Use deterministic `PerceptionResult` fixtures and fake clocks for all FSM and timer tests. Do not make unit tests depend on a live Windows client, YOLO weights, or wall-clock sleeps.
3. Keep all OS input behind the existing HSL contract. Combat and lifecycle code may produce `Action` values, but must never call platform input APIs directly.
4. Treat `AgentLoop` as the tick boundary. Every transition, lifecycle event, and recovery decision must be observable in the existing SQLite events table.
5. Preserve fail-safe behavior: halt, disconnect, death, inventory return, and cap shutdown must prevent unsafe or stale combat actions.
6. Keep the existing shared-type boundary: cross-process data uses `lagent.common.PartyState`; local FSM details stay in the owning Agent process.

## Delivery Sequence

### Phase 0: Shared lifecycle contract and test harness

**Purpose:** Establish the small interfaces that all five stories need before adding behavior.

**Tasks:**

- Define canonical state names and transition ownership for combat and lifecycle states: `IDLE`, `PULLING`, `FIGHTING`, `LOOTING`, `BUFFING`, `DEAD`, `RETURNING`, `PAUSED`, and `STOPPED`.
- Add a reusable transition/event helper or equivalent local pattern that records `state_transition` with `from`, `to`, reason, and tick/session identifiers.
- Define a lifecycle signal representation for `death_detected`, `inventory_full`, `session_cap_reached`, and `session_halt`.
- Define an explicit safe-action policy for `PAUSED`, `DEAD`, `RETURNING`, and shutdown states. The policy must be testable without sending OS input.
- Add deterministic fixtures for WL/PP `PerceptionResult`, `PartyState`, profile bindings, and a fake clock.
- Resolve the existing timeout action ambiguity from Story 4.3 before reusing that path in combat. Prefer an explicit transition signal or `next_state` result over interpreting `wait(0.0)` in multiple callers.

**Exit check:** A unit test can drive a synthetic tick from a normal state into a lifecycle interruption and prove that no combat action is dispatched after the interruption.

### Phase 1: Story 6.1 - Warlord Combat FSM

**Dependency:** Phase 0, perception fixtures, HSL dispatch, Story 4.1 loop.

**Implementation tasks:**

- Add a Warlord FSM/policy module under `lagent/agent/warlord/` using the existing state-handler shape.
- Map mob detection in the configured `mob_area` to `IDLE -> PULLING`.
- Map melee-range or configured pull-complete evidence to `PULLING -> FIGHTING`.
- Run the configured AoE/attack sequence while `FIGHTING`; transition to `LOOTING` when the mob area is clear.
- Execute loot key/movement actions through HSL and return to `IDLE` after loot detection clears or the configured timeout expires.
- Make policy bindings profile-driven; avoid hardcoding class-specific keys in the FSM.
- Publish the WL `PartyState` on each relevant transition so PP can make decisions within one loop tick.
- Log every transition and combat decision to SQLite.

**Focused tests:**

- idle with no mobs produces no pull action;
- mob detection starts pulling;
- melee-range detection starts fighting;
- clear mob area starts looting;
- loot timeout returns to idle;
- all generated actions reach HSL;
- transition events include the correct reason and state;
- PAUSED/DEAD/RETURNING suppress combat actions.

**Exit check:** A deterministic fixture completes `IDLE -> PULLING -> FIGHTING -> LOOTING -> IDLE` and the event sequence matches the expected order.

### Phase 2: Story 6.2 - Prophet Buff Cycle FSM

**Dependency:** Phase 0, Story 5.2 Safety Check, Party Bus peer state.

**Implementation tasks:**

- Add a PP buff timer service/state handler with independent timers for each configured buff.
- Load timer durations and skill bindings from `prophet.yaml`; use a fake clock in tests.
- Enter `BUFFING` only when a timer expires, then evaluate Safety Check before every cast.
- On Safety Check failure, preserve the pending buff and retry after `retry_interval`; never drop the cast.
- Ensure `PartyState.fsm_state == PULLING` blocks timed casts and that mob distance uses frame-pixel coordinates.
- Prevent offensive sequences while PP is not in an allowed configured state.
- Log each cast and each safety decision with buff name, timestamp, peer state, radius result, and pass/fail outcome.
- Publish PP state before and after a buff cycle.

**Focused tests:**

- timer expiry enters buffing;
- safe conditions cast the pending buff and reset its timer;
- WL pulling defers the cast;
- nearby mob defers the cast;
- deferred casts retry and eventually execute;
- multiple buffs are not abandoned mid-cycle;
- PP produces no offensive action outside BUFFING;
- malformed or missing timer configuration fails profile validation.

**Exit check:** A fake-clock test proves a deferred buff remains pending across multiple failed checks and is cast exactly once after the first passing check.

### Phase 3: Story 6.3 - Death Detection and Full Party Recovery

**Dependency:** Phases 1-2, Party Bus state relay, orchestrator halt semantics.

**Implementation tasks:**

- Add death detection from the configured YOLO/UI detection or explicit normalized perception signal.
- Transition the affected agent to `DEAD` and cancel/suppress the current combat action.
- Implement respawn and navigation as profile-configured HSL action sequences.
- Publish `DEAD`, respawn progress, and arrival at the buff restoration position over Party Bus.
- Coordinate PP's full rebuff only after WL is recoverable and Safety Check permits casting.
- Snapshot the pre-death state and resume it only after recovery is complete; default to `IDLE` if the snapshot is invalid.
- Log death detection, respawn, buff restoration, recovery completion, and elapsed recovery time.
- Make recovery idempotent so duplicate death frames or duplicate Party Bus messages do not repeat respawn or rebuff actions.

**Focused tests:**

- death detection interrupts fighting and enters `DEAD`;
- respawn sequence is dispatched through HSL;
- WL arrival enables PP rebuff;
- PP waits when Safety Check fails;
- both agents resume their saved states after a complete cycle;
- duplicate signals do not duplicate recovery actions;
- recovery exceeding 60 seconds is logged as a failed/over-budget recovery event;
- no combat input is emitted while either party member is unrecovered.

**Exit check:** A deterministic two-agent harness completes death detection through resumed operation and asserts recovery elapsed time, event ordering, and zero unsafe actions.

### Phase 4: Story 6.4 - Inventory-Full Detection and Town Return

**Dependency:** Phase 1 combat FSM, profile loot rules, lifecycle contract.

**Implementation tasks:**

- Normalize inventory-full detection from YOLO/OCR into a lifecycle signal.
- Transition WL to `RETURNING`, suspend combat policy, and retain the current session context.
- Execute profile-configured town navigation through HSL.
- Evaluate explicit deposit/drop rules; reject or log any item without an authorizing rule rather than silently discarding it.
- Reconcile PP behavior while WL is returning so PP does not cast unsafe timed buffs or offensive actions.
- Detect completion, return both agents to `IDLE`, and publish the resumed party state.
- Log inventory detection, return start/completion, each loot disposition, and any blocked disposition.

**Focused tests:**

- inventory-full interrupts each combat state;
- return actions are HSL-routed;
- configured deposit and drop rules are honored;
- unconfigured loot is retained and produces a warning/event;
- repeated inventory-full frames do not restart the return sequence;
- combat resumes only after town handling completes;
- PP remains safe during WL return.

**Exit check:** A fixture with configured and unconfigured loot proves that no unauthorized discard occurs and the session resumes from `IDLE` after one return cycle.

### Phase 5: Story 6.5 - Session Cap and Clean Shutdown

**Dependency:** Phases 1-4, session DB, safe halt semantics, Party Bus control messages.

**Implementation tasks:**

- Add a monotonic session-cap controller initialized at session start from profile/configuration.
- Check the cap at every loop boundary, including before dispatching a newly selected combat action.
- On expiry, atomically enter shutdown mode and prevent new combat actions.
- Complete WL safe-position navigation through HSL, allowing only shutdown-approved actions.
- Trigger PP's final buff cycle after WL is safe, subject to the same Safety Check and a bounded shutdown timeout.
- Set both agents to idle/standing, stop capture/inference workers, stop heartbeat publication as appropriate, and close the session with `ended_at`.
- Log `session_cap_shutdown` with final states, timing, and any bounded fallback path.
- Make shutdown idempotent and compatible with an already-paused or already-dead agent.

**Focused tests:**

- cap fires at the configured duration using a fake monotonic clock;
- cap interrupts each combat state;
- no combat action is dispatched after cap detection;
- WL reaches the safe-position phase;
- PP final buff is attempted only after WL is safe;
- both agents become idle and emit no further input;
- `ended_at` and `session_cap_shutdown` are written exactly once;
- shutdown remains safe when a worker or Party Bus peer is unavailable.

**Exit check:** A two-agent fake-clock integration test proves cap expiry produces the expected shutdown event and zero actions after the final idle state.

## Integration And Validation Order

Run the following after each phase, keeping the check narrow first:

1. Focused story tests for the phase.
2. Existing upstream regression tests for `AgentLoop`, Party Bus, HSL, profile validation, and session DB.
3. Full test suite: `python3 -m pytest -q`.
4. Static/runtime import check for all new modules: `python3 -m compileall lagent tests`.
5. Integration harness with two fake agents, fake perception, fake clock, fake HSL, Party Bus transport, and a temporary SQLite database.
6. Shadow Mode smoke run proving all WL/PP actions are shaped and logged without OS input.
7. Windows-only manual gate with the real game client after deterministic tests pass.

## End-to-End Acceptance Gate

Epic 6 is complete only when all of the following are true:

- Stories 6.1-6.5 have focused tests passing and are moved through `review` to `done`.
- A synthetic session covers combat, timed buffing, death recovery, inventory return, and cap shutdown in one event log.
- No generated action bypasses HSL.
- Every lifecycle transition and terminal event is present in `data/sessions.db` with the session ID.
- Party Bus disconnect or heartbeat halt still suppresses further input.
- Death recovery meets the 60-second target in the controlled harness.
- The session cap is enforced in a mid-combat test.
- A Shadow Mode run confirms the complete lifecycle can be observed without OS output.
- Live WL+PP validation is performed only after the deterministic and Shadow Mode gates pass; the 4-hour autonomy target is an operational validation gate, not a unit-test requirement.

## Status Tracking

Leave the current Epic 6 statuses as `backlog` until the first standalone story artifact is created and implementation begins. Then update statuses in order:

1. `epic-6: in-progress`
2. `6-1-warlord-combat-fsm-pull-fight-loot: ready-for-dev` through `done`
3. Repeat for 6.2, 6.3, 6.4, and 6.5.
4. Mark `epic-6: done` only after the end-to-end acceptance gate passes.
5. Complete `epic-6-retrospective` after delivery; record any deferred lifecycle issues in `deferred-work.md`.

## Known Risks And Decisions

- **Upstream readiness:** Epic 6 cannot be validated against real perception until the reviewed Epic 2 path is accepted.
- **Timeout semantics:** Story 4.3 currently records a timeout-action ambiguity. Resolve that contract before sharing the loop with combat FSMs.
- **Profile shape:** Existing YAML uses lowercase state keys while some FSM code reads uppercase keys. Normalize profile state lookup at the boundary and add a regression test.
- **BC Policy artifacts:** Epic 6 depends on within-state policy bindings, but the later training story does not yet define BC serialization. Start with profile-backed deterministic policy adapters and document the artifact interface for later training integration.
- **Live safety:** Real-client tests are last, bounded, and run only in Shadow Mode first. No 4-hour run should be used to diagnose deterministic FSM defects.
