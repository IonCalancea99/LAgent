---
storyId: 3.3
epic: "Epic 3: Human Simulation Layer & Shadow Mode"
title: "Fatigue Model"
status: ready
---

# Story 3.3: Fatigue Model

## User Story

As Ion,
I want the Fatigue Factor to grow monotonically over session time and trigger an automatic Break that resets it, with all parameters configurable in the agent profile,
So that action latency variation mimics human tiredness patterns over a long session (FR-10).

## Acceptance Criteria

### Criterion 1: Monotonic fatigue growth over session time

**Given** a session starts
**When** time progresses past each fatigue increment interval (default: every 30-60 min)
**Then** `HSL.fatigue_factor` increases by the configured step; all action latencies are multiplied by the current factor

### Criterion 2: Automatic Break at fatigue ceiling

**Given** `HSL.fatigue_factor` reaches the configured ceiling
**When** the ceiling is hit
**Then** a Break is triggered automatically; no mouse or keyboard input is produced for a randomized duration within the configured break-length range (default 5-15 min); after the Break, `fatigue_factor` resets to 1.0

### Criterion 3: Independent fatigue state per agent process

**Given** two Agent processes are running (WL and PP)
**When** both have HSL instances
**Then** each instance has independent `fatigue_state`; WL fatigue does not affect PP fatigue

## Dependencies

- HSL instance-level state container
- Per-agent process boundary (no module-level shared fatigue globals)
- Session timer source and break scheduler

## Notes

Instance isolation here protects AD-8 and prevents cross-agent behavioral coupling that would appear non-human.
