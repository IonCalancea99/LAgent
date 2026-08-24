---
storyId: 2.2
epic: "Epic 2: Perception Pipeline"
title: "ROI Extraction from Agent Profile"
status: ready
---

# Story 2.2: ROI Extraction from Agent Profile

## User Story

As Ion,
I want named ROI crops extracted from each captured frame using coordinates from the YAML agent profile,
So that downstream detection runs only on relevant screen regions and ROI positions can be changed via profile update without code changes (FR-2).

## Acceptance Criteria

### Criterion 1: Extract named ROI crops per profile

**Given** `warlord.yaml` defines ROIs: `hp_bar`, `mp_bar`, `buff_strip`, `mob_area`
**When** a frame is captured
**Then** each named ROI is extracted as a pixel-accurate crop matching the profile coordinates

### Criterion 2: Update ROI coordinates without code changes

**Given** the ROI coordinates in the profile are updated and the Agent restarted
**When** a new frame is captured
**Then** the extraction uses the new coordinates without any code change

### Criterion 3: Validate ROI coordinates at startup

**Given** a ROI coordinate is out of bounds for the current window resolution
**When** the Agent starts
**Then** a validation error is raised at startup identifying the offending ROI name and value

## Dependencies

- Agent profile schema with ROI definition section
- Frame object with width/height and pixel buffer
- Pydantic validation for coordinate ranges

## Notes

ROI extraction should be fast and happen inline with the capture thread. The ROI map is passed downstream to the GPU Inference Server as a dict of {roi_name: cropped_pixels}. All coordinates must be validated before the first frame capture to fail fast per FR-7 (Fail-fast config loading).
