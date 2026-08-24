---
storyId: 3.2
epic: "Epic 3: Human Simulation Layer & Shadow Mode"
title: "Keystroke Timing Noise"
status: ready
---

# Story 3.2: Keystroke Timing Noise

## User Story

As Ion,
I want inter-key delays for all skill key sequences drawn from a per-skill Gaussian distribution,
So that keystroke timing is statistically human-like and never mechanically uniform (FR-9).

## Acceptance Criteria

### Criterion 1: Per-skill Gaussian delay sampling

**Given** a skill key sequence is executed
**When** `HSL.press_key(skill_id, key)` is called
**Then** the inter-key delay is sampled from the Gaussian distribution for that `skill_id` (mean + std from profile defaults)

### Criterion 2: Non-uniform repeated timings

**Given** 50 presses of the same skill key
**When** their delays are measured
**Then** the distribution has non-zero standard deviation; no two consecutive delays are identical

### Criterion 3: Training-updated timing parameters are applied

**Given** a training run updates timing params for a skill
**When** the updated params are loaded
**Then** subsequent key presses for that skill use the new mean and std

## Dependencies

- HSL keystroke dispatcher
- Profile schema fields for timing means and standard deviations
- Training pipeline export format for timing parameters

## Notes

This story should avoid hardcoded timing constants except bootstrap defaults, with all operational values loaded from profile or training output.
