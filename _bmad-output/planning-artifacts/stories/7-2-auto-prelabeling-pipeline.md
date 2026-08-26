---
storyId: 7.2
epic: "Epic 7: Training Pipeline"
title: "Auto-Prelabeling Pipeline"
status: ready-for-dev
---

# Story 7.2: Auto-Prelabeling Pipeline

## User Story

As Ion,
I want `python -m lagent.train prelabel --recording <path>` to apply the current YOLO models to all captured frames and produce a Label Studio–importable annotation file,
So that I only need to correct the labels that YOLO got wrong — not annotate everything from scratch (FR-20).

## Acceptance Criteria

### Criterion 1: Apply YOLO models to recorded frames

**Given** a recording directory containing captured frames (from Story 7.1 or YouTube ingestion)
**When** `python -m lagent.train prelabel --recording recordings/<session_id>` is run
**Then** the current `models/common/current.pt` and class-specific `models/<class>/current.pt` models are applied to all frames; detections are extracted with confidence scores and bounding boxes

### Criterion 2: Label Studio format output

**Given** prelabeling has completed on all frames
**When** checking the recording directory
**Then** a `prelabeled.json` annotation file is written in Label Studio import format (standard Label Studio JSON schema with image URLs, regions, and bbox coordinates); the file is ready for direct import

### Criterion 3: Prelabeling performance on target hardware

**Given** a 30-minute recording (≈18,000 frames at 10 FPS)
**When** prelabeling runs on a GTX 1070 Ti with batch processing
**Then** prelabeling completes in ≤15 minutes

### Criterion 4: Label Studio import compatibility

**Given** the `prelabeled.json` file exists
**When** it is imported into a local Label Studio project
**Then** all frames load with bounding box annotations; no format conversion is required; annotators can immediately begin correcting labels

## Dependencies

- lagent.train module infrastructure (Story 1.1, lagent/train/__main__.py)
- Recording Mode (Story 7.1) or YouTube ingestion (Story 7.4) to provide frame directory
- GPU Inference Server model loading logic (Epic 2, Story 2.3)
- Session database for metadata tracking

## Tasks / Subtasks

- [ ] Implement `python -m lagent.train prelabel` CLI subcommand
- [ ] Add argument parsing for `--recording <path>` directory path
- [ ] Validate recording directory structure and frame files
- [ ] Implement batch frame loading from disk
- [ ] Integrate GPU Inference Server model loading for inference
- [ ] Implement YOLO inference loop over all frames with batching
- [ ] Extract detections: class name, confidence, bounding box (xyxy format)
- [ ] Convert xyxy bounding boxes to Label Studio xywh format
- [ ] Generate Label Studio JSON annotation file schema
- [ ] Map frame filenames to Label Studio task IDs
- [ ] Implement atomic write to `recordings/<session_id>/prelabeled.json`
- [ ] Add progress logging and ETA display
- [ ] Create validation for output JSON against Label Studio schema
- [ ] Add smoke tests for frame directory validation and YOLO inference

## Notes

Prelabeling is an offline, non-real-time process. Batch processing on GPU is essential to meet the 15-minute SLA. The output JSON must be deterministic (no random ordering) for reproducibility. If a frame fails to load or inference errors occur, log the issue and skip that frame; do not halt the entire run. Store frame metadata (original filename, index) in the Label Studio output for traceability. The confidence scores in the output can be used later for quality metrics and automated acceptance filters.

## Technical Requirements

- CLI: `python -m lagent.train prelabel --recording <path> [--batch-size <n>] [--confidence-threshold <0.0-1.0>]`
- Input frame formats: PNG, JPEG (auto-detect)
- Output: `recordings/<session_id>/prelabeled.json` (Label Studio format)
- Label Studio JSON schema: tasks list with image data URL, regions (bounding boxes with class names and confidence)
- Confidence threshold: configurable, default 0.5 (filters low-confidence detections from output)
- Batch size: configurable, default 32 (tune for GTX 1070 Ti memory)
- Frame loading: in-memory batches of size N, process sequentially

## Testing Requirements

- Unit test: `--recording` argument validation
- Unit test: recording directory structure validation (frames/ and inputs.jsonl existence)
- Integration test: YOLO inference on sample recording; verify output format
- Integration test: Label Studio JSON schema validation (use Label Studio's own schema)
- Performance test: 30-minute recording prelabeling ≤15 minutes on GTX 1070 Ti
- Integration test: import output JSON into real Label Studio instance

## Architecture Compliance

- AD-7: No in-session model reload; always load from `models/<class>/current.pt` at startup
- AD-6: Training Pipeline (lagent.train) is separate CLI, never co-runs with live session
- NFR-1: All computation local; no cloud services
- NFR-3: VRAM budget ~2.5–3.5 GB during inference (same as runtime)
