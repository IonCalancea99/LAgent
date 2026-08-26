"""lagent.train CLI entry point — invoke subcommands for training pipeline tasks.

Usage:
    python -m lagent.train <subcommand> [options]

Available subcommands:
    prelabel — Apply YOLO models to recorded frames and generate Label Studio annotations
"""

from __future__ import annotations

import argparse
import sys


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
    
    if args.subcommand == "prelabel":
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
