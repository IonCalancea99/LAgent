---
storyId: 7.4
epic: "Epic 7: Training Pipeline"
title: "YouTube Frame Ingestion"
status: review
baseline_commit: b7fda8fc0bcf2e582ede9932517ba5abc30cefb1
---

# Story 7.4: YouTube Frame Ingestion

## User Story

As Ion,
I want `python -m lagent.train ingest --url <youtube-url> --fps <n>` to download the video via yt-dlp, extract frames via OpenCV, and feed them into the prelabeling pipeline,
So that I can supplement my own recordings with publicly available gameplay footage without any external API credentials (FR-22).

## Acceptance Criteria

### Criterion 1: Download video via yt-dlp

**Given** a YouTube URL pointing to a public Asterios x55 gameplay video
**When** `python -m lagent.train ingest --url <url> --fps 5` is run
**Then** yt-dlp downloads the video to a temp directory; download completes without requiring YouTube API keys or authentication credentials

### Criterion 2: Extract frames at configurable FPS

**Given** the video has been downloaded
**When** frame extraction begins
**Then** OpenCV reads the video file; frames are extracted at the specified FPS (e.g., 5 FPS for a 10-minute video = 3,000 frames); each frame is saved in the same format as Recording Mode (PNG or JPEG)

### Criterion 3: Write frames to recording directory

**Given** frame extraction has completed
**When** frames are written to disk
**Then** frames are written to a new recording directory `recordings/<ingest_session_id>/frames/` in the same structure and format as Recording Mode output; a `inputs.jsonl` stub file is created (empty or minimal, since ingested video has no input correspondence)

### Criterion 4: Performance on target hardware

**Given** a 10-minute gameplay video is ingested
**When** the process completes (download + extraction + optionally prelabeling)
**Then** total time is ≤5 minutes on the GTX 1070 Ti

### Criterion 5: Indistinguishable from recorded frames

**Given** extracted frames are in the recording directory
**When** they are fed to the prelabeling pipeline (Story 7.2) or Label Studio
**Then** they are indistinguishable in format from frames captured by Recording Mode; no special handling is required; prelabeling and labeling workflows proceed identically

## Dependencies

- yt-dlp library (added to pyproject.toml dependencies)
- OpenCV (cv2) for video frame extraction
- Recording Mode directory structure (Story 7.1) as template
- Auto-Prelabeling Pipeline (Story 7.2) as downstream consumer
- Session database for metadata tracking (Story 1.3)

## Tasks / Subtasks

- [x] Add yt-dlp and opencv-python to project dependencies (pyproject.toml)
- [x] Implement `python -m lagent.train ingest` CLI subcommand
- [x] Add argument parsing for `--url <url>`, `--fps <n>`, optional `--output-dir <path>`
- [x] Implement video URL validation (basic sanity check)
- [x] Integrate yt-dlp to download video to temp directory
- [x] Implement error handling for download failures (network, unavailable video, etc.)
- [x] Implement frame extraction via OpenCV with configurable FPS
- [x] Handle video format variations (different codecs, resolutions)
- [x] Create recording directory structure matching Story 7.1 output
- [x] Save frames to disk (PNG or JPEG, matching Recording Mode format)
- [x] Generate minimal `inputs.jsonl` stub (empty or placeholder)
- [x] Create session metadata in `recordings/<ingest_session_id>` (e.g., README with source URL)
- [x] Add progress logging and frame count display
- [x] Implement cleanup of temp download directory
- [x] Create validation: extracted frame count matches expected count at given FPS
- [x] Add smoke tests for URL validation, yt-dlp integration, and frame extraction

### Review Findings

- [ ] [Review][Patch] Reject non-finite FPS values before extraction [lagent/train/ingest.py:19]
	`_positive_fps` accepts `nan`, `inf`, and overflowed numeric values because it only checks `fps <= 0`; `inf` reaches `expected_count` and raises `OverflowError` instead of producing a clear CLI validation error.
- [ ] [Review][Patch] Remove incomplete recording directories when ingestion fails after creation [lagent/train/ingest.py:137]
	Download succeeds before `_new_recording_dir` creates the output directory, so extraction or metadata-write failures leave partial `recordings/<session>/frames` directories behind. Those directories can be mistaken for valid downstream inputs and accumulate on repeated failures.

## Notes

YouTube ingestion is optional but valuable for expanding training datasets with public gameplay footage. The video must be public and downloadable via yt-dlp without interactive login. No YouTube API key is required; yt-dlp uses client-side scraping. The 5-minute SLA (10-minute video) assumes good network bandwidth and local SSD; network-limited machines will be slower. Store the source URL and download metadata in the recording directory for reproducibility. Frame extraction via OpenCV is deterministic; the same video URL should produce the same frames across runs (barring video removal or re-upload). If a video becomes unavailable, the download fails gracefully and the user is prompted to provide an alternative.

## Technical Requirements

- CLI: `python -m lagent.train ingest --url <url> --fps <float> [--output-dir <path>]`
- Input: public YouTube video URL (or any yt-dlp-compatible URL)
- Download tool: yt-dlp (no API key required)
- Frame extraction: OpenCV cv2.VideoCapture() with frame seek-by-time
- Output directory: `recordings/<ingest_session_id>/frames/` (auto-generated session ID from timestamp or URL hash)
- Frame format: PNG or JPEG (match Recording Mode default, configurable)
- Metadata file: `recordings/<ingest_session_id>/README.txt` or JSON with source URL, download time, FPS, frame count
- Input stub: `recordings/<ingest_session_id>/inputs.jsonl` (empty or `{"ingested": true}` single line)
- Temp directory: OS temp (use `tempfile.TemporaryDirectory()`) for video download; auto-cleanup on completion
- Error messages: clear indication of download vs. extraction failure

## Testing Requirements

- Unit test: command-line argument parsing (URL, FPS validation)
- Unit test: yt-dlp availability check (graceful error if yt-dlp not installed)
- Integration test: download a small public gameplay video (real YouTube call; may need network permission)
- Integration test: extract frames at different FPS values (5, 10, etc.)
- Integration test: verify extracted frame count matches expected count
- Integration test: verify frame format (PNG/JPEG) and dimensions match expectations
- Integration test: recording directory structure validation
- Performance test: 10-minute video ingest ≤5 minutes on GTX 1070 Ti (or fast network + SSD system)
- Smoke test: error handling for invalid URL, network failure, unavailable video
- Smoke test: temp directory cleanup after ingest completes or fails

## Architecture Compliance

- AD-6: Training Pipeline (lagent.train) is separate CLI, never co-runs with live session
- NFR-1: All computation local; no cloud services, no credentials stored; only public data downloaded
- NFR-2: Windows platform — yt-dlp and OpenCV are cross-platform; verify Windows compatibility in tests
- Filename convention: recording directory naming matches epoch timestamp or deterministic URL hash for reproducibility

## Dev Agent Record

### Implementation Plan

- Add lazy yt-dlp and OpenCV integrations so CLI startup remains usable when optional tools are absent.
- Download into `TemporaryDirectory`, sample frame indices by timestamp, and write zero-padded PNGs matching Recording Mode.
- Persist empty `inputs.jsonl` plus JSON source metadata and validate the expected extracted frame count.

### Completion Notes

- Implemented `ingest` CLI and reusable ingestion functions with URL/FPS validation and contextual download/extraction errors.
- Added mocked smoke coverage for parsing, URL validation, download integration, frame extraction, output structure, metadata, and temporary-directory cleanup.
- `compileall`, VS Code diagnostics, CLI help, `git diff --check`, and the stdlib mocked smoke harness pass. Full pytest execution is unavailable because pytest is not installed in the active environment.

### File List

- `lagent/train/ingest.py`
- `lagent/train/__main__.py`
- `tests/test_story_7_4_ingestion.py`
- `pyproject.toml`
- `_bmad-output/planning-artifacts/stories/7-4-youtube-frame-ingestion.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-08-26: Implemented YouTube-compatible video ingestion, frame extraction, recording metadata, CLI wiring, dependencies, and smoke tests.

## Status

review
