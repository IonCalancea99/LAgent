---
storyId: 2.3
epic: "Epic 2: Perception Pipeline"
title: "GPU Inference Server — YOLO Detection (Common + Class Models)"
status: ready
---

# Story 2.3: GPU Inference Server — YOLO Detection (Common + Class Models)

## User Story

As Ion,
I want the GPU Inference Server to accept frame + ROI map from each Agent over DEALER/ROUTER ZeroMQ and return a merged Detection list from both Common Model and Class Model YOLOv8-nano inference,
So that both agents get class-agnostic and class-specific detections within the 100 ms per-frame budget on the GTX 1070 Ti (FR-3, AD-2).

## Acceptance Criteria

### Criterion 1: Dual-model inference with merged results

**Given** `models/common/current.pt` and `models/warlord/current.pt` exist (stub YOLOv8-nano weights)
**When** the GPU Server receives `{agent_id: "warlord", frame_bytes: <bytes>, roi_map: {...}}`
**Then** both models run inference; detections are merged into a single list; each `Detection` has `class_name: str`, `confidence: float`, `bbox_xyxy: tuple[int,int,int,int]` (pixel coords, origin top-left per AD-10b)
**And** combined inference completes in ≤100 ms per frame on the GTX 1070 Ti

### Criterion 2: Concurrent request handling per agent

**Given** both WL Agent and PP Agent send concurrent inference requests
**When** the GPU Server processes them
**Then** each agent receives only its own `PerceptionResult`; correlation by `agent_id` is correct; no cross-agent result contamination

### Criterion 3: Confidence threshold filtering

**Given** a detection falls below the configured confidence threshold
**When** the result list is assembled
**Then** that detection is excluded from `PerceptionResult.detections`

## Dependencies

- YOLOv8-nano model loading (torch inference)
- Detection dataclass with class_name, confidence, bbox_xyxy fields
- GPU memory management (VRAM budget ~2.5–3.5 GB per AD-3)
- ZeroMQ ROUTER socket on GPU Server, DEALER clients on agents
- PerceptionResult schema

## Notes

The Common Model runs on all frames regardless of class; Class Model is class-specific (loaded per agent type). Inference timing must be logged per frame to catch GPU saturation early. Box coordinates must use pixel-space origin (top-left = (0,0)) as per AD-10b. Non-maximum suppression (NMS) should be applied before merging to reduce duplicates.
