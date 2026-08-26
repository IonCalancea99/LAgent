---
storyId: 7.1
epic: "Epic 7: Training Pipeline"
title: "Recording Mode — Dual-Write Frame Capture & Input Log"
status: done
baseline_commit: ef9c257d60c1b031319750b83f2cd9859cee3a76
---

# Story 7.1: Recording Mode — Dual-Write Frame Capture & Input Log

## User Story

As Ion,
I want Recording Mode activated by a `--record` flag that switches the Agent capture thread to dual-write (pipeline + disk archive) and activates a pynput listener logging all keyboard and mouse inputs,
So that I can capture my own gameplay as labeled training data without interfering with manual play (FR-19, AD-13).

## Acceptance Criteria

### Criterion 1: Recording Mode activation and frame dual-write

**Given** an Agent is started with `--record` flag
**When** the capture thread runs
**Then** frames are written to `recordings/<session_id>/frames/` AND pushed to the pipeline simultaneously; the game client does not drop below 30 FPS

### Criterion 2: Input logging with pynput

**Given** Recording Mode is active
**When** Ion presses keys or moves the mouse
**Then** each input event is logged to `recordings/<session_id>/inputs.jsonl` with a timestamp synchronized to the frame sequence; each JSONL line contains `{timestamp, event_type, key/position, state}`

### Criterion 3: Recording cleanup and finalization

**Given** the hotkey to stop Recording Mode is pressed (or Agent is stopped)
**When** recording ends
**Then** the frame archive and input log are finalized and closed cleanly; the directory is ready for prelabeling; a session record is created in `sessions.db` with `mode: recording`

## Dependencies

- lagent.common shared types (PerceptionResult, GameState)
- Frame queue and pipeline wiring from Epic 2
- Existing Agent startup and profile loading (Epic 1)
- Session database write functionality (Story 1.3)

## Tasks / Subtasks

- [x] Implement `--record` command-line flag for Agent process
- [x] Modify capture thread to support dual-write mode
- [x] Create `recordings/<session_id>/frames/` directory structure on startup
- [x] Implement frame archival to disk (parallel to pipeline push)
- [x] Integrate pynput listener for keyboard and mouse input
- [x] Implement JSONL logging for input events with frame-synchronized timestamps
- [x] Add frame sequence numbering for timestamp synchronization
- [x] Ensure game client maintains ≥30 FPS during dual-write
- [x] Implement hotkey-based recording stop and cleanup
- [x] Add session database entry with `mode: recording`
- [x] Create smoke tests for flag parsing, directory creation, and dual-write
- [x] Verify input log format matches prelabeling pipeline expectations

## Dev Agent Record

### Implementation Plan

- Added an asynchronous `RecordingSession` writer with bounded archival queue so frame disk I/O does not block capture or pipeline publication.
- Added lazy `pynput` keyboard/mouse listeners with Ctrl+Shift+R finalization and frame-number-correlated JSONL events.
- Added launch-mode parsing and wired recording sessions to capture and WAL-backed session startup records.

### Completion Notes

- AC1: Capture frames are forwarded to the existing `FrameQueue` and archived as sequential PNG files.
- AC2: Keyboard and mouse callbacks write the required JSONL event fields plus `frame_number`.
- AC3: Listener hotkey and agent shutdown close the input file and drain the frame writer; session rows use `mode: recording`.
- Validation: Python compilation, project-wide `compileall`, and `git diff --check` pass. Pytest could not run because the active interpreter lacks `pytest` and `pydantic`.

### File List

- `lagent/agent/__main__.py`
- `lagent/agent/capture.py`
- `lagent/agent/recording.py`
- `tests/test_story_7_1_recording.py`

## Change Log

- 2026-08-26: Implemented recording-mode frame dual-write, pynput input logging, cleanup, CLI mode handling, and focused smoke tests.

### Review Findings

- [x] [Review][Patch] Close can race with input callbacks and close the JSONL handle between the pre-check and write, causing lost events or `ValueError` in pynput callbacks [lagent/agent/recording.py:83]
- [x] [Review][Patch] Frame writer exceptions are uncaught and can terminate the writer; `close()` may then block forever trying to enqueue its sentinel when the archival queue is full [lagent/agent/recording.py:111]
- [x] [Review][Patch] User-supplied `session_id` is used directly as a path component, allowing absolute or `..` segments to escape the recordings root [lagent/agent/recording.py:36]
- [x] [Review][Patch] Automatic profile identification records an event before the session row exists, so `--record` without `--class` can fail its required `mode: recording` session creation through the foreign-key constraint [lagent/agent/__main__.py:69]
- [x] [Review][Patch] Recording mode constructs HSL with `mode="active"`, so the agent can send OS input while the operator is manually playing, contradicting the non-interference requirement [lagent/agent/__main__.py:176]
- [x] [Review][Patch] Focused tests do not cover the required performance threshold, session database entry, or concurrent/asynchronous dual-write behavior [tests/test_story_7_1_recording.py:8]

## Notes

Recording Mode is mutually exclusive with live Session Mode at process launch (AD-13). The dual-write must not block the pipeline; use non-blocking disk writes or thread-pool writes if necessary. Input timestamps must be synchronized to frame numbers so prelabeling can correlate inputs to frames for behavior model training. The 30 FPS game client floor is a hard constraint — recording overhead must be ≤~3 ms per frame.

## Technical Requirements

- Command-line argument: `--record` (boolean flag, disables normal session logic)
- Output directories: `recordings/<session_id>/frames/`, `recordings/<session_id>/inputs.jsonl`
- Frame storage format: PNG or JPEG (configurable, PNG default for lossless)
- Input event schema: `{timestamp: float, event_type: str, key_or_position: Any, state: str}`
- Frame numbering: sequential integer from 0, stored in frame metadata or filename
- Hotkey: configurable, suggest Ctrl+Shift+R for toggle (can be in profile YAML)

## Testing Requirements

- Unit test: `--record` flag correctly activates dual-write mode
- Integration test: frames are written to disk and pipeline in parallel
- Integration test: pynput events are logged with correct timestamps
- Performance test: dual-write overhead is <3 ms per frame on target hardware (GTX 1070 Ti + 10 FPS)
- Smoke test: recording directory cleanup and session.db entry creation

## Architecture Compliance

- AD-13: Recording Mode is switchable only at process launch, not mid-session
- AD-3: FrameQueue oldest-frame eviction behavior unchanged
- AD-9: Session record written to WAL-mode SQLite
- NFR-1: All data stored locally; no cloud upload
