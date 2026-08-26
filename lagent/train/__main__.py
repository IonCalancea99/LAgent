"""lagent.train CLI entry point — invoke subcommands for training pipeline tasks.

Usage:
    python -m lagent.train <subcommand> [options]

Available subcommands:
    train — Fine-tune YOLO model from corrected Label Studio annotations and deploy atomically
    prelabel — Apply YOLO models to recorded frames and generate Label Studio annotations
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)


def main() -> None:
    """Parse and dispatch training subcommands."""
    parser = argparse.ArgumentParser(
        prog="python -m lagent.train",
        description="LAgent training pipeline CLI",
    )

    subparsers = parser.add_subparsers(
        dest="subcommand",
        required=True,
        help="Training subcommand to execute",
    )

    # Training subcommand (Story 7.3)
    train_parser = subparsers.add_parser(
        "train",
        help="Fine-tune YOLO model from corrected Label Studio annotations and deploy atomically",
    )
    train_parser.add_argument(
        "--recording",
        type=Path,
        required=True,
        help="Path to recording directory containing frames/ and labels.json",
    )
    train_parser.add_argument(
        "--epochs",
        type=int,
        default=10,
        help="Number of training epochs (default: 10)",
    )
    train_parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Batch size for training (default: 16)",
    )
    train_parser.add_argument(
        "--validation-split",
        type=float,
        default=0.8,
        help="Fraction of dataset for training vs validation (default: 0.8)",
    )
    train_parser.add_argument(
        "--lr",
        type=float,
        default=0.001,
        help="Learning rate (default: 0.001)",
    )
    train_parser.add_argument(
        "--model-root",
        type=Path,
        default=Path("models"),
        help="Root directory for models (default: models)",
    )
    train_parser.add_argument(
        "--mlflow-dir",
        type=Path,
        default=Path("models/.mlflow"),
        help="MLflow tracking directory (default: models/.mlflow)",
    )
    train_parser.add_argument(
        "--mAP-threshold",
        type=float,
        default=0.65,
        help="Minimum mAP50 threshold for deployment (default: 0.65)",
    )
    train_parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="Device for training: cuda or cpu (default: cuda)",
    )
    
    train_parser.add_argument(
        "--model-class",
        type=str,
        default="common",
        help="Model class directory to train and deploy (default: common)",
    )
    # Prelabeling subcommand
    prelabel_parser = subparsers.add_parser(
        "prelabel",
        help="Apply YOLO models to recorded frames and generate Label Studio annotations",
    )
    prelabel_parser.add_argument(
        "--recording",
        type=str,
        required=True,
        help="Path to recording directory containing frames/ subdirectory",
    )
    prelabel_parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for frame inference (default: 32)",
    )
    prelabel_parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Confidence threshold for detections (default: 0.5)",
    )
    prelabel_parser.add_argument(
        "--model-root",
        type=str,
        default="models",
        help="Root directory for YOLO models (default: models)",
    )
    
    args = parser.parse_args()
    
    if args.subcommand == "train":
        from lagent.train.train import train_command
        try:
            train_command(
                recording_path=args.recording,
                epochs=args.epochs,
                batch_size=args.batch_size,
                validation_split=args.validation_split,
                lr=args.lr,
                model_root=args.model_root,
                mlflow_dir=args.mlflow_dir,
                mAP_threshold=args.mAP_threshold,
                device=args.device,
                model_class=args.model_class,
            )
        except Exception as e:
            logging.error("Training command failed: %s", e)
            sys.exit(1)

    elif args.subcommand == "prelabel":
        from lagent.train.prelabel import prelabel_command
        # Reconstruct args for prelabel_command by re-parsing just the prelabel args
        prelabel_args = [
            "--recording", args.recording,
            "--batch-size", str(args.batch_size),
            "--confidence-threshold", str(args.confidence_threshold),
            "--model-root", args.model_root,
        ]
        sys.argv = ["lagent.train", "prelabel"] + prelabel_args
        prelabel_command()


if __name__ == "__main__":
    main()
