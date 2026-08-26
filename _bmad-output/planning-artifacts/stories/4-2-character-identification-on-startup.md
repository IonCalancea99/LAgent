---
storyId: 4.2
epic: "Epic 4: Fishing Mode"
title: "Character Identification on Startup"
status: done
---

# Story 4.2: Character Identification on Startup

## User Story

As Ion,
I want the Agent to scan the bound game window at startup and determine the active character class via skill bar fingerprinting before starting the control loop,
So that the correct agent profile is assigned automatically and I am only prompted on ambiguous cases (FR-15).

## Acceptance Criteria

### Criterion 1: Automatic role assignment when confidence is high

**Given** a Warlord game window is the bound window
**When** the Agent starts without a `--class` flag
**Then** the startup scan identifies the window as `warlord`; the `warlord.yaml` profile is loaded; the result is logged; the auto-assignment threshold is defined as `>= 0.75` confidence for `warlord`

### Criterion 2: Manual fallback when confidence is below threshold

**Given** identification confidence is below the configured threshold (`< 0.75`)
**When** the Agent starts
**Then** the control loop is halted; Ion is prompted in the terminal to manually confirm the class assignment before the loop begins; the detection result, confidence value, and fallback path are logged

### Criterion 3: Explicit override bypasses scanning

**Given** the `--class warlord` flag is passed explicitly
**When** the Agent starts
**Then** the identification scan is skipped and the specified profile is loaded directly; the override is logged as an explicit operator decision

### Criterion 4: Manual selection persists for the session

**Given** the startup identification result is ambiguous or below threshold but the user chooses a profile manually
**When** the loop launches
**Then** the chosen profile remains active for the session and the ambiguity is recorded in `sessions.db` for later tuning

## Dependencies

- Window binding and profile resolution
- Startup scanning logic for skill-bar fingerprinting
- CLI flag handling for explicit `--class` overrides
- Session DB recording of identification confidence and manual fallback events

## Notes

The architecture's startup assignment requirement is intentional: the system should identify the class automatically in clear cases, but it must keep the operator in the loop when confidence falls below the threshold. This avoids the wrong profile being loaded silently.

### Review Findings

- [x] [Review][Patch] Normal startup never launches `AgentLoop` [lagent/agent/__main__.py:116] — Interactive startup now enters the control loop; non-interactive no-argument invocation preserves the scaffold entry-point contract.
- [x] [Review][Patch] Invalid manual profile input aborts startup [lagent/agent/__main__.py:52] — CLI and resolver validation now retry until a supported profile is selected.
- [x] [Review][Patch] Equal-confidence fingerprints are assigned by profile order [lagent/agent/startup.py:56] — Tied top-confidence fingerprints now produce an ambiguous result and use manual fallback.
