---
storyId: 3.5
epic: "Epic 3: Human Simulation Layer & Shadow Mode"
title: "Shadow Mode - Full HSL Shaping Without OS Output"
status: ready
---

# Story 3.5: Shadow Mode - Full HSL Shaping Without OS Output

## User Story

As Ion,
I want a `--shadow` launch flag that runs the full HSL shaping pipeline but suppresses all OS input API calls,
So that I can validate the bot's behavioral fingerprint against my recorded play before any live session (FR-24).

## Acceptance Criteria

### Criterion 1: HSL shaping executes with zero live input emission

**Given** an Agent is started with `--shadow` flag
**When** the policy produces actions
**Then** all actions pass through HSL (Bezier path computed, timing sampled, fatigue applied) and are written to the session log; no mouse or keyboard events are sent to Windows

### Criterion 2: Shadow sessions are explicitly logged and inspectable

**Given** a Shadow Mode session completes
**When** the session log is inspected
**Then** the session record has `mode: shadow`; all shaped actions (including Bezier path, timing value, fatigue factor) are logged; the log is clearly distinguishable from a live session

### Criterion 3: Mode is fixed at process start

**Given** `--shadow` flag is present at launch
**When** the Agent is running
**Then** there is no runtime mechanism to switch to live mode; mode is fixed at process start

## Dependencies

- Agent CLI startup mode parser
- HSL shaping pipeline instrumentation
- OS input adapter with hard suppression path in shadow mode
- Session DB logging of mode and shaped action metadata

## Notes

Shadow mode must be immutable for a running process to avoid accidental transition into live input during validation sessions.
