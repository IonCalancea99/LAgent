---
storyId: 3.4
epic: "Epic 3: Human Simulation Layer & Shadow Mode"
title: "Micro-drift and Error Injection"
status: ready
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

## Dependencies

- HSL action dispatcher interception point
- Profile settings for drift frequency/magnitude and error probability
- Session DB writer for override events

## Notes

Error injection should be disabled or tightly constrained for safety-critical actions where correction cannot be guaranteed within one decision cycle.
