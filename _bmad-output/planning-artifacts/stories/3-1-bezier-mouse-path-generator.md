---
storyId: 3.1
epic: "Epic 3: Human Simulation Layer & Shadow Mode"
title: "Bezier Mouse Path Generator"
status: done
---

# Story 3.1: Bezier Mouse Path Generator

## User Story

As Ion,
I want all mouse moves routed through a cubic Bezier path generator with randomized control point offsets and a bell-curve speed profile,
So that no straight-line mouse movement is ever produced by the bot and cursor paths look human under visual inspection (FR-8).

## Acceptance Criteria

### Criterion 1: Cubic Bezier path for every move

**Given** a source position and a target position
**When** `HSL.move_mouse(src, dst)` is called
**Then** the cursor follows a cubic Bezier path; control point offsets are drawn from the configured range (default +/-15-30 px); no straight-line path is produced

### Criterion 2: Human-like variability over repeated moves

**Given** 100 mouse moves are generated between the same two points
**When** their paths are inspected
**Then** no two paths are identical; speed profiles follow a bell curve (slow-fast-slow) with +/-10% per-path variance

### Criterion 3: Profile-driven configuration

**Given** the `bezier_offset_range` is changed in the profile
**When** new moves are generated
**Then** control point offsets reflect the new range without code changes

## Dependencies

- HSL mouse movement module
- Agent profile loader for `bezier_offset_range`
- Deterministic path sampler hooks for validation tests

## Notes

This story should enforce the invariant that all mouse moves flow through HSL and no alternate direct OS mouse path exists.
