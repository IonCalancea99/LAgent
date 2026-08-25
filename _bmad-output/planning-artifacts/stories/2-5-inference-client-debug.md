---
storyId: 2.5
epic: "Epic 2: Perception Pipeline"
title: "Inference Client, PolicyQueue & Debug Perception Display"
status: review
---

# Story 2.5: Inference Client, PolicyQueue & Debug Perception Display

## User Story

As Ion,
I want the Agent's Inference Client to pop frames from FrameQueue, send them to the GPU Server, and push the returned `PerceptionResult` to PolicyQueue — with a debug mode that logs detections and OCR values to stdout each tick,
So that I can visually verify the full capture → inference → result pipeline on a live game window before writing any policy logic (AD-3).

## Acceptance Criteria

### Criterion 1: End-to-end frame-to-result pipeline

**Given** an Agent is started with `--debug` flag against a live game window
**When** the inference loop runs
**Then** stdout shows a `PerceptionResult` log line per tick (~10/s) listing all detections with class, confidence, bbox, and all OCR values

### Criterion 2: Bounded PolicyQueue with oldest-result eviction

**Given** PolicyQueue is full (maxsize=2) when a new `PerceptionResult` arrives
**When** the Inference Client pushes the result
**Then** the oldest result is evicted; no blocking occurs on the inference path

### Criterion 3: Graceful handling of GPU Server unavailability

**Given** the GPU Server is unreachable
**When** the Agent's Inference Client attempts to send a frame
**Then** the request times out; the frame is dropped; the capture thread is not blocked; a warning is logged

## Dependencies

- FrameQueue popping logic (thread-safe queue)
- ZeroMQ DEALER socket client to GPU Server ROUTER
- PolicyQueue bounded queue (maxsize=2)
- Frame → bytes encoding/serialization
- PerceptionResult deserialization from GPU Server response
- Debug mode flag and logging formatter

## Notes

The Inference Client runs in a separate thread from the capture thread. It must not block the capture thread if the GPU Server is slow or unavailable. PolicyQueue must use oldest-result eviction (not frame-eviction) since results are more expensive to regenerate. Debug output should include per-tick latency measurements (capture→send, GPU processing, recv→push). The inference loop should run continuously at the frame rate; if no frame is available, a skip is logged but the loop continues.

## Tasks / Subtasks

- [x] Implement bounded `PolicyQueue` with oldest-result eviction.
- [x] Implement threaded `InferenceClient` with frame serialization, ROI forwarding, timeout handling, and debug output.
- [x] Wire `--debug` capture and inference startup and graceful shutdown into the Agent entry point.
- [x] Add focused tests for successful results, queue eviction, and GPU timeout handling.

## Dev Agent Record

### Implementation Plan

- Keep capture and inference in separate daemon threads so GPU latency cannot block frame production.
- Reuse `AgentTransport` for DEALER/ROUTER communication and `extract_roi_map` for profile-defined OCR crops.
- Use a queue subclass with nonblocking oldest-result eviction to preserve the newest perception state.

### Completion Notes

- Added `PolicyQueue`, `InferenceClient`, and PNG/bytes frame serialization in `lagent/agent/inference.py`.
- Added `--debug`, `--window-title`, `--gpu-endpoint`, and `--fps` pipeline startup options to the Agent entry point.
- Debug output includes detections, OCR values, and capture/send, GPU, and receive/push latency measurements.
- Focused validation passes: 3 tests passed; package compilation and diagnostics pass.
- Full perception validation is blocked for two pre-existing integration tests because the active `.venv` lacks `pyzmq`.

### File List

- `lagent/agent/inference.py`
- `lagent/agent/__main__.py`
- `tests/test_story_2_5_inference_client.py`

## Change Log

- 2026-08-25: Implemented the capture-to-perception inference client, bounded policy queue, debug CLI pipeline, and focused tests.
