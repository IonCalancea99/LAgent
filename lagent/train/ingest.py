"""Download videos and turn them into Recording Mode-compatible frames."""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _positive_fps(value: str) -> float:
    fps = float(value)
    if fps <= 0:
        raise argparse.ArgumentTypeError("fps must be greater than zero")
    return fps


def parse_ingest_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lagent.train ingest",
        description="Download a public video and extract training frames",
    )
    parser.add_argument("--url", required=True, help="Public video URL supported by yt-dlp")
    parser.add_argument("--fps", required=True, type=_positive_fps, help="Frames to extract per second")
    parser.add_argument("--output-dir", type=Path, default=Path("recordings"))
    return parser.parse_args(args)


def validate_video_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be an absolute HTTP or HTTPS video URL")


@dataclass(frozen=True)
class IngestResult:
    recording_dir: Path
    frame_count: int
    source_fps: float


def _download_video(url: str, temp_dir: Path) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is required for video ingestion; install the project dependencies") from exc

    output_template = str(temp_dir / "video.%(ext)s")
    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([url])
    except Exception as exc:
        raise RuntimeError(f"video download failed for {url}: {exc}") from exc

    candidates = sorted(path for path in temp_dir.glob("video.*") if path.is_file())
    if not candidates:
        raise RuntimeError("video download failed: yt-dlp did not produce a video file")
    return candidates[0]


def _new_recording_dir(output_dir: Path) -> Path:
    session_id = datetime.now(timezone.utc).strftime("ingest-%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    recording_dir = output_dir / session_id
    (recording_dir / "frames").mkdir(parents=True, exist_ok=False)
    return recording_dir


def _extract_frames(video_path: Path, frames_dir: Path, requested_fps: float) -> tuple[int, float]:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for video frame extraction") from exc

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"video extraction failed: OpenCV could not open {video_path.name}")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if source_fps <= 0 or frame_total <= 0:
        capture.release()
        raise RuntimeError("video extraction failed: video has no usable frame rate or frame count")

    duration = frame_total / source_fps
    expected_count = int(duration * requested_fps + 0.999999)
    frame_count = 0
    try:
        for output_index in range(expected_count):
            timestamp = output_index / requested_fps
            if timestamp >= duration:
                break
            source_index = min(int(timestamp * source_fps), frame_total - 1)
            capture.set(cv2.CAP_PROP_POS_FRAMES, source_index)
            success, frame = capture.read()
            if not success:
                logger.warning("stopping extraction at frame %d: OpenCV read failed", output_index)
                break
            frame_path = frames_dir / f"{frame_count:06d}.png"
            if not cv2.imwrite(str(frame_path), frame):
                raise RuntimeError(f"video extraction failed: could not write {frame_path.name}")
            frame_count += 1
            if frame_count % 100 == 0:
                logger.info("Extracted %d frames", frame_count)
    finally:
        capture.release()
    if frame_count != expected_count:
        raise RuntimeError(
            f"video extraction failed: expected {expected_count} frames at {requested_fps:g} FPS, "
            f"extracted {frame_count}"
        )
    return frame_count, source_fps


def ingest_video(url: str, fps: float, *, output_dir: Path = Path("recordings")) -> IngestResult:
    validate_video_url(url)
    if fps <= 0:
        raise ValueError("fps must be greater than zero")

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".ingest-") as temp_name:
            video_path = _download_video(url, Path(temp_name))
            recording_dir = _new_recording_dir(output_dir)
            frame_count, source_fps = _extract_frames(video_path, recording_dir / "frames", fps)

        (recording_dir / "inputs.jsonl").write_text("", encoding="utf-8")
        metadata: dict[str, Any] = {
            "source_url": url,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "fps": fps,
            "source_fps": source_fps,
            "frame_count": frame_count,
        }
        (recording_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        logger.info("Ingestion complete: %d frames written to %s", frame_count, recording_dir)
        return IngestResult(recording_dir, frame_count, source_fps)
    except Exception:
        logger.error("Ingestion failed for %s", url)
        raise


def ingest_command(url: str, fps: float, output_dir: Path) -> IngestResult:
    return ingest_video(url, fps, output_dir=output_dir)