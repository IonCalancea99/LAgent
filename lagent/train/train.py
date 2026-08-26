"""Story 7.3: Model Training & Atomic Deployment

Fine-tune YOLO models from corrected Label Studio annotations with local MLflow tracking
and atomic deployment to models/<class>/current.pt.

CLI: python -m lagent.train train --recording <path> [--epochs <n>] [--batch-size <n>] [--validation-split <0.0-1.0>] [--lr <float>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover - exercised when optional ML dependencies are absent
    YOLO = None

try:
    import mlflow
except ImportError:  # pragma: no cover - local JSON tracking remains available for minimal installs
    mlflow = None


def parse_train_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for train subcommand.
    
    AC-1: CLI interface — `python -m lagent.train train --recording <path>`
    """
    parser = argparse.ArgumentParser(
        prog="lagent.train.train",
        description="Fine-tune YOLO model from corrected Label Studio annotations",
    )
    parser.add_argument(
        "subcommand",
        nargs="?",
        choices=["train"],
        default="train",
        help="Training subcommand (train)",
    )
    parser.add_argument(
        "--recording",
        type=Path,
        required=True,
        help="Path to recording directory containing frames/ and labels.json",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=10,
        help="Number of training epochs (default: 10)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Batch size for training (default: 16)",
    )
    parser.add_argument(
        "--validation-split",
        type=float,
        default=0.8,
        help="Fraction of dataset for training vs validation (default: 0.8 = 80%% train, 20%% validation)",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=0.001,
        help="Learning rate (default: 0.001)",
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=Path("models"),
        help="Root directory for models (default: models)",
    )
    parser.add_argument(
        "--mlflow-dir",
        type=Path,
        default=Path("models/.mlflow"),
        help="MLflow tracking directory (default: models/.mlflow)",
    )
    parser.add_argument(
        "--mAP-threshold",
        type=float,
        default=0.65,
        help="Minimum mAP50 threshold for deployment (default: 0.65)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="Device for training: cuda or cpu (default: cuda)",
    )
    parser.add_argument(
        "--model-class",
        type=str,
        default="common",
        help="Model class directory to train and deploy (default: common)",
    )

    return parser.parse_args(args)


def validate_training_dataset(recording_dir: Path) -> None:
    """Validate recording directory has required structure for training.
    
    AC-1: Recording directory must contain:
      - frames/ subdirectory with image files
      - labels.json with Label Studio annotations
    """
    recording_dir = Path(recording_dir)
    
    if not recording_dir.exists():
        raise FileNotFoundError(f"Recording directory not found: {recording_dir}")

    frames_dir = recording_dir / "frames"
    if not frames_dir.exists() or not frames_dir.is_dir():
        raise ValueError(
            f"Recording directory missing 'frames/' subdirectory: {recording_dir}"
        )

    labels_file = recording_dir / "labels.json"
    if not labels_file.exists():
        raise ValueError(
            f"Recording directory missing 'labels.json' file: {recording_dir}"
        )

    # Verify frames exist
    frame_extensions = {".png", ".jpg", ".jpeg"}
    frames = [
        f for f in frames_dir.iterdir()
        if f.is_file() and f.suffix.lower() in frame_extensions
    ]
    
    if not frames:
        raise ValueError(f"No frame files found in {frames_dir}")

    logger.info(
        "Recording directory validated: %s (%d frames)",
        recording_dir,
        len(frames),
    )


def load_label_studio_annotations(labels_file: Path) -> list[dict[str, Any]]:
    """Load and parse Label Studio JSON format annotations.
    
    AC-1: Parse Label Studio JSON with:
      - tasks[].data.image: frame filename
      - tasks[].annotations[].result[]: bounding boxes with labels and confidence
    
    Returns list of annotation dicts with frame_path and annotations.
    """
    labels_file = Path(labels_file)
    
    if not labels_file.exists():
        raise FileNotFoundError(f"Labels file not found: {labels_file}")

    with open(labels_file, "r") as f:
        label_studio_data = json.load(f)

    annotations_list = []
    
    for task in label_studio_data.get("tasks", []):
        frame_name = task.get("data", {}).get("image")
        if not frame_name:
            logger.warning("Task %s missing image path", task.get("id"))
            continue

        task_annotations = []
        for anno in task.get("annotations", []):
            for result in anno.get("result", []):
                if result.get("type") == "rectanglelabels":
                    value = result.get("value", {})
                    task_annotations.append({
                        "x": value.get("x", 0),
                        "y": value.get("y", 0),
                        "width": value.get("width", 0),
                        "height": value.get("height", 0),
                        "label": value.get("rectanglelabels", ["unknown"])[0],
                    })

        annotations_list.append({
            "image_path": frame_name,
            "annotations": task_annotations,
        })

    logger.info(
        "Loaded %d annotations from %s",
        len(annotations_list),
        labels_file,
    )
    return annotations_list


@dataclass
class DatasetSplit:
    """Train/validation dataset split."""
    
    frames_dir: Path
    annotations: dict[str, Any] | list[dict[str, Any]]
    validation_split: float = 0.8  # 80% train, 20% validation
    
    def __post_init__(self):
        """Split dataset into train and validation sets."""
        if isinstance(self.annotations, dict):
            tasks = self.annotations.get("tasks", [])
        else:
            tasks = self.annotations

        if not 0.0 < self.validation_split < 1.0:
            raise ValueError("validation_split must be between 0.0 and 1.0")
        
        # Deterministic split by frame index
        split_idx = int(len(tasks) * self.validation_split)
        
        self.train_frames = tasks[:split_idx]
        self.val_frames = tasks[split_idx:]
        
        logger.info(
            "Dataset split: %d train, %d validation",
            len(self.train_frames),
            len(self.val_frames),
        )


class MLflowTracker:
    """Local MLflow experiment tracking."""
    
    def __init__(
        self,
        experiment_name: str = "model_training",
        run_dir: Optional[Path] = None,
    ):
        self.experiment_name = experiment_name
        self.run_dir = Path(run_dir or "models/.mlflow")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_run: dict[str, Any] = {}
        
        logger.info("MLflow tracker initialized: %s", self.run_dir)

    def start_run(self, run_name: Optional[str] = None):
        """Context manager for MLflow run."""
        class RunContext:
            def __init__(self, tracker):
                self.tracker = tracker

            def __enter__(self):
                run_id = f"{datetime.now().isoformat()}_{uuid.uuid4().hex[:8]}"
                self.tracker.current_run = {
                    "id": run_id,
                    "name": run_name or f"run_{run_id}",
                    "params": {},
                    "metrics": {},
                    "start_time": time.time(),
                }
                if mlflow is not None:
                    self.mlflow_run = mlflow.start_run(
                        run_name=self.tracker.current_run["name"],
                    )
                    self.mlflow_run.__enter__()
                logger.info("MLflow run started: %s", self.tracker.current_run["id"])
                return self.tracker.current_run

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.tracker.current_run["end_time"] = time.time()
                self.tracker.current_run["duration"] = (
                    self.tracker.current_run["end_time"]
                    - self.tracker.current_run["start_time"]
                )
                if getattr(self, "mlflow_run", None) is not None:
                    self.mlflow_run.__exit__(exc_type, exc_val, exc_tb)
                logger.info("MLflow run completed in %.2f seconds", self.tracker.current_run["duration"])

        return RunContext(self)

    def log_params(self, params: dict[str, Any]) -> None:
        """Log training parameters."""
        self.current_run["params"].update(params)
        if mlflow is not None:
            mlflow.log_params(params)
        logger.info("Logged params: %s", params)

    def log_metric(self, key: str, value: float, step: int = 0) -> None:
        """Log training metric."""
        if key not in self.current_run["metrics"]:
            self.current_run["metrics"][key] = []
        self.current_run["metrics"][key].append({"step": step, "value": value})
        if mlflow is not None:
            mlflow.log_metric(key, value, step=step)
        logger.info("Logged metric: %s = %.4f (step %d)", key, value, step)

    def save_run(self, output_dir: Optional[Path] = None) -> Path:
        """Save run metadata to disk."""
        output_dir = Path(output_dir or self.run_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        run_file = output_dir / f"run_{self.current_run['id']}.json"
        with open(run_file, "w") as f:
            json.dump(self.current_run, f, indent=2, default=str)
        
        logger.info("MLflow run saved to %s", run_file)
        return run_file


class YoloTrainer:
    """Fine-tune YOLOv8-nano model on training dataset."""
    
    def __init__(
        self,
        base_model_path: Path,
        device: str = "cuda",
    ):
        self.base_model_path = Path(base_model_path)
        self.device = device
        self.model = self._load_base_model()
        
        logger.info(
            "YoloTrainer initialized: base_model=%s, device=%s",
            self.base_model_path,
            self.device,
        )

    def _load_base_model(self) -> Any:
        """Load YOLOv8-nano base model."""
        if YOLO is None:
            raise RuntimeError("ultralytics is required for model training")

        if self.base_model_path.exists():
            logger.info("Loading base model from %s", self.base_model_path)
            model = YOLO(str(self.base_model_path))
        else:
            logger.info("Using YOLOv8-nano pretrained model")
            model = YOLO("yolov8n.pt")

        return model

    def train(
        self,
        epochs: int = 10,
        batch_size: int = 16,
        learning_rate: float = 0.001,
        dataset_yaml: Optional[Path] = None,
    ) -> dict[str, Any]:
        """Fine-tune model on training dataset.
        
        AC-1: Training loop with configurable epochs, batch size, learning rate.
        Returns training metrics.
        """
        logger.info(
            "Starting fine-tuning: epochs=%d, batch_size=%d, lr=%f",
            epochs,
            batch_size,
            learning_rate,
        )

        # The command supplies a generated dataset YAML for each recording.
        if dataset_yaml is None:
            dataset_yaml = getattr(self, "dataset_path", None)
        if dataset_yaml is None:
            raise ValueError("dataset_yaml is required for training")

        try:
            results = self.model.train(
                data=str(dataset_yaml),
                epochs=epochs,
                batch=batch_size,
                lr0=learning_rate,
                device=self.device,
                patience=3,
                verbose=True,
            )

            # Extract training metrics
            metrics = {
                "loss": float(_nested_metric(results, "box", "loss")),
                "mAP50": float(_nested_metric(results, "metrics", "mAP50")),
                "precision": float(_nested_metric(results, "metrics", "precision")),
                "recall": float(_nested_metric(results, "metrics", "recall")),
            }

            logger.info("Training completed with metrics: %s", metrics)
            return metrics

        except Exception as exc:
            logger.error("Training failed: %s", exc)
            raise

    def validate(
        self,
        val_dataset_yaml: Path,
    ) -> dict[str, Any]:
        """Validate trained model on validation dataset.
        
        AC-3: Run validation and return mAP score.
        """
        logger.info("Validating model on %s", val_dataset_yaml)

        try:
            results = self.model.val(data=str(val_dataset_yaml))
            
            metrics = {
                "mAP50": float(_nested_metric(results, "box", "map50")),
                "mAP": float(_nested_metric(results, "box", "map")),
            }

            logger.info("Validation metrics: %s", metrics)
            return metrics

        except Exception as exc:
            logger.error("Validation failed: %s", exc)
            raise


def validate_model(
    model: Any,
    val_dataset_path: Path,
    threshold: float = 0.65,
) -> bool | dict[str, Any]:
    """Validate fine-tuned model against validation dataset.
    
    AC-3: Compute mAP score and check against threshold.
    Returns metrics dict if validation passes, False if fails.
    """
    logger.info("Validating model against threshold %.2f", threshold)

    try:
        results = model.val(data=str(val_dataset_path))
        validation_metrics = {
            "mAP50": float(_nested_metric(results, "box", "map50")),
            "threshold": threshold,
        }

        if validation_metrics["mAP50"] >= threshold:
            logger.info("Validation passed: mAP50 %.2f >= %.2f", 
                       validation_metrics["mAP50"], threshold)
            return validation_metrics
        else:
            logger.warning("Validation failed: mAP50 %.2f < %.2f",
                          validation_metrics["mAP50"], threshold)
            return False

    except Exception as exc:
        logger.error("Validation error: %s", exc)
        return False


def _nested_metric(value: Any, *attributes: str) -> Any:
    """Read nested metric attributes while supporting mapping-shaped test results."""
    for attribute in attributes:
        if isinstance(value, dict):
            value = value.get(attribute, 0.0)
        else:
            value = getattr(value, attribute, 0.0)
    return value


def _write_yolo_dataset(split: DatasetSplit, output_dir: Path) -> Path:
    """Materialize a Label Studio split in the directory layout expected by YOLO."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to convert Label Studio annotations") from exc

    labels = sorted({
        annotation.get("label", "unknown")
        for task in split.train_frames + split.val_frames
        for annotation in task.get("annotations", [])
    })
    if not labels:
        raise ValueError("No rectangle annotations found in labels.json")
    class_ids = {label: index for index, label in enumerate(labels)}

    for subset, tasks in (("train", split.train_frames), ("val", split.val_frames)):
        images_dir = output_dir / subset / "images"
        labels_dir = output_dir / subset / "labels"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        for task in tasks:
            source = split.frames_dir / task["image_path"]
            if not source.is_file():
                raise FileNotFoundError(f"Annotated frame not found: {source}")
            destination = images_dir / source.name
            shutil.copy2(source, destination)
            with Image.open(source) as image:
                image_width, image_height = image.size
            rows = []
            for annotation in task.get("annotations", []):
                center_x = (annotation["x"] + annotation["width"] / 2) / 100
                center_y = (annotation["y"] + annotation["height"] / 2) / 100
                rows.append("%d %.6f %.6f %.6f %.6f" % (
                    class_ids[annotation.get("label", "unknown")],
                    center_x,
                    center_y,
                    annotation["width"] / 100,
                    annotation["height"] / 100,
                ))
            (labels_dir / f"{source.stem}.txt").write_text("\n".join(rows))

    dataset_yaml = output_dir / "dataset.yaml"
    dataset_yaml.write_text(
        f"path: {output_dir}\n"
        "train: train/images\n"
        "val: val/images\n"
        f"names: {json.dumps(labels)}\n"
    )
    return dataset_yaml


def deploy_model_atomic(
    new_model_path: Path,
    current_model_path: Path,
    archive_dir: Optional[Path] = None,
) -> Path:
    """Atomically deploy new model by replacing current.pt.
    
    AC-4: Write to temp, validate, os.replace() atomically, archive prior model.
    
    Returns path to archived prior model.
    """
    new_model_path = Path(new_model_path)
    current_model_path = Path(current_model_path)
    archive_dir = Path(archive_dir or current_model_path.parent / "backups")

    logger.info("Preparing atomic deployment: %s → %s", new_model_path, current_model_path)

    # Validate new model exists and is valid
    if not new_model_path.exists():
        raise FileNotFoundError(f"New model not found: {new_model_path}")

    if new_model_path.stat().st_size == 0:
        raise ValueError(f"New model is empty: {new_model_path}")

    # Create archive directory
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Generate archive filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = archive_dir / f"backup_{timestamp}.pt"

    try:
        # If current model exists, archive it
        if current_model_path.exists():
            logger.info("Archiving prior model to %s", archive_path)
            shutil.copy2(current_model_path, archive_path)

        # Atomic swap: os.replace() is atomic at filesystem level
        logger.info("Performing atomic swap")
        os.replace(str(new_model_path), str(current_model_path))

        logger.info("Deployment successful: %s is now current model", current_model_path)
        return archive_path

    except Exception as exc:
        logger.error("Atomic deployment failed: %s", exc)
        # Clean up temp file on failure
        if new_model_path.exists():
            new_model_path.unlink()
        raise


def train_command(
    recording_path: Path,
    epochs: int = 10,
    batch_size: int = 16,
    validation_split: float = 0.8,
    lr: float = 0.001,
    model_root: Path = Path("models"),
    mlflow_dir: Path = Path("models/.mlflow"),
    mAP_threshold: float = 0.65,
    device: str = "cuda",
    model_class: str = "common",
) -> None:
    """Execute full training pipeline: load data → train → validate → deploy.
    
    AC1-AC5: Complete workflow from recording to atomic model deployment.
    """
    logger.info("Starting training command with recording: %s", recording_path)

    recording_path = Path(recording_path)
    model_root = Path(model_root)

    # Step 1: Validate dataset
    try:
        validate_training_dataset(recording_path)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Dataset validation failed: %s", exc)
        raise

    # Step 2: Load annotations
    labels_file = recording_path / "labels.json"
    try:
        annotations = json.loads(labels_file.read_text())
    except (json.JSONDecodeError, FileNotFoundError) as exc:
        logger.error("Failed to load annotations: %s", exc)
        raise

    # Step 3: Parse annotations and split dataset
    try:
        annotations_list = load_label_studio_annotations(labels_file)
        dataset_split = DatasetSplit(
            frames_dir=recording_path / "frames",
            annotations=annotations_list,
            validation_split=validation_split,
        )
    except Exception as exc:
        logger.error("Dataset processing failed: %s", exc)
        raise

    # Step 4: Initialize MLflow tracking
    mlflow_tracker = MLflowTracker(experiment_name="model_training", run_dir=mlflow_dir)

    with mlflow_tracker.start_run():
        # Log training parameters
        mlflow_tracker.log_params({
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": lr,
            "validation_split": validation_split,
            "dataset_frames": len(dataset_split.train_frames),
            "val_frames": len(dataset_split.val_frames),
            "model_class": model_class,
        })

        # Step 5: Initialize trainer
        base_model_path = model_root / model_class / "current.pt"
        try:
            trainer = YoloTrainer(
                base_model_path=base_model_path,
                device=device,
            )
        except RuntimeError as exc:
            logger.error("Trainer initialization failed: %s", exc)
            raise

        # Step 6: Fine-tune model
        logger.info("Starting model fine-tuning")
        try:
            training_start = time.time()
            dataset_dir = Path(tempfile.mkdtemp(prefix="lagent_yolo_dataset_"))
            dataset_yaml = _write_yolo_dataset(dataset_split, dataset_dir)
            metrics = trainer.train(
                epochs=epochs,
                batch_size=batch_size,
                learning_rate=lr,
                dataset_yaml=dataset_yaml,
            )

            # Log training metrics
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    mlflow_tracker.log_metric(key, value)

            training_duration = time.time() - training_start
            logger.info("Training completed in %.2f seconds (%.2f minutes)",
                       training_duration, training_duration / 60)

        except Exception as exc:
            logger.error("Training failed: %s", exc)
            raise

        # Step 7: Validate model
        logger.info("Starting model validation")
        try:
            val_metrics = validate_model(
                model=trainer.model,
                val_dataset_path=dataset_yaml,
                threshold=mAP_threshold,
            )

            if isinstance(val_metrics, dict):
                for key, value in val_metrics.items():
                    if isinstance(value, (int, float)):
                        mlflow_tracker.log_metric(f"val_{key}", value)
                deployment_ready = True
            else:
                logger.warning("Validation did not pass threshold")
                deployment_ready = False

        except Exception as exc:
            logger.error("Validation failed: %s", exc)
            deployment_ready = False

        # Step 8: Deploy model atomically
        if deployment_ready:
            logger.info("Deploying validated model")
            try:
                # Save trained model to temp path
                temp_model_path = Path(tempfile.gettempdir()) / f"yolo_trained_{uuid.uuid4().hex}.pt"
                trainer.model.save(str(temp_model_path))

                # Determine target model path (common or class-specific)
                current_model_path = model_root / model_class / "current.pt"
                current_model_path.parent.mkdir(parents=True, exist_ok=True)

                # Atomic deployment
                archive_path = deploy_model_atomic(
                    new_model_path=temp_model_path,
                    current_model_path=current_model_path,
                    archive_dir=current_model_path.parent / "backups",
                )

                logger.info("✓ Model deployment complete")
                logger.info("  Current model: %s", current_model_path)
                logger.info("  Prior model archived: %s", archive_path)

                mlflow_tracker.log_metric("deployment_successful", 1.0)

            except Exception as exc:
                logger.error("Deployment failed: %s", exc)
                mlflow_tracker.log_metric("deployment_successful", 0.0)
                raise
        else:
            logger.warning("Model validation did not meet threshold; deployment skipped")
            mlflow_tracker.log_metric("deployment_successful", 0.0)

        # Step 9: Save MLflow run metadata
        mlflow_tracker.save_run()

    logger.info("✓ Training pipeline completed successfully")
