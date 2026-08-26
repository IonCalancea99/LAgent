---
storyId: 7.3
epic: "Epic 7: Training Pipeline"
title: "Model Training & Atomic Deployment"
status: ready-for-dev
---

# Story 7.3: Model Training & Atomic Deployment

## User Story

As Ion,
I want `python -m lagent.train train --recording <path>` to fine-tune the YOLO model from corrected labels, log the run to local MLflow, and atomically replace `current.pt` only after the new model passes validation,
So that I never lose a working model and training history is fully tracked locally (FR-21, AD-7).

## Acceptance Criteria

### Criterion 1: Fine-tune YOLO model from annotated recording

**Given** a recording directory with corrected Label Studio annotations (imported back to `recordings/<session_id>/labels.json`)
**When** `python -m lagent.train train --recording recordings/<session_id>` is run
**Then** YOLOv8-nano is initialized from `models/common/current.pt`; training dataset is constructed from frames and corrected labels; fine-tuning proceeds for a configured number of epochs; training metrics (loss, mAP, precision, recall) are logged per epoch

### Criterion 2: Local MLflow logging and versioning

**Given** training has started
**When** each epoch completes
**Then** metrics are logged to local MLflow (run directory: `models/.mlflow/` or configured path); training parameters (learning rate, batch size, epochs, dataset snapshot hash) are recorded; the model version is incremented

### Criterion 3: Model validation before deployment

**Given** training has completed
**When** the validation dataset (subset of corrected labels) is evaluated
**Then** the new model is tested on validation frames; mAP score is computed; if mAP >= configured threshold (default 0.65), the model is eligible for deployment

### Criterion 4: Atomic model replacement with archival

**Given** validation passes
**When** deployment begins
**Then** the new model is written to a temp file; `models/common/current.pt` (or class-specific path) is validated; the temp model replaces current via `os.replace()` atomically; the prior `current.pt` is archived to `models/common/backup_<timestamp>.pt`; no two valid models with the same name coexist during swap

### Criterion 5: Fast training turnaround

**Given** training completes on the GTX 1070 Ti from a 30-minute labeled recording (≈9,000–18,000 frames)
**When** the training run finishes (5–15 epochs)
**Then** wall-clock time from start to deployment ≤2 hours; the new model produces detections when loaded in the GPU Inference Server

## Dependencies

- Auto-Prelabeling Pipeline (Story 7.2) to produce and validate label quality
- Recording Mode (Story 7.1) to provide training data
- Existing GPU Inference Server model loading (Epic 2, Story 2.3)
- Session database for run metadata (Story 1.3)
- Local MLflow setup for experiment tracking

## Tasks / Subtasks

- [ ] Implement `python -m lagent.train train` CLI subcommand
- [ ] Add argument parsing for `--recording <path>` and optional `--epochs <n>`, `--batch-size <n>`, `--validation-split <0.0-1.0>`
- [ ] Validate Label Studio annotations exist in recording directory
- [ ] Implement dataset loader: frames + bounding box parsing from Label Studio JSON
- [ ] Split dataset into training and validation subsets (default 80/20)
- [ ] Initialize YOLOv8-nano from `models/common/current.pt`
- [ ] Implement fine-tuning training loop with PyTorch/YOLOv8 API
- [ ] Log training metrics (loss, mAP, precision, recall) to local MLflow per epoch
- [ ] Store training parameters and dataset metadata in MLflow run
- [ ] Implement validation dataset evaluation
- [ ] Compute and log validation mAP score
- [ ] Implement validation threshold check (default 0.65)
- [ ] Implement atomic deployment: temp write, validate, os.replace(), archive prior model
- [ ] Add safeguards: do not overwrite a model with a worse model
- [ ] Add logging for every deployment decision (pass/fail reason)
- [ ] Create comprehensive smoke tests for training loop and model swap

## Notes

Training is an offline process that must never co-run with a live session (AD-6). The GTX 1070 Ti has 8 GB VRAM; training alone uses 4–6 GB, so concurrent inference is not feasible. The atomic deployment is critical: a failed mid-swap must never leave `current.pt` in a corrupted state. Always archive the prior model; do not delete. MLflow should track a complete audit trail: model version, dataset hash, hyperparameters, metrics, and timestamp. The 2-hour SLA assumes ~9,000–18,000 frames and 5–15 epochs; larger datasets or more epochs will take longer — document this constraint.

## Technical Requirements

- CLI: `python -m lagent.train train --recording <path> [--epochs <n>] [--batch-size <n>] [--validation-split <float>] [--lr <float>]`
- Dataset format: Label Studio JSON annotations (from Story 7.2) + frame images
- Model initialization: load from `models/common/current.pt`
- Training framework: YOLOv8-nano with PyTorch backend
- Hyperparameters: epochs (default 10), batch size (default 16 or 32 depending on VRAM), learning rate (default 0.001)
- Validation threshold: mAP >= 0.65 (configurable in config.yaml)
- Output model: saved to `models/common/current.pt` after passing validation
- Archive naming: `models/common/backup_<timestamp>_<prior_version>.pt`
- MLflow tracking: local directory `models/.mlflow/`, runs include metadata, metrics, and model artifact
- Atomic swap: Python `os.replace()` on the model file

## Testing Requirements

- Unit test: command-line argument parsing
- Unit test: dataset loader validation (frames and annotations exist)
- Unit test: train/validation split correctness
- Integration test: training loop completes without errors on sample dataset
- Integration test: MLflow run is created and metrics are logged
- Integration test: validation score is computed and logged
- Integration test: atomic model replacement works; prior model is archived
- Integration test: new model loads in GPU Inference Server without errors
- Performance test: 30-minute recording training ≤2 hours on GTX 1070 Ti
- Smoke test: recovery from training failure (dataset parse error, CUDA OOM) — do not swap model

## Architecture Compliance

- AD-6: Training Pipeline is separate CLI (`python -m lagent.train`); never co-runs with live session
- AD-7: No in-session model reload; model swap only on disk, GPU Server picks up on next startup
- NFR-1: All training local; no cloud services, no external model hub uploads
- NFR-3: GTX 1070 Ti VRAM budget for training: 4–6 GB; must not run concurrently with inference
