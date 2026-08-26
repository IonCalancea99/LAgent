---
storyId: 3.4
epic: "Epic 3: Human Simulation Layer & Shadow Mode"
title: "Micro-drift and Error Injection"
status: done
---

# Story 3.4: Micro-drift and Error Injection

## User Story

As Ion,
I want occasional small cursor movements to non-target positions (micro-drift) and rare deliberate misclick-and-correct sequences (error injection) wired into the HSL,
So that the bot's idle and action patterns are statistically indistinguishable from natural human imprecision (FR-11, FR-12, AD-8).

## Acceptance Criteria

### Criterion 1: Configurable micro-drift behavior

**Given** micro-drift is enabled in the profile (off-by-default)
**When** the Agent is idle between actions
**Then** small cursor movements to non-target positions occur at the configured frequency and magnitude; camera drift occurs at the configured rate

### Criterion 2: Low-rate error injection with corrective action

**Given** error injection probability is set to 2% in the profile
**When** 200 actions are executed
**Then** approximately 2-6 deliberate misclicks occur; each is followed by a corrective action within one decision cycle; each override is logged as an `override` event in `sessions.db`

### Criterion 3: Mandatory HSL dispatch path for actions

**Given** an `Action` is produced by the FSM policy
**When** it is dispatched
**Then** it must pass through the caller's `HSL` instance before reaching the OS input API; no code path bypasses HSL (AD-8)

## Tasks / Subtasks

- [x] Add off-by-default cursor and camera drift profile controls
- [x] Implement idle micro-drift with configured frequency and magnitude
- [x] Add HSL action dispatcher for mouse, keyboard, and wait actions
- [x] Implement eligible click misclick and corrective click sequence
- [x] Log each injected override through `SessionsDB.append_event`
- [x] Protect key and wait actions from error injection by default
- [x] Add focused Story 3.4 regression tests

### Review Findings

- [x] [Review][Patch] Idle micro-drift leaves `cursor_position` stale [lagent/hsl/mouse.py:344] — fixed by synchronizing the tracked cursor position with the returned origin.
- [x] [Review][Patch] Runtime dict profiles accept malformed micro-drift magnitudes [lagent/hsl/mouse.py:293] — fixed by centralizing shape, finiteness, and positivity validation.
- [ ] [Review][Patch] No policy-to-HSL integration enforces the mandatory dispatch boundary [lagent/hsl/mouse.py:275] — the repository has no production caller that sends policy `Action` objects through `dispatch_action()`; existing public `move_mouse()` and `press_key()` methods remain directly callable, so AC3/AD-8 is convention-only and unverified end to end.
- [x] [Review][Defer] Dict profile Bezier range is ignored [lagent/hsl/mouse.py:390] — deferred, pre-existing; `move_mouse()` already used `getattr()` before Story 3.4 and does not honor `bezier_offset_range` when `profile` is a dict.

## Dev Agent Record

### Completion Notes

- Added profile-configurable cursor drift, camera drift callback, error probability, and protected action types.
- Added `HSL.dispatch_action` and `HSL.dispatch` so policy actions have one HSL-owned dispatch boundary.
- Error injection performs a wrong-target click, corrective movement, and target click, then logs an `override` event when a session database is provided.
- Focused validation: 4 Story 3.4 tests passed; existing Stories 3.1-3.3 HSL tests passed (14 tests).

### File List

- lagent/common/types.py
- lagent/hsl/mouse.py
- tests/test_story_3_4_drift_error_injection.py

## Change Log

- 2026-08-26: Implemented micro-drift, camera drift callback, HSL action dispatch, corrective error injection, and override logging.

## Status

in-progress

## Dependencies

- HSL action dispatcher interception point
- Profile settings for drift frequency/magnitude and error probability
- Session DB writer for override events

## Notes

Error injection should be disabled or tightly constrained for safety-critical actions where correction cannot be guaranteed within one decision cycle.
