---
storyId: 9.7
epic: "Epic 9: Quest Mode"
title: "Quest Telemetry & Tray/Overlay Status"
status: ready-for-dev
---

# Story 9.7: Quest Telemetry & Tray/Overlay Status

## User Story

As Ion,
I want quest progress and failure state to be visible in the live status surfaces,
so that I can monitor objective progress without opening the game or guessing whether the quest is still active.

## Acceptance Criteria

### Criterion 1: Status surfaces show quest state

**Given** a quest is running
**When** the tray or overlay is refreshed
**Then** it shows the quest name, current objective, objective index, and a status such as running, paused, complete, or failed

**Given** no quest is active
**When** the status surfaces are refreshed
**Then** they show the neutral non-quest state and do not display stale quest text from a prior session

### Criterion 2: Failure reasons are visible and actionable

**Given** the quest enters a safe stop or failure state
**When** the status surfaces render the latest event
**Then** they show the failure reason, such as `npc_not_found`, `route_stuck`, or `retry_limit_reached`, in an operator-readable form without exposing internal debug noise

**Given** the quest is complete
**When** the status is updated
**Then** it shows a terminal success state and preserves the final objective index

### Criterion 3: Quest telemetry remains low-noise and deterministic

**Given** duplicate quest events or stale session data are emitted
**When** the UI renders the session state
**Then** only the latest valid quest status is shown, and stale values are ignored before they can overwrite the current session

## Dependencies

- Story 9.3 quest FSM terminal states.
- Story 9.6 quest checkpoint and failure logging.
- Epic 8 tray UI and overlay status model.

## Developer Context

Questing adds another layer of runtime state that must be projected to the tray and status overlay without turning the UI into a quest planner. The tray should show a compact summary, while the overlay can show a slightly richer current objective and status. These surfaces are read-only projections of the same session telemetry and must not own quest logic.

Use the existing telemetry model rather than a separate quest state file. Keep the rendering deterministic and safe on stale data.

## Technical Requirements

- Surface quest status in existing tray and overlay states without new workflow complexity.
- Expose safe-stop and failure reasons in a compact human-readable format.
- Ignore stale or duplicate objective events from older sessions.
- Keep quest telemetry consistent with the session DB event model and Epic 8 UI contract.

## Testing Requirements

- Test quest states render in the tray and overlay summary.
- Test stale quest events do not overwrite newer session state.
- Test failure reason formatting for safe-stop and retry exhaustion scenarios.
- Test no-quest idle view prevents stale quest text from showing.

## Architecture Compliance

- AD-5: UI remains a projection surface only and does not own runtime quest decisions.
- AD-9: quest telemetry uses the existing session log as the single source of truth.
- AD-12: no new cross-process shared state beyond the existing session DB contract.

## File Structure

Expected implementation surfaces: UI integration in the existing tray/overlay code and tests under `tests/test_story_9_7_quest_status_projection.py`.

## Completion Status

Ready for development.

## Change Log

- 2026-08-26: Story created from Epic 9 requirement and sprint proposal.
