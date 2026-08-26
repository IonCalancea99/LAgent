---
storyId: 8.3
epic: "Epic 8: Tray UI & Status Overlay"
title: "Session State Wiring & Tray Feedback"
status: in-progress
baseline_commit: 441485922e8ead0d449f84a2904f679d955bef68
---

# Story 8.3: Session State Wiring & Tray Feedback

## User Story

As Ion,
I want the tray icon, tooltip, and menu to reflect live session state,
so that I can tell whether LAgent is idle, running, recording, or halted without opening a window (UX-6).

## Acceptance Criteria

### Criterion 1: Tooltip reflects the active session

**Given** a session is running
**When** Ion hovers over the tray icon
**Then** the tooltip shows mode, active profile, and elapsed time in a stable format such as `Combat · warlord+prophet · 01:24:37`

**Given** there is no active session
**When** the tooltip is requested
**Then** it identifies the UI as idle and does not show stale session data

### Criterion 2: Recording state is explicit and recoverable

**Given** Recording Mode is off
**When** Ion toggles it on before starting a session
**Then** the menu checkmark and tray visual indicate recording, and newly started agent processes receive `--record`

**Given** a session is running and Ion toggles Recording Mode on
**When** the mode change is applied
**Then** the UI performs an orderly agent restart with the same session ID/profile, does not run live and recording agent copies simultaneously, records `recording_mode_changed`, and restores the menu to the correct checked state only after the replacement agents are ready

**Given** the recording restart fails
**When** startup rollback completes
**Then** the UI leaves the session halted, clears the recording checkmark if recording is not active, records the failure, enables Start Session, and communicates the failure through the tray state/notification

### Criterion 3: Unexpected halt reaches the operator

**Given** the Orchestrator emits a session halt event or a required child exits unexpectedly
**When** the UI observes the halt
**Then** it marks the session Halted, updates the tray icon to an error state, shows the Windows notification `Session halted - check status overlay`, enables Start Session, and prevents Stop from appearing successful when children remain alive

**Given** telemetry is temporarily unavailable
**When** the refresh deadline expires
**Then** the UI marks state as Unknown/Stale rather than claiming Idle or Running, keeps the last known tooltip only with a stale indication, and continues retrying without crashing the tray loop

### Criterion 4: State transitions are deterministic

**Given** startup, running, recording, halted, stopped, and restart events arrive in any valid order
**When** the UI state reducer processes them
**Then** menu enabled states, icon state, tooltip, notification behavior, and active session ID are derived from one state model; duplicate events are idempotent and an old session cannot overwrite a newer one

## Dependencies

- Story 8.1 process manager and tray menu.
- Story 8.2 telemetry reader/overlay status model.
- Orchestrator heartbeat/session-halt events from Story 5.3.
- Recording Mode launch flag and agent behavior from Story 7.1.
- `pystray` notification support or a Windows notification adapter.

## Tasks/Subtasks

- [x] Implement the reducer-backed session state model and tooltip formatting.
- [x] Wire recording launch flags and orderly agent restart/rollback.
- [x] Add halt/stale telemetry handling, tray projection, and notification adapter.
- [ ] Add focused tests and run the full regression suite.

## Developer Context

The tray must be a projection of session state, not a second source of truth. Define a small UI state model/reducer with explicit states such as IDLE, STARTING, RUNNING, RECORDING, STOPPING, HALTED, and UNKNOWN. Feed it process lifecycle results and database events, then render menu/icon/tooltip/notification from that model.

Do not toggle `--record` in an existing Agent process: architecture says Recording Mode is selected at Agent launch. A running-session toggle therefore requires an orderly stop/restart boundary. Quiesce/terminate both Agents before relaunching them, preserve GPU/Orchestrator ownership unless their contracts require restart, and ensure no overlapping Agent process can produce OS input. The restart must retain the session ID and make its lifecycle visible in telemetry.

Use a monotonic clock for elapsed display and a session `started_at` timestamp for persistence/recovery. Notifications and icon assets are platform adapters with no-op/test doubles in headless environments. Avoid notification storms by deduplicating halt notifications per session/event ID.

## Technical Requirements

- All rendered states must be derivable from current session ID plus process/telemetry evidence.
- Tooltip refresh must not require opening the overlay.
- Icon states must distinguish idle, active, recording, and halted using visual and accessible text/tooltip cues.
- Windows notification text must use a hyphen in source/test-safe text: `Session halted - check status overlay`.
- UI event handling must be non-blocking; DB polling and process waits cannot freeze the tray callback thread.
- Ignore stale events from prior sessions and malformed payloads with structured diagnostics.

## Testing Requirements

- Reducer tests for every state transition, duplicate/out-of-order event, stale telemetry, and session rollover.
- Test tooltip formatting for idle, active, recording, halted, and unknown states.
- Test pre-start recording launch flags and running-session orderly restart/rollback.
- Test halt detection from both Orchestrator event and unexpected child exit, including notification deduplication.
- Test platform adapters with fakes so CI does not require Windows tray or notification services.
- Add a Windows/manual smoke check for actual icon changes, tooltip display, and system notification.

## Architecture Compliance

- AD-5: UI remains sole launcher and contains only control/status projection logic.
- AD-9: Session and event telemetry remain in shared WAL SQLite; no ad hoc state file is introduced.
- AD-12: Keep runtime process boundaries intact and avoid importing agent internals.
- AD-13: Recording Mode is a launch-time Agent flag and remains mutually exclusive with live Agent execution.

## File Structure

Expected implementation surfaces: `lagent/ui/state.py`, `lagent/ui/tray.py`, `lagent/ui/process_manager.py`, `lagent/ui/notifications.py`, and telemetry integration from Stories 8.1-8.2. Add focused tests under `tests/test_story_8_3_session_state_wiring.py`.

## Completion Status

Ready for development. Ultimate context engine analysis completed - comprehensive developer guide created.

## Change Log

- 2026-08-26: Story created from Epic 8 specification.
- 2026-08-26: Implemented reducer-backed tray state, recording restart/rollback, halt notifications, and focused tests. Runtime pytest/full regression remains blocked by missing `pytest` and `pydantic` dependencies.

## Dev Agent Record

### Implementation Plan

- Keep session state in an immutable reducer model and render menu/icon/tooltip from it.
- Treat recording as a launch-time Agent flag; restart only Agent children at a session boundary.
- Use a headless notification adapter with per-session event deduplication.

### Completion Notes

- Added deterministic `IDLE`, `STARTING`, `RUNNING`, `RECORDING`, `STOPPING`, `HALTED`, and `UNKNOWN` state handling with stale-session rejection.
- Added stable elapsed tooltips, stale preservation, tray icon state projection, and the required halt notification text.
- Added recording launch arguments and rollback-safe Agent restart behavior with telemetry event methods.
- `python3 -m py_compile ...` and `git diff --check` pass. Runtime tests could not run because `pytest` and `pydantic` are unavailable in the environment.

### File List

- `_bmad-output/planning-artifacts/stories/8-3-session-state-wiring-tray-feedback.md`
- `lagent/ui/state.py`
- `lagent/ui/notifications.py`
- `lagent/ui/process_manager.py`
- `lagent/ui/tray.py`
- `lagent/ui/telemetry.py`
- `lagent/ui/__main__.py`
- `tests/test_story_8_3_session_state_wiring.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-08-26: Implementation is complete; runtime test gate remains pending environment dependencies.
