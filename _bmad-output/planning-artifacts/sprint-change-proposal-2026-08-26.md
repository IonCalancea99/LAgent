---
title: "Sprint Change Proposal — Quest Completion Capability"
project: LAgent
status: approved
created: 2026-08-26
mode: batch
---

# Sprint Change Proposal: Quest Completion Capability

## 1. Issue Summary

### Trigger

Ion identified a new product requirement: LAgent must be able to pass/complete quests in Lineage 2 on the Asterios x55 server.

### Discovery context

The request was raised after the current implementation plan had already defined fishing automation, WL+PP combat farming, death recovery, inventory return, session shutdown, training, and tray control. No existing story, requirement, or implementation defines quest acceptance, objective tracking, NPC interaction, dialogue handling, quest navigation, or quest completion. The first V1 target is the simple conversational **Supply Check** quest, starting with NPC Marcela in Kamael village, run by a level-3 Orc Fighter.

### Evidence

- The PRD defines Fishing Mode and Combat Mode as the available behavior profiles and explicitly scopes the V1 behavior around farming.
- The PRD's `GameState` vocabulary contains HP/MP, buffs, mobs, loot, position, and UI mode, but no quest or dialogue state.
- The architecture spine maps all current functional requirements and contains no quest subsystem or quest message contract.
- The current Warlord profile contains combat FSM bindings, combat skill keys, recovery actions, and inventory rules, but no navigation, NPC, dialogue, or quest configuration.
- Repository search found no quest-specific story, implementation module, test, model field, or profile field.

### Problem statement

LAgent cannot currently complete a quest because its perception contract, state model, behavior policy, profile schema, runtime FSMs, and operator controls have no representation for quest objectives or the interactions needed to advance them.

### Trigger classification

- Checklist 1.1: **[!] Action-needed** — no single triggering story was supplied; this is a new stakeholder requirement raised during sprint execution.
- Checklist 1.2: **[x] Done** — new requirement emerged from the stakeholder/operator.
- Checklist 1.3: **[x] Done** — evidence is the explicit request plus the documented absence of quest capability in current artifacts and code.

## 2. Impact Analysis

### Epic impact

**Epic 4 — Fishing Mode:** No direct behavior change. Quest capability should not be embedded in Fishing Mode.

**Epic 6 — Combat Mode & Session Lifecycle:** Indirect impact. Combat may be used as one quest objective, and existing death recovery, inventory return, session cap, and HSL action dispatch should be reusable. The combat FSM should expose a controlled handoff or shared objective completion signal rather than owning quest logic.

**Epic 8 — Tray UI & Status Overlay:** Moderate impact. The operator needs a way to select a quest profile or quest mode and see high-level quest progress/status. Existing tray and overlay controls are operationally relevant but should not become a quest planner.

**New Epic 9 — Quest Mode:** Required for V1. Questing is a distinct behavior profile with its own objective discovery, NPC interaction, conversational dialogue, persistence, and validation stories. Phase 1 should implement the Marcela/Supply Check conversational path for a level-3 Orc Fighter, while keeping the quest resource lookup dynamic rather than hardcoding the entire quest definition.

### Story impact

Existing completed stories should remain intact. The following planned or implemented surfaces need extension points:

- Shared types and profile validation: add quest-compatible fields without breaking existing Fishing/Combat profiles.
- Perception pipeline: represent quest-relevant detections and OCR values such as NPC identity, interaction prompts, dialogue options, quest log/objective text, and completion indicators. Exact detection classes and OCR strategy require confirmation against the target quests.
- Agent base loop and FSM: support a QUESTING or Quest FSM mode with explicit objective transitions and bounded waits.
- Agent behavior: add an Orc Fighter quest profile for the selected fixture. Warlord/Prophet party coordination is not part of the Phase 1 quest slice unless later required by the quest resource.
- Session telemetry: log objective transitions, navigation failures, interaction attempts, dialogue choices, quest completion, abandonment, and operator halt events.
- Tray/profile selection: expose quest mode only after a quest profile and safety behavior are defined.

### Artifact conflicts and updates

**PRD:** Add questing to the vision/user journeys, glossary, functional requirements, MVP scope decision, and success metrics. Clarify whether this is V1 scope or a later phase. The current statement that Combat Mode is the V1 primary behavior profile must be revised only if questing is intended for V1.

**Epics:** Add Epic 9 and stories for the smallest confirmed quest slice. Update the FR coverage map and dependencies. Avoid writing a generic “all quests” promise without a bounded quest family, route, and interaction vocabulary.

**Architecture:** Extend the capability map and shared contracts. Preserve AD-1, AD-2, AD-4, AD-6, AD-8, AD-9, AD-10b, AD-11, and AD-12. In particular, quest decisions remain inside the Agent process, all perception remains in the GPU server, and all cross-process state remains ZeroMQ `PartyState` or explicitly versioned shared types.

**UX:** No UX specification artifact exists. The tray/overlay story should be updated only for operational status such as selected quest profile, current objective, progress, and failure state. Detailed quest authoring or route editing should be deferred unless the operator explicitly needs it.

**Other artifacts:** Add quest fixtures and deterministic FSM tests; update user documentation and profile examples. No deployment or CI/CD change is implied by the requirement alone.

### Technical impact

The likely implementation surface is:

- `lagent/common/types.py`: quest/objective state contract and perception fields, subject to final schema design.
- `profiles/*.yaml`: quest profile section covering objective sequence, navigation waypoints or route actions, NPC interaction rules, dialogue choices, timeouts, retry limits, and abort conditions.
- `lagent/agent/`: quest FSM/policy module and integration with existing lifecycle/HSL dispatch.
- `lagent/gpu_server/`: quest-specific YOLO classes and OCR extraction, loaded through the existing inference server.
- `lagent/common/sessions_db.py` or event producers: quest event payload conventions; avoid schema changes unless querying quest progress requires them.
- `lagent/ui/`: profile selection and status projection, likely after core quest execution is deterministic.
- `tests/`: deterministic quest state-machine harness, interaction timeout tests, route failure tests, recovery tests, and end-to-end shadow-mode coverage.
- `models/`: quest model labels and versioned class-model artifacts; no in-session model reload.

## 3. Recommended Approach

### Option 1 — Direct adjustment

**Status:** Viable for a bounded quest slice.

**Effort:** Medium to High.

**Risk:** Medium to High, depending on navigation and dialogue variability.

Add a new Quest Mode epic and implement the explicitly named Marcela/Supply Check conversational quest first. Use a Lineage resource as the source for quest identity, NPC, dialogue, and objective metadata, while constraining execution to the level-3 Orc Fighter path. Reuse the existing capture, inference, HSL, session, telemetry, death recovery, and inventory behavior. Introduce quest-specific contracts only where this fixture proves they are needed.

### Option 2 — Potential rollback

**Status:** Not viable.

**Effort:** High.

**Risk:** High.

Rolling back completed combat, lifecycle, training, or UI work would not solve the missing quest requirements and would discard reusable infrastructure.

### Option 3 — MVP review

**Status:** Resolved as a V1 scope addition.

**Effort:** Low for the decision; implementation remains Medium to High.

**Risk:** Medium.

The original request was broad, but the V1 boundary is now explicit: support Supply Check from Marcela in Kamael village for a level-3 Orc Fighter. “All quests” remains out of scope for this change. Dynamic discovery from the Lineage resource is part of the capability, but Phase 1 execution is limited to a simple conversational quest.

### Recommended path

**Selected approach: Hybrid — Option 1 plus Option 3.**

1. Keep completed infrastructure and current combat/fishing work.
2. Add a new Epic 9 for Quest Mode and mark it required for V1.
3. Implement the Marcela/Supply Check conversational path for a level-3 Orc Fighter as the Phase 1 acceptance fixture.
4. Resolve quest metadata and available conversational steps dynamically from the selected Lineage resource; do not hardcode a universal quest catalog.
5. Implement perception and FSM behavior behind the existing architecture rules, with shadow-mode and deterministic harness validation before live play.

This preserves momentum and avoids a premature “generic quest engine.” The first quest will reveal the actual requirements for navigation, dialogue, objective tracking, and persistence; those contracts should be generalized only after the fixture proves them.

### Timeline and risk

- **Timeline:** Add a new medium/high-complexity epic; existing sprint stories should not be silently expanded to absorb it. Dynamic resource lookup raises the implementation complexity above a purely scripted quest, but the fixed Supply Check acceptance path keeps Phase 1 bounded.
- **Primary risks:** visual ambiguity in quest text/dialogue, unreliable navigation, quest state persistence after death or restart, interaction timing, and server-specific UI differences.
- **Safety risk:** a failed or ambiguous objective must halt or enter a bounded recovery state; it must never continue issuing unverified movement or dialogue actions indefinitely.
- **Scope risk:** “all quests” would be a major replan. Dynamic discovery plus one supported conversational path is a moderate change with a high integration risk until the Lineage resource format is validated.

## 4. Detailed Change Proposals

### A. PRD proposal

**Section:** Glossary, Features, MVP Scope, Success Metrics, and Open Questions.

**OLD:**

- Available behavior profiles are Fishing Mode and Combat Mode.
- V1 scope lists Fishing Mode and Combat Mode but no quest behavior.
- No quest state, objective, NPC, dialogue, navigation, or completion requirement exists.

**NEW:**

Add a V1 Quest Mode requirement:

> **Quest Mode:** A resource-driven behavior mode required for V1. Phase 1 shall execute the simple conversational Supply Check quest beginning with NPC Marcela in Kamael village for a level-3 Orc Fighter. The system shall discover the quest and its available conversational steps from the selected Lineage resource, identify NPC/interaction/dialogue states, verify objective completion, and stop safely when state is ambiguous or retries are exhausted.

Add an FR-26 family only after the first quest is named:

- **FR-26 Quest resource discovery:** the Agent shall resolve the selected quest, starting NPC, objective sequence, and available conversational choices from the configured Lineage resource before issuing quest actions.
- **FR-27 Quest objective execution:** the Agent shall execute the discovered ordered objective sequence and verify each objective transition from perception before advancing.
- **FR-28 Quest interaction:** the Agent shall identify the discovered NPC/interaction/dialogue states and issue only resource- or profile-authorized actions, with timeout and retry limits.
- **FR-29 Quest navigation:** the Agent shall follow the route required by the discovered Supply Check path and detect navigation failure before continuing.
- **FR-30 Quest completion and failure:** the Agent shall verify quest completion, log the result, and enter a safe terminal state on ambiguity, timeout, or exhausted retries.
- **FR-31 Quest recovery:** after death, disconnect, or restart, the Agent shall resume only from a verified quest checkpoint or require operator intervention.

Add success metrics for the selected quest fixture, such as completion rate, zero unverified interaction loops, bounded recovery time, and successful shadow-mode validation. Do not invent numeric targets until the first quest and route are selected.

**Rationale:** The PRD needs to state the user value and acceptance boundary without committing to a generic quest engine or unvalidated server behavior.

**MVP impact:** Questing is required for V1, limited to the Marcela/Supply Check conversational fixture for a level-3 Orc Fighter. Broad arbitrary quest support remains out of scope.

### B. Epic proposal

**Artifact:** `epics.md`

**OLD:**

- Epic list ends at Epic 8, with no quest epic or FR coverage.

**NEW:**

Add:

> **Epic 9: Quest Mode** — Ion can run the Marcela/Supply Check conversational quest in Kamael village with a level-3 Orc Fighter, first in shadow mode and then live mode. The Agent discovers quest metadata from the configured Lineage resource, tracks verified objectives, navigates through the required route, interacts with NPC/dialogue states, logs progress, and halts safely on ambiguity.
>
> **Dependencies:** Epics 1–3, Story 4.1 agent loop, Story 4.2 character identification, Epic 6 lifecycle recovery, and Epic 8 operational status. Party coordination is conditional on the selected quest.

Initial stories should be created only after the target quest is named:

- 9.1 Lineage resource adapter and quest state/profile contract
- 9.2 Supply Check perception fixtures: Marcela, objective, dialogue, and completion signals
- 9.3 Deterministic quest FSM and objective verification
- 9.4 Profile/resource-driven Kamael village navigation and stuck detection
- 9.5 Marcela interaction and dialogue selection with bounded retries
- 9.6 Quest checkpoint, failure, and lifecycle recovery
- 9.7 Quest telemetry and tray/overlay status
- 9.8 Shadow-mode and live Supply Check acceptance fixture

**Rationale:** This gives questing a coherent ownership boundary and prevents combat stories from becoming a catch-all.

### C. Architecture proposal

**Artifact:** `ARCHITECTURE-SPINE.md`

**OLD:**

- Capability map has no quest capability.
- `GameState` and `PerceptionResult` have no quest-specific contract.
- Profile structure is oriented to FSM bindings, skills, recovery, and inventory.

**NEW:**

- Add V1 Quest Mode to the capability-to-architecture map, owned by `lagent.agent.quest` or an equivalent agent-local module.
- Add a Lineage resource adapter with a validated boundary: external resource data is parsed into the internal quest contract before the Agent FSM consumes it.
- Add a shared, versioned quest state subset only if it must cross processes; keep detailed objective state agent-owned under AD-4.
- Extend `AgentProfile` with validated quest configuration rather than free-form unvalidated payloads.
- Keep YOLO/OCR quest perception in `lagent.gpu_server.inference` under AD-2 and AD-10.
- Add explicit invariants: resource parsing must fail closed; objective advancement requires positive verification; route/interaction retries are bounded; ambiguous quest state enters PAUSED/SAFE_STOP; quest progress is logged to SQLite; no filesystem polling is introduced.
- Phase 1 questing is single-agent Orc Fighter behavior. Do not add PartyState fields unless a later quest requires party coordination.

**Rationale:** Questing introduces a new behavior domain while preserving the actor/pipes-and-filters architecture and existing safety boundaries.

### D. UX proposal

**Artifact:** No UX specification currently exists; update the Epic 8 story and any future UX artifact.

**OLD:**

- Tray profile submenu offers Fishing, Combat, and Shadow.
- Overlay shows FSM state, HP/MP, and session timer.

**NEW:**

- Add the `Supply Check` Quest profile for the level-3 Orc Fighter after the resource adapter contract is approved.
- Overlay may show `Quest: <name>`, current objective, objective index, and status (`running`, `paused`, `complete`, `failed`) without exposing a quest editor.
- Surface safe-stop reasons such as `objective not verified`, `NPC not found`, `navigation timeout`, or `retry limit reached`.

**Rationale:** The operator needs visibility into a long-running quest, but route authoring and quest management UI would expand scope unnecessarily.

### E. Test and documentation proposal

**OLD:**

- No quest fixtures, quest-specific tests, or quest user documentation.

**NEW:**

- Add deterministic replay fixtures for each objective transition.
- Test ambiguous OCR/detection, missing NPC, dialogue timeout, navigation stuck detection, retry exhaustion, death recovery, inventory-full handling, session cap, and safe stop.
- Add shadow-mode acceptance before live acceptance.
- Document the supported quest, required profile/model assets, route assumptions, known failure modes, and operator recovery procedure.

**Rationale:** Quest automation is stateful and server-specific; deterministic fixtures are necessary to avoid validating only by live trial-and-error.

## 5. Implementation Handoff

### Scope classification

**Moderate**: limited to the named Supply Check quest and tracked in the new Epic 9 backlog.

**Major**, if the requirement means broad support for arbitrary quests, automatic quest discovery, generic route planning, or questing must replace the current V1 gate.

### Handoff

- **Product Manager / Analyst:** use `lineage.ru` web scraping as the resource source and define measurable completion criteria for Marcela/Supply Check. **Completed for scope approval; scraper-format validation remains Story 9.1.**
- **Architect:** approve the quest contract, ownership boundary, persistence/checkpoint strategy, and any PartyState changes.
- **Product Owner / Developer:** add Epic 9 and the bounded stories to the backlog; update sprint status only after proposal approval.
- **Developer agent:** implement the approved story slice with deterministic fixtures, shadow-mode validation, and existing HSL/lifecycle safeguards.
- **UX designer (optional):** update tray/overlay status only if quest mode is approved for operator-facing use.

### Success criteria

- One named quest or quest chain is explicitly supported and documented.
- Every objective transition is verified from perception before the next objective begins.
- Navigation and interaction retries are bounded and produce a logged safe stop when exhausted.
- Death, inventory-full, session cap, and disconnect behavior do not bypass quest safety rules.
- Shadow-mode replay passes deterministic fixtures before live testing.
- Live acceptance completes the selected quest without human input, or stops safely with an actionable event.
- Existing Fishing and Combat profiles continue to validate and run unchanged.

## Checklist Status

### Section 1 — Understand the Trigger and Context

- [!] 1.1 Triggering story: no story supplied; new stakeholder requirement.
- [x] 1.2 Core problem precisely defined.
- [x] 1.3 Evidence documented from user request and repository/artifact absence.

### Section 2 — Epic Impact Assessment

- [x] 2.1 Current epics assessed.
- [x] 2.2 New Epic 9 identified as the appropriate scope boundary.
- [x] 2.3 Remaining Epic 6 and Epic 8 dependencies assessed.
- [x] 2.4 No planned epic is obsolete.
- [x] 2.5 V1 priority is confirmed; sequence Epic 9 after its runtime dependencies and before V1 acceptance.

### Section 3 — Artifact Conflict and Impact Analysis

- [!] 3.1 PRD requires additions; V1 scope is resolved but exact success thresholds remain to be set.
- [!] 3.2 Architecture requires quest contracts and invariants.
- [!] 3.3 UX artifact is absent; Epic 8 needs a limited operational-status extension if approved.
- [!] 3.4 Tests, fixtures, models, profiles, and documentation require additions.

### Section 4 — Path Forward Evaluation

- [x] 4.1 Direct adjustment viable for one bounded quest.
- [N/A] 4.2 Rollback not justified.
- [x] 4.3 MVP review completed; questing is required for V1 with a bounded Phase 1 fixture.
- [x] 4.4 Hybrid recommendation selected.

### Section 5 — Proposal Components

- [x] 5.1 Issue summary.
- [x] 5.2 Epic and artifact impact.
- [x] 5.3 Recommended path and alternatives.
- [x] 5.4 MVP impact is defined: V1 includes Supply Check only, not arbitrary quests.
- [x] 5.5 Handoff plan.

### Section 6 — Final Review and Handoff

- [x] 6.1 Applicable analysis completed; unresolved decisions are marked.
- [x] 6.2 Proposal checked for consistency and bounded scope.
- [x] 6.3 Ion approved the proposal on 2026-08-26.
- [x] 6.4 `sprint-status.yaml` updated with Epic 9 and Stories 9.1–9.8 in backlog.
- [x] 6.5 Handoff routed to Product Owner/Developer; resource format and visual signal confirmation are implementation prerequisites.

## Remaining Validation Questions

1. Define the `lineage.ru` scraper's supported page format, caching policy, and behavior when the site is unavailable.
2. Select the most reliable available perception combination for Marcela, dialogue choices, objective progress, and quest completion, preferring stable UI/OCR signals with visual confirmation where needed.
3. Supply Check is strictly conversational for the level-3 Orc Fighter; no combat behavior is required in Phase 1.

## Review State

This proposal was reviewed in **batch mode** and approved by Ion on **2026-08-26**. Handoff: Product Owner/Developer for Epic 9 backlog execution, with Architect review of the resource adapter and quest contract before implementation.

## Workflow Completion

- **Issue addressed:** Add V1 quest completion capability.
- **Change scope:** Moderate; bounded to Supply Check in Phase 1.
- **Artifacts modified:** PRD, epics, architecture spine, sprint status, and this proposal.
- **Routed to:** Product Owner, Architect, and Developer agent.
- **Deliverables:** Approved Sprint Change Proposal, artifact change proposals, Epic 9 backlog plan, and implementation handoff.
