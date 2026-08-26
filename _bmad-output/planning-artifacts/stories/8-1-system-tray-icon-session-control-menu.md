---
storyId: 8.1
epic: "Epic 8: Tray UI & Status Overlay"
title: "System Tray Icon & Session Control Menu"
status: ready-for-dev
---

# Story 8.1: System Tray Icon & Session Control Menu

## User Story

As Ion,
I want a Windows system-tray icon with profile-aware start and stop controls,
so that I can launch and end a live, fishing, combat, or shadow session without opening a terminal (UX-1, UX-2, AD-5).

## Acceptance Criteria

### Criterion 1: Tray process starts and exposes the menu

**Given** `python -m lagent.ui` is started on Windows
**When** the process initializes
**Then** it creates a `pystray.Icon` with a bundled/local icon asset, remains alive on the tray event loop, and does not import `lagent.agent`, `lagent.hsl`, or `lagent.gpu_server`

**Given** the tray icon is available
**When** Ion opens its context menu
**Then** the menu contains `Start Session` with Fishing, Combat, and Shadow entries, `Stop Session`, a Recording Mode toggle, a Status Overlay toggle, and Exit

### Criterion 2: Start launches the complete runtime

**Given** no session is running and a valid mode is selected
**When** Ion activates Start Session -> Combat (or Fishing/Shadow)
**Then** the UI creates one session ID and session row, launches exactly one GPU server, WL agent, PP agent, and Orchestrator child process, and passes the selected mode/profile and session ID to each applicable process

**Given** a child cannot start or exits during startup
**When** the startup timeout expires
**Then** the UI terminates already-started children, records a `startup_failed` event with the failing process and error, leaves Start enabled, keeps Stop disabled, and does not report a running session

### Criterion 3: Menu state prevents conflicting commands

**Given** a session is starting or running
**When** Ion opens the menu
**Then** Start Session is disabled, Stop Session is enabled only after the process group is registered, and Exit requests session shutdown before closing the tray loop

**Given** no session is running
**When** Ion opens the menu
**Then** Stop Session is disabled and Start Session is enabled

### Criterion 4: Stop performs clean process-group shutdown

**Given** a session is running
**When** Ion selects Stop Session
**Then** the UI sends SIGTERM/Windows-equivalent termination to all child processes, waits up to a configured grace period, force-terminates only remaining children after the grace period, and prevents new input-producing processes from being spawned

**Given** shutdown completes
**When** the session row is read from `data/sessions.db`
**Then** `ended_at` is populated and a `session_stopped` event contains the session ID, mode, clean/forced outcome, and child exit results

## Dependencies

- Story 1.3 SessionsDB and WAL-mode `data/sessions.db`.
- Story 1.4 process startup/handshake and existing module entry points.
- Story 6.5 clean session shutdown semantics.
- `pystray` 0.19.x and a Windows-compatible icon asset.

## Developer Context

The current `lagent/ui/__main__.py` is a stub. Build the UI launcher in `lagent/ui/` and keep it as the exclusive runtime process launcher. The UI may use a small process-manager/telemetry-reader abstraction, but runtime process modules must communicate only through their existing CLI/ZeroMQ/database contracts. Do not duplicate Agent or Orchestrator logic in the UI.

Use one `subprocess.Popen` handle per child, close inherited handles, capture enough stderr/stdout for startup diagnostics without blocking the tray thread, and use a dedicated shutdown path that is idempotent. The selected mode and profile must be represented in the session record; do not infer mode from child names.

The current `sessions` table has `session_id`, `started_at`, `profile`, `mode`, and `created_at`, but no `ended_at`. Extend the shared DB bootstrap and update helpers in a backward-compatible way for existing databases before the UI depends on that column. All DB writes use a UI-owned connection and existing JSON event conventions.

## Technical Requirements

- Entry point: `python -m lagent.ui`.
- Profile/mode mapping must be explicit: Fishing -> fishing profile, Combat -> warlord+prophet profile, Shadow -> shadow startup mode.
- Session ID is generated once by the UI and passed to every child.
- No GUI toolkit is loaded into Agent, GPU, or Orchestrator processes.
- Startup and shutdown timeouts are configurable constants or UI configuration, with deterministic tests using an injected clock/process factory where practical.
- Platform-specific termination must be isolated so unit tests run on non-Windows hosts.

## Testing Requirements

- Test menu labels and initial enabled/disabled states without requiring a desktop tray.
- Test each mode creates the expected four command lines and one session row.
- Test partial startup rollback and startup failure telemetry.
- Test clean stop, forced stop after timeout, repeated stop, and Exit while running.
- Test `ended_at` persistence and event payloads against a temporary SQLite database.
- Add a Windows/manual smoke check for tray creation and actual child termination; headless CI must skip it clearly rather than failing on missing display/tray support.

## Architecture Compliance

- AD-5: Tray/UI is the sole launcher and never imports runtime internals.
- AD-9: Use the shared WAL SQLite database; one connection for the UI process.
- AD-12: UI imports only `lagent.common` contracts and UI-local/session-reader code.
- Runtime process communication remains ZeroMQ; the UI does not introduce filesystem polling or shared memory between agents.

## File Structure

Expected implementation surfaces: `lagent/ui/__main__.py`, `lagent/ui/tray.py`, `lagent/ui/process_manager.py`, `lagent/ui/telemetry.py`, and the shared `lagent/common/sessions_db.py` migration/update surface. Add focused tests under `tests/test_story_8_1_system_tray.py`.

## Completion Status

Ready for development. Ultimate context engine analysis completed - comprehensive developer guide created.

## Change Log

- 2026-08-26: Story created from Epic 8 specification.
