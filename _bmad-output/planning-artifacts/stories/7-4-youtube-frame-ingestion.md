---
storyId: 7.4
epic: "Epic 7: Training Pipeline"
title: "YouTube Frame Ingestion"
status: ready-for-dev
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

- [ ] Add yt-dlp and opencv-python to project dependencies (pyproject.toml)
- [ ] Implement `python -m lagent.train ingest` CLI subcommand
- [ ] Add argument parsing for `--url <url>`, `--fps <n>`, optional `--output-dir <path>`
- [ ] Implement video URL validation (basic sanity check)
- [ ] Integrate yt-dlp to download video to temp directory
- [ ] Implement error handling for download failures (network, unavailable video, etc.)
- [ ] Implement frame extraction via OpenCV with configurable FPS
- [ ] Handle video format variations (different codecs, resolutions)
- [ ] Create recording directory structure matching Story 7.1 output
- [ ] Save frames to disk (PNG or JPEG, matching Recording Mode format)
- [ ] Generate minimal `inputs.jsonl` stub (empty list or placeholder)
- [ ] Create session metadata in `recordings/<ingest_session_id>` (e.g., README with source URL)
- [ ] Add progress logging and frame count display
- [ ] Implement cleanup of temp download directory
- [ ] Create validation: extracted frame count matches expected count at given FPS
- [ ] Add smoke tests for URL validation, yt-dlp integration, and frame extraction

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
