---
storyId: 8.2
epic: "Epic 8: Tray UI & Status Overlay"
title: "Status Overlay Window"
status: done
---

# Story 8.2: Status Overlay Window

## User Story

As Ion,
I want a borderless, semi-transparent, always-on-top status overlay,
so that I can monitor both agents without taking focus away from the game (UX-3, UX-4, UX-5).

## Acceptance Criteria

### Criterion 1: Overlay renders a stable two-agent view

**Given** `python -m lagent.ui` is running
**When** Ion enables Status Overlay
**Then** a borderless PyQt6 window appears with two stable rows, WL and PP, and each row shows agent name, FSM state, HP percentage, MP percentage, and elapsed session time

**Given** no session is active
**When** the overlay is visible
**Then** both rows show `Stopped`, HP/MP use a defined neutral display such as `--`, and no stale values or blank error widgets appear

### Criterion 2: Telemetry updates within the defined budget

**Given** a session is active and agents append state/heartbeat events to `sessions.db`
**When** the overlay refreshes
**Then** it displays the latest valid state for each agent within 2 seconds of the event timestamp, calculates elapsed time from `started_at`, and does not block the Qt event loop on database access

**Given** an event is malformed, delayed, or absent
**When** the next refresh occurs
**Then** the affected row retains its last valid value, marks the telemetry stale/error state visibly, and the other row continues updating

### Criterion 3: Overlay does not interfere with the game

**Given** the game client has focus
**When** the overlay is displayed
**Then** it remains always-on-top, does not activate or steal focus on refresh, and uses click-through/no-focus window flags so mouse and keyboard input reaches the game client

**Given** the overlay is toggled off or the UI exits
**When** the window closes
**Then** its timer and database connection are released and no orphan Qt window remains

## Dependencies

- Story 8.1 UI lifecycle and active-session selection.
- Story 1.3 `SessionsDB` schema and event reader.
- Agent/Orchestrator event payloads containing agent identity, FSM state, HP%, and MP%.
- PyQt6 6.7.x.

## Developer Context

The current `lagent/ui/` package contains only a stub entry point. Implement the overlay as UI-owned PyQt6 code, not inside an Agent process. The UI may read `sessions.db`, but it must not mutate an Agent's GameState or import Agent/FSM classes.

Prefer a read-only telemetry reader with a short-lived or dedicated UI connection and parameterized queries. Query the latest state-bearing events per agent rather than replaying the entire event table every tick. Because current DB helpers expose events but not a canonical snapshot, define and document the event payload shape consumed by the overlay, for example `source=agent.warlord|agent.prophet`, `type=state`, payload with `fsm_state`, `hp_percent`, and `mp_percent`. Preserve the last valid snapshot and compute staleness from event timestamps.

Qt polling must run on a `QTimer` at a period that supports the two-second requirement, such as 500 ms, with DB work moved off the GUI thread or bounded so paint/input handling stays responsive. Values must be sanitized and clamped to 0-100 before feeding progress bars. Session mode/profile and timer formatting should be deterministic and use the session's stored start time.

Use native Windows flags for frameless, translucent, topmost, tool, and transparent-for-input behavior. Keep the platform-specific flag setup isolated behind a small helper so Linux/macOS unit tests can exercise formatting and telemetry behavior without creating a native window.

## Technical Requirements

- Entry point module remains `python -m lagent.ui`; overlay lifetime is controlled by the tray menu.
- No full GUI panel, navigation, or training UI is in scope.
- Overlay must remain compact and stable in size; long FSM labels must elide or fit without moving neighboring fields.
- Render HP and MP with accessible text values in addition to bars; do not rely on color alone.
- Handle session rollover by discarding snapshots from an older session ID.
- Treat missing/invalid numeric telemetry as unknown, never as zero health.

## Testing Requirements

- Unit test state formatting, timer formatting, HP/MP clamping, stale detection, malformed payload handling, and session rollover.
- Test that a no-session model renders `Stopped` and unknown values.
- Test polling never displays an event from another session.
- Add an offscreen Qt test for row/widget creation and visibility.
- Add a Windows/manual smoke check for topmost, no-activate, click-through behavior and game focus preservation; skip clearly in headless CI.

## Architecture Compliance

- AD-5: Overlay is part of Tray/UI and stays outside live runtime processes.
- AD-9: Read shared `data/sessions.db` using SQLite/WAL-compatible access.
- AD-12: Do not import `lagent.agent`, `lagent.hsl`, or `lagent.gpu_server`.

## File Structure

Expected implementation surfaces: `lagent/ui/overlay.py`, `lagent/ui/telemetry.py`, and tray integration from Story 8.1. Add focused tests under `tests/test_story_8_2_status_overlay.py`.

## Completion Status

Ready for development. Ultimate context engine analysis completed - comprehensive developer guide created.

## Change Log

- 2026-08-26: Story created from Epic 8 specification.
