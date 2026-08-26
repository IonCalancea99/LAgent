"""Story 7.2: Auto-Prelabeling Pipeline

CLI subcommand for applying YOLO models to recorded frames and generating
Label Studio JSON annotations in a single offline batch process.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from lagent.common import Detection, PerceptionResult
from lagent.gpu_server.server import YoloInference

logger = logging.getLogger(__name__)


def parse_prelabel_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for prelabel subcommand.
    
    AC-1: CLI interface — `python -m lagent.train prelabel --recording <path>`
    """
    parser = argparse.ArgumentParser(
        prog="lagent.train.prelabel",
        description="Apply YOLO models to recorded frames and generate Label Studio annotations",
    )
    parser.add_argument(
        "--recording",
        type=Path,
        required=True,
        help="Path to recording directory containing frames/ subdirectory",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for frame inference (default: 32)",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Confidence threshold for detections (default: 0.5)",
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=Path("models"),
        help="Root directory for YOLO models (default: models)",
    )
    return parser.parse_args(args)


def validate_recording_directory(recording_dir: Path) -> None:
    """Validate recording directory structure.
    
    AC-1: Recording directory must contain:
      - frames/ subdirectory with image files
      - inputs.jsonl metadata file
    """
    if not recording_dir.exists():
        raise FileNotFoundError(f"Recording directory not found: {recording_dir}")

    frames_dir = recording_dir / "frames"
    if not frames_dir.exists():
        raise ValueError(f"Recording directory missing 'frames/' subdirectory: {recording_dir}")

    inputs_file = recording_dir / "inputs.jsonl"
    if not inputs_file.exists():
        raise ValueError(f"Recording directory missing 'inputs.jsonl' file: {recording_dir}")

    logger.info("Recording directory validated: %s", recording_dir)


def list_frame_files(frames_dir: Path) -> list[Path]:
    """List frame files in directory, sorted by name.
    
    AC-1: Support PNG and JPEG formats.
    """
    frame_extensions = {".png", ".jpg", ".jpeg"}
    frames = [
        f for f in frames_dir.iterdir()
        if f.is_file() and f.suffix.lower() in frame_extensions
    ]
    frames.sort(key=lambda x: x.name)
    logger.info("Found %d frame files in %s", len(frames), frames_dir)
    return frames


def batch_frame_loader(frames_dir: Path, batch_size: int = 32) -> list[list[Path]]:
    """Load frame file paths in batches.
    
    Yields batches of frame paths for efficient processing.
    """
    frames = list_frame_files(frames_dir)
    batches = [frames[i : i + batch_size] for i in range(0, len(frames), batch_size)]
    logger.info("Created %d batches of %d frames", len(batches), batch_size)
    return batches


def load_frame_safe(frame_path: Path) -> Any | None:
    """Load frame from disk; return None on error.
    
    AC-4: Skip invalid frames and continue pipeline.
    """
    try:
        from PIL import Image
        frame = Image.open(frame_path)
        frame.load()  # Force load to detect corruption early
        return frame
    except Exception as exc:
        logger.warning("Failed to load frame %s: %s", frame_path, exc)
        return None


def create_yolo_detector(
    model_root: Path = Path("models"),
    confidence_threshold: float = 0.5,
) -> YoloInference:
    """Create YOLO detector instance.
    
    AC-1: Load models from models/common/current.pt and models/<class>/current.pt.
    """
    logger.info("Loading YOLO models from %s", model_root)
    detector = YoloInference(
        model_root=model_root,
        confidence_threshold=confidence_threshold,
    )
    logger.info("YOLO detector ready with %d models loaded", len(detector.models))
    return detector


def run_inference_on_batch(
    detector: YoloInference,
    frame_paths: list[Path],
) -> list[tuple[Path, PerceptionResult]]:
    """Run YOLO inference on a batch of frames.
    
    AC-1: Extract class name, confidence, and bounding boxes.
    Returns list of (frame_path, PerceptionResult) tuples.
    """
    results: list[tuple[Path, PerceptionResult]] = []
    
    for frame_path in frame_paths:
        frame = load_frame_safe(frame_path)
        if frame is None:
            logger.warning("Skipping frame due to load failure: %s", frame_path)
            continue
        
        try:
            # Use 'common' as agent_id for prelabeling (offline, no specific agent)
            perception = detector.detect(frame, agent_id="common")
            results.append((frame_path, perception))
            logger.debug(
                "Inference complete: %s → %d detections",
                frame_path.name,
                len(perception.detections),
            )
        except Exception as exc:
            logger.warning("Inference failed for frame %s: %s", frame_path, exc)
            continue
    
    logger.info("Batch inference complete: %d / %d frames", len(results), len(frame_paths))
    return results


def convert_bbox_xyxy_to_label_studio(bbox_xyxy: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Convert bounding box from xyxy to xywh format.
    
    AC-2: Label Studio uses xywh (x, y, width, height) format.
    Input (xyxy): (x1, y1, x2, y2) — top-left and bottom-right corners
    Output (xywh): (x, y, width, height)
    """
    x1, y1, x2, y2 = bbox_xyxy
    width = x2 - x1
    height = y2 - y1
    return (x1, y1, width, height)


def build_label_studio_json(
    inference_results: list[tuple[Path, PerceptionResult]],
    recording_dir: Path,
) -> list[dict[str, Any]]:
    """Convert inference results to Label Studio JSON format.
    
    AC-2: Generate Label Studio JSON with:
      - Image URLs/paths
      - Bounding box regions with class names and confidence
      - Deterministic ordering (reproducible)
    
    AC-3: Include frame metadata for traceability.
    """
    tasks: list[dict[str, Any]] = []
    
    for task_id, (frame_path, perception) in enumerate(inference_results, start=1):
        # Build annotations from detections
        regions: list[dict[str, Any]] = []
        for detection in perception.detections:
            x, y, width, height = convert_bbox_xyxy_to_label_studio(detection.bbox_xyxy)
            
            region = {
                "id": f"region_{len(regions)}",
                "type": "rectangle",
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "rotation": 0,
                "label": [detection.class_name],
                "score": detection.confidence,
            }
            regions.append(region)
        
        # Create task
        task = {
            "id": task_id,
            "data": {
                "image": str(frame_path.name),  # Frame filename for reference
                "image_url": str(frame_path),   # Full path for Label Studio import
            },
            "annotations": [
                {
                    "id": f"annotation_{task_id}",
                    "completed_by": 1,  # Prelabeled by system
                    "result": regions,
                }
            ] if regions else [],
            "meta": {
                "frame_index": task_id - 1,
                "frame_name": frame_path.name,
            }
        }
        tasks.append(task)
    
    logger.info("Built Label Studio JSON with %d tasks", len(tasks))
    return tasks


def write_label_studio_json(recording_dir: Path, tasks: list[dict[str, Any]]) -> Path:
    """Write Label Studio JSON file atomically.
    
    AC-2: Write to recordings/<session_id>/prelabeled.json.
    AC-4: Atomic write for consistency.
    """
    output_file = recording_dir / "prelabeled.json"
    temp_file = recording_dir / "prelabeled.json.tmp"
    
    # Write to temporary file first
    with open(temp_file, "w") as f:
        json.dump(tasks, f, indent=2)
    
    # Atomic rename
    temp_file.replace(output_file)
    logger.info("Label Studio JSON written: %s", output_file)
    
    return output_file


def run_prelabeling(
    recording_dir: Path,
    batch_size: int = 32,
    confidence_threshold: float = 0.5,
    model_root: Path = Path("models"),
) -> Path:
    """Execute prelabeling pipeline end-to-end.
    
    AC-1: Apply YOLO models to all frames in recording directory
    AC-2: Generate Label Studio JSON output
    AC-3: Complete within performance SLA (15 min for 30-min recording on GTX 1070 Ti)
    AC-4: Robust error handling — skip failed frames, log issues
    """
    import time
    
    logger.info("Starting prelabeling pipeline: %s", recording_dir)
    start_time = time.perf_counter()
    
    # Step 1: Validate recording directory
    validate_recording_directory(recording_dir)
    
    # Step 2: Create YOLO detector
    detector = create_yolo_detector(
        model_root=model_root,
        confidence_threshold=confidence_threshold,
    )
    
    # Step 3: Load frames in batches
    batches = batch_frame_loader(recording_dir / "frames", batch_size=batch_size)
    logger.info("Processing %d batches of up to %d frames", len(batches), batch_size)
    
    # Step 4: Run inference on all batches
    all_results: list[tuple[Path, PerceptionResult]] = []
    for batch_idx, batch in enumerate(batches):
        batch_results = run_inference_on_batch(detector, batch)
        all_results.extend(batch_results)
        logger.info("Batch %d / %d complete", batch_idx + 1, len(batches))
    
    # Step 5: Generate Label Studio JSON
    tasks = build_label_studio_json(all_results, recording_dir)
    
    # Step 6: Write output file
    output_file = write_label_studio_json(recording_dir, tasks)
    
    elapsed_time = time.perf_counter() - start_time
    logger.info(
        "Prelabeling complete: %d frames processed in %.2f seconds",
        len(all_results),
        elapsed_time,
    )
    
    return output_file


def prelabel_command() -> None:
    """Entry point for prelabel CLI subcommand."""
    args = parse_prelabel_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    try:
        output_file = run_prelabeling(
            args.recording,
            batch_size=args.batch_size,
            confidence_threshold=args.confidence_threshold,
            model_root=args.model_root,
        )
        print(f"✓ Prelabeling complete: {output_file}")
    except Exception as exc:
        logger.error("Prelabeling failed: %s", exc)
        raise


if __name__ == "__main__":
    prelabel_command()
