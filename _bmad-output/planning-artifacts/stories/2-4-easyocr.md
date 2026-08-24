---
storyId: 2.4
epic: "Epic 2: Perception Pipeline"
title: "EasyOCR Integration — HP/MP/Buff Numeric Values"
status: ready
---

# Story 2.4: EasyOCR Integration — HP/MP/Buff Numeric Values

## User Story

As Ion,
I want the GPU Inference Server to run EasyOCR on the HP bar, MP bar, and buff-timer ROI crops and include the extracted values in `PerceptionResult.ocr_values`,
So that Agents have current numeric HP%, MP%, and buff counts in their GameState without running OCR locally (FR-4, AD-10).

## Acceptance Criteria

### Criterion 1: Extract numeric values from ROI crops

**Given** valid HP bar and MP bar ROI crops from a live game frame
**When** EasyOCR runs on those crops
**Then** `ocr_values` dict contains keys `hp`, `mp`, and at least one `buff_*` key with string-encoded numeric values

### Criterion 2: GPU acceleration when available

**Given** a CUDA-capable GPU is present
**When** the GPU Server starts
**Then** EasyOCR runs on GPU; a log line confirms "OCR device: cuda"

### Criterion 3: Graceful CPU fallback

**Given** no CUDA device is available
**When** the GPU Server starts
**Then** EasyOCR falls back to CPU; a log line confirms "OCR device: cpu"; inference continues without error

## Dependencies

- EasyOCR library (easyocr)
- ROI crop pixel buffers from the inference pipeline
- Numeric parsing logic (handle "245/500" → "245", "500" or percentage formats)
- CUDA/device detection

## Notes

OCR latency should be tracked separately from YOLO to identify bottlenecks. Buff timers may be formatted as "12:34" (minutes:seconds) or numeric counts; parser should handle both. Invalid OCR reads (e.g., all zeros on a blank region) should be logged but not cause errors. OCR results should be included in PerceptionResult alongside Detection list so FSM policy can make decisions based on HP%, MP%, and active buffs. EasyOCR should run on the same GPU as YOLO inference.
