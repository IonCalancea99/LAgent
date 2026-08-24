---
storyId: 2.1
epic: "Epic 2: Perception Pipeline"
title: "Screen Capture Thread — dxcam Primary, mss Fallback"
status: ready
---

# Story 2.1: Screen Capture Thread — dxcam Primary, mss Fallback

## User Story

As Ion,
I want the Agent capture thread to grab game window frames at ~10 FPS using dxcam (with mss fallback) and push them to a bounded FrameQueue,
So that frames are available for the inference pipeline within 10 ms of capture without ever blocking the capture thread (FR-1, AD-3).

## Acceptance Criteria

### Criterion 1: Capture at target rate with 10 ms latency

**Given** a Lineage 2 game window is open and bound by window title in the agent profile
**When** the Agent starts in debug mode
**Then** the capture thread captures frames at the configured rate (default 10 FPS); each frame is pushed to FrameQueue within 10 ms of capture

### Criterion 2: Bounded queue with oldest-frame eviction

**Given** the FrameQueue is already full (maxsize=2)
**When** the capture thread produces a new frame
**Then** the oldest frame is evicted and replaced by the new frame; the capture thread is never blocked by a slow downstream stage

### Criterion 3: Fallback to mss when dxcam unavailable

**Given** dxcam is unavailable (import fails)
**When** the Agent starts
**Then** the capture thread falls back to mss silently; a log message notes the fallback; capture continues at target rate

## Dependencies

- Window handle resolution from agent profile
- FrameQueue queue structure (bounded, maxsize=2)
- Millisecond-precision timestamp on each Frame

## Notes

The capture thread must never block downstream inference stages. The 10 FPS rate is sufficient for Lineage 2's ≥500 ms skill cast times. Timestamps must be captured at frame-grab time, not queue insertion time.
