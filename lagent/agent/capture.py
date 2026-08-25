"""Screen capture support for the perception pipeline.

Story 2.1 implements a capture loop that prefers dxcam and falls back to mss
when dxcam is unavailable. The capture thread never blocks downstream stages:
all bounded queues use oldest-frame eviction when full.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Frame:
    """Single captured frame with a capture timestamp for pipeline latency."""

    window_title: str
    frame: Any
    captured_at_ms: int
    source: str
    captured_at: float
    roi_map: dict[str, Any] | None = None

    @property
    def width(self) -> int:
        """Image width in pixels when the frame payload exposes array dimensions."""
        shape = getattr(self.frame, "shape", None)
        if shape is not None and len(shape) >= 2:
            return int(shape[1])
        return 0

    @property
    def height(self) -> int:
        """Image height in pixels when the frame payload exposes array dimensions."""
        shape = getattr(self.frame, "shape", None)
        if shape is not None and len(shape) >= 2:
            return int(shape[0])
        return 0


class FrameQueue(queue.Queue):
    """Bounded queue that evicts the oldest frame instead of blocking."""

    def _put_latest(self, frame: Frame) -> None:
        with self.not_full:
            while self.maxsize > 0 and self._qsize() >= self.maxsize:
                self._get()
                self.unfinished_tasks -= 1
            self._put(frame)
            self.unfinished_tasks += 1
            self.not_empty.notify()

    def put(self, item: Frame, block: bool = True, timeout: float | None = None) -> None:
        del block, timeout
        self._put_latest(item)

    def put_nowait(self, item: Frame) -> None:
        self._put_latest(item)

    def put_frame(self, frame: Frame) -> None:
        self._put_latest(frame)


def _resolve_window_region(window_title: str) -> tuple[int, int, int, int]:
    """Resolve a window title to the screen region consumed by dxcam."""

    try:
        import win32gui  # type: ignore
    except ImportError as exc:  # pragma: no cover - platform dependency
        raise RuntimeError("window resolution requires Windows") from exc

    handle = win32gui.FindWindow(None, window_title)
    if not handle:
        raise RuntimeError(f"window not found: {window_title}")

    left, top, right, bottom = win32gui.GetWindowRect(handle)
    if right <= left or bottom <= top:
        raise RuntimeError(f"window has no capture region: {window_title}")
    return left, top, right, bottom


def _load_dxcam_backend(window_title: str, fps: int) -> Any:
    """Create the preferred dxcam backend for a particular window."""

    try:
        import dxcam  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised via fallback path in tests
        raise RuntimeError("dxcam import failed") from exc

    backend = dxcam.create()
    if backend is None:
        raise RuntimeError("dxcam backend creation failed")
    backend.window_region = _resolve_window_region(window_title)
    backend.capture_fps = fps
    return backend


def _load_mss_backend() -> Any:
    """Create the mss backend used as the fallback capture path."""

    try:
        import mss  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised via fallback path in tests
        raise RuntimeError("mss import failed") from exc

    return mss.mss()


def resolve_capture_backend(window_title: str, fps: int = 10, log: logging.Logger | None = None):
    """Resolve the capture backend, preferring dxcam and falling back to mss."""

    logger_instance = log or logging.getLogger(__name__)
    try:
        backend = _load_dxcam_backend(window_title, fps)
        return "dxcam", backend
    except Exception as exc:  # noqa: BLE001 - fallback is expected for missing platform libraries.
        logger_instance.info("dxcam unavailable for %s (%s); fallback to mss", window_title, exc)
        return "mss", _load_mss_backend()


class CaptureThread(threading.Thread):
    """Periodically capture frames from a game window and push them to a queue."""

    def __init__(
        self,
        window_title: str,
        fps: int = 10,
        max_queue_size: int = 2,
        log: logging.Logger | None = None,
    ) -> None:
        super().__init__(daemon=True, name=f"capture-{window_title or 'window'}")
        self.window_title = window_title
        self.fps = fps
        self.logger = log or logger
        self.frame_queue: FrameQueue = FrameQueue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self.backend_name, self.backend = resolve_capture_backend(window_title, fps, self.logger)

    def stop(self) -> None:
        self._stop_event.set()

    def _capture_once(self) -> Frame | None:
        timestamp = time.time()
        captured_at_ms = int(time.time_ns() / 1_000_000)

        try:
            if self.backend_name == "dxcam":
                region = getattr(self.backend, "window_region", None)
                raw_frame = self.backend.grab(region=region) if hasattr(self.backend, "grab") else self.backend
            else:
                raw_frame = self.backend.grab({"title": self.window_title})
        except Exception as exc:  # noqa: BLE001 - capture failures are logged and retry later.
            self.logger.warning("capture failed for %s: %s", self.window_title, exc)
            return None

        if raw_frame is None:
            return None

        return Frame(
            window_title=self.window_title,
            frame=raw_frame,
            captured_at_ms=captured_at_ms,
            source=self.backend_name,
            captured_at=timestamp,
        )

    def run(self) -> None:
        interval = 1.0 / max(self.fps, 1)

        while not self._stop_event.is_set():
            started_at = time.monotonic()
            frame = self._capture_once()
            if frame is not None:
                self.frame_queue.put_frame(frame)

            elapsed = time.monotonic() - started_at
            remaining = max(0.0, interval - elapsed)
            if self._stop_event.wait(timeout=remaining):
                break


__all__ = ["CaptureThread", "Frame", "FrameQueue", "resolve_capture_backend"]
