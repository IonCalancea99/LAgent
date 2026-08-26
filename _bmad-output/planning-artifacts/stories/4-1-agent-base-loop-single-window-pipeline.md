---
storyId: 4.1
epic: "Epic 4: Fishing Mode"
title: "Agent Base Loop — Capture-to-Policy Single-Window Pipeline"
status: draft
---

# Story 4.1: Agent Base Loop — Capture-to-Policy Single-Window Pipeline

## User Story

As Ion,
I want the full single-window pipeline wired end-to-end: capture thread → inference client → PolicyQueue → FSM base → HSL → OS input,
So that a running Agent process completes one perception-decision-action tick per frame and I can plug in real Fishing Mode states on top of the working loop (FR-5 base).

## Acceptance Criteria

### Criterion 1: One tick per frame with end-to-end logging

**Given** a single Agent process is started with a valid profile
**When** the main loop runs
**Then** each tick captures one frame, sends it to the GPU inference server, receives a `PerceptionResult`, invokes the FSM state handler, passes the resulting `Action` through HSL, and dispatches it to the OS input API; the full tick latency is logged and a tick ID is emitted for deterministic queue eviction and latency backpressure tracing

### Criterion 2: Stable idle loop under delayed inference

**Given** the FSM is in a stub IDLE state producing a no-op action
**When** the loop runs for 60 seconds
**Then** the Agent completes at least 500 ticks (approximately 8/s); no tick causes an unhandled exception; all ticks are logged to `sessions.db`; the loop remains stable when a single frame is delayed by up to 2x the normal inference budget

### Criterion 3: Oldest-frame eviction without capture backpressure

**Given** a downstream stage such as the GPU inference server is slow for one tick
**When** the capture thread continues running
**Then** the oldest frames are evicted from `FrameQueue`; the capture thread is never blocked; no backlog causes latency to cascade across subsequent ticks; the dropped-frame count is logged with the queue state

### Criterion 4: Deterministic replayable state transitions

**Given** the base loop is under test in a deterministic harness
**When** cast, wait, and reel transitions are simulated
**Then** each state transition is replayable from a seeded input sequence and the same state machine outcome is produced across runs without dependence on wall-clock timing

## Dependencies

- Capture thread and bounded `FrameQueue`
- `InferenceClient` communication to GPU server
- Bounded `PolicyQueue` with oldest-result eviction
- Agent base loop state tick orchestration
- HSL input shaping and OS adapter handoff
- Session DB telemetry for tick metadata and dropped-frame accounting

## Notes

This story is the architecture-defined base loop for Epic 4. The implementation should be decomposed into smaller execution units before coding begins: capture queue/backpressure, inference client + latency logging, state-machine tick orchestration, and HSL/OS output handoff.
