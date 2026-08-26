---
storyId: 7.1
epic: "Epic 7: Training Pipeline"
title: "Recording Mode — Dual-Write Frame Capture & Input Log"
status: ready-for-dev
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

- [ ] Implement `--record` command-line flag for Agent process
- [ ] Modify capture thread to support dual-write mode
- [ ] Create `recordings/<session_id>/frames/` directory structure on startup
- [ ] Implement frame archival to disk (parallel to pipeline push)
- [ ] Integrate pynput listener for keyboard and mouse input
- [ ] Implement JSONL logging for input events with frame-synchronized timestamps
- [ ] Add frame sequence numbering for timestamp synchronization
- [ ] Ensure game client maintains ≥30 FPS during dual-write
- [ ] Implement hotkey-based recording stop and cleanup
- [ ] Add session database entry with `mode: recording`
- [ ] Create smoke tests for flag parsing, directory creation, and dual-write
- [ ] Verify input log format matches prelabeling pipeline expectations

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
