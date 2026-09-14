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
import uuid
from dataclasses import dataclass, field
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
    frame_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    crop_offset: tuple[int, int] = (0, 0)
    screen_offset: tuple[int, int] = (0, 0)
    raw_window_rect: tuple[int, int, int, int] | None = None
    capture_region: tuple[int, int, int, int] | None = None

    @property
    def width(self) -> int:
        """Image width in pixels when the frame payload exposes array or mss.ScreenShot dimensions."""
        shape = getattr(self.frame, "shape", None)
        if shape is not None and len(shape) >= 2:
            return int(shape[1])
        size = getattr(self.frame, "size", None)
        if size is not None and len(size) >= 2:
            return int(size[0])
        return 0

    @property
    def height(self) -> int:
        """Image height in pixels when the frame payload exposes array or mss.ScreenShot dimensions."""
        shape = getattr(self.frame, "shape", None)
        if shape is not None and len(shape) >= 2:
            return int(shape[0])
        size = getattr(self.frame, "size", None)
        if size is not None and len(size) >= 2:
            return int(size[1])
        return 0

    def frame_to_screen(self, x: float, y: float) -> tuple[float, float]:
        """Convert frame-local pixel coordinate to global screen coordinate."""
        return x + self.screen_offset[0], y + self.screen_offset[1]

    def screen_to_frame(self, x: float, y: float) -> tuple[float, float]:
        """Convert global screen coordinate to frame-local pixel coordinate."""
        return x - self.screen_offset[0], y - self.screen_offset[1]

    def frame_to_client(self, x: float, y: float) -> tuple[float, float]:
        """Convert frame-local pixel coordinate to window client area coordinate."""
        return x + self.crop_offset[0], y + self.crop_offset[1]

    def client_to_frame(self, x: float, y: float) -> tuple[float, float]:
        """Convert window client area coordinate to frame-local pixel coordinate."""
        return x - self.crop_offset[0], y - self.crop_offset[1]


class FrameQueue(queue.Queue):
    """Bounded queue that evicts the oldest frame instead of blocking."""

    def __init__(self, maxsize: int = 0) -> None:
        super().__init__(maxsize=maxsize)
        self.dropped_frames = 0

    def _put_latest(self, frame: Frame) -> None:
        with self.not_full:
            while self.maxsize > 0 and self._qsize() >= self.maxsize:
                self._get()
                self.unfinished_tasks -= 1
                self.dropped_frames += 1
            self._put(frame)
            self.unfinished_tasks += 1
            self.not_empty.notify()

    @property
    def queue_state(self) -> dict[str, int]:
        return {
            "size": self.qsize(),
            "maxsize": self.maxsize,
            "dropped_frames": self.dropped_frames,
        }

    def put(self, item: Frame, block: bool = True, timeout: float | None = None) -> None:
        del block, timeout
        self._put_latest(item)

    def put_nowait(self, item: Frame) -> None:
        self._put_latest(item)

    def put_frame(self, frame: Frame) -> None:
        self._put_latest(frame)


def _ensure_dpi_awareness() -> None:
    """Ensure process is DPI-aware so Windows API coordinates match physical pixel resolution."""
    try:
        import ctypes

        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return

        try:
            windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            try:
                windll.shcore.SetProcessDpiAwareness(2)
            except (AttributeError, OSError):
                windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _resolve_window_region(window_title: str) -> tuple[int, int, int, int]:
    """Resolve a window title to the screen region consumed by dxcam."""

    try:
        import win32gui  # type: ignore
    except ImportError as exc:  # pragma: no cover - platform dependency
        raise RuntimeError("window resolution requires Windows") from exc

    _ensure_dpi_awareness()

    handle = win32gui.FindWindow(None, window_title)
    if not handle:
        raise RuntimeError(f"window not found: {window_title}")

    client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(handle)
    left, top = win32gui.ClientToScreen(handle, (client_left, client_top))
    right, bottom = win32gui.ClientToScreen(handle, (client_right, client_bottom))
    if right <= left or bottom <= top:
        raise RuntimeError(f"window has no capture region: {window_title}")
    return left, top, right, bottom


def _resolve_window_monitor_info(handle: Any) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return ((screen_width, screen_height), (monitor_left, monitor_top)) for a window handle."""
    try:
        import win32api  # type: ignore
        import win32con  # type: ignore

        hmonitor = win32api.MonitorFromWindow(handle, getattr(win32con, "MONITOR_DEFAULTTONEAREST", 2))
        if hmonitor:
            info = win32api.GetMonitorInfo(hmonitor)
            m_rect = info.get("Monitor", (0, 0, 0, 0))
            m_w = m_rect[2] - m_rect[0]
            m_h = m_rect[3] - m_rect[1]
            if m_w > 0 and m_h > 0:
                return (m_w, m_h), (m_rect[0], m_rect[1])
    except Exception:
        pass

    try:
        import win32api  # type: ignore

        sm_w = win32api.GetSystemMetrics(0)
        sm_h = win32api.GetSystemMetrics(1)
        if sm_w > 0 and sm_h > 0:
            return (sm_w, sm_h), (0, 0)
    except Exception:
        pass

    return (0, 0), (0, 0)


def _get_dxcam_output_dimensions(backend: Any = None, handle: Any = None) -> tuple[int, int]:
    """Dynamically detect DXCam output display dimensions."""
    # 1. From DXCam backend attributes if present
    if backend is not None:
        width = getattr(backend, "width", None)
        height = getattr(backend, "height", None)
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return width, height
        output = getattr(backend, "output", None)
        if output is not None:
            o_w = getattr(output, "width", None) or getattr(output, "resolution", (None, None))[0]
            o_h = getattr(output, "height", None) or getattr(output, "resolution", (None, None))[1]
            if isinstance(o_w, int) and isinstance(o_h, int) and o_w > 0 and o_h > 0:
                return int(o_w), int(o_h)

    # 2. From monitor associated with the window
    if handle:
        (m_w, m_h), _ = _resolve_window_monitor_info(handle)
        if m_w > 0 and m_h > 0:
            return m_w, m_h

    # 3. From system metrics (primary display)
    try:
        import win32api  # type: ignore

        sm_w = win32api.GetSystemMetrics(0)
        sm_h = win32api.GetSystemMetrics(1)
        if sm_w > 0 and sm_h > 0:
            return sm_w, sm_h
    except Exception:
        pass

    # 4. Fallback default for headless or mocked test environments
    return 1920, 1080


def normalize_capture_region(
    window_rect: tuple[int, int, int, int],
    screen_size: tuple[int, int],
    monitor_origin: tuple[int, int] = (0, 0),
) -> tuple[int, int, int, int]:
    """Calculate the valid intersection between a window rectangle and display output bounds.

    Clamps negative coordinates and out-of-bound edges so the resulting region
    strictly satisfies:
        0 <= left < right <= screen_width
        0 <= top < bottom <= screen_height

    Args:
        window_rect: (left, top, right, bottom) window bounds.
        screen_size: (width, height) output display dimensions.
        monitor_origin: (m_left, m_top) top-left origin of display in virtual space.

    Returns:
        (norm_left, norm_top, norm_right, norm_bottom) in display-relative coordinates.

    Raises:
        RuntimeError: if the window is invalid or completely outside the display bounds.
        ValueError: if screen_size has non-positive dimensions.
    """
    screen_width, screen_height = screen_size
    if screen_width <= 0 or screen_height <= 0:
        raise ValueError(f"invalid screen dimensions: {screen_size}")

    w_left, w_top, w_right, w_bottom = window_rect
    if w_right <= w_left or w_bottom <= w_top:
        raise RuntimeError(f"window has invalid or empty rect: {window_rect}")

    m_left, m_top = monitor_origin

    # Translate window coords to display-local space
    rel_left = w_left - m_left
    rel_top = w_top - m_top
    rel_right = w_right - m_left
    rel_bottom = w_bottom - m_top

    # Calculate intersection with [0, 0, screen_width, screen_height]
    norm_left = max(0, min(rel_left, screen_width))
    norm_top = max(0, min(rel_top, screen_height))
    norm_right = max(0, min(rel_right, screen_width))
    norm_bottom = max(0, min(rel_bottom, screen_height))

    if norm_right <= norm_left or norm_bottom <= norm_top:
        raise RuntimeError(
            f"window region {window_rect} is completely outside display bounds "
            f"({screen_width}x{screen_height} at origin {monitor_origin})"
        )

    return norm_left, norm_top, norm_right, norm_bottom


def _validate_dxcam_region(
    region: tuple[int, int, int, int],
    screen_size: tuple[int, int] | None = None,
) -> None:
    """Ensure the normalized capture region strictly satisfies DXCam output constraints.

    Requires:
        0 <= left < right <= screen_width
        0 <= top < bottom <= screen_height
    """
    if screen_size is None:
        screen_size = _get_dxcam_output_dimensions()

    screen_width, screen_height = screen_size
    left, top, right, bottom = region
    if not (0 <= left < right <= screen_width and 0 <= top < bottom <= screen_height):
        raise RuntimeError(
            f"window region {region} exceeds dxcam output {screen_width}x{screen_height}"
        )


def _mss_monitor_for_window(window_title: str) -> dict[str, int]:
    """Translate absolute client bounds to the monitor mapping required by mss."""

    left, top, right, bottom = _resolve_window_region(window_title)
    return {"left": left, "top": top, "width": right - left, "height": bottom - top}


def _load_dxcam_backend(window_title: str, fps: int) -> Any:
    """Create the preferred dxcam backend for a particular window."""

    try:
        import dxcam  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised via fallback path in tests
        raise RuntimeError("dxcam import failed") from exc

    _ensure_dpi_awareness()

    backend = dxcam.create()
    if backend is None:
        raise RuntimeError("dxcam backend creation failed")

    raw_region = _resolve_window_region(window_title)

    handle = None
    monitor_origin = (0, 0)
    try:
        import win32gui  # type: ignore

        handle = win32gui.FindWindow(None, window_title)
        if handle:
            _, monitor_origin = _resolve_window_monitor_info(handle)
    except Exception:
        pass

    screen_size = _get_dxcam_output_dimensions(backend=backend, handle=handle)
    normalized_region = normalize_capture_region(
        raw_region, screen_size=screen_size, monitor_origin=monitor_origin
    )
    try:
        _validate_dxcam_region(normalized_region, screen_size)
    except TypeError:
        _validate_dxcam_region(normalized_region)

    logger.debug(
        "%s window rect: %s\nDXCam output size: %s\nNormalized capture region: %s",
        window_title,
        raw_region,
        screen_size,
        normalized_region,
    )

    crop_x = normalized_region[0] - (raw_region[0] - monitor_origin[0])
    crop_y = normalized_region[1] - (raw_region[1] - monitor_origin[1])
    screen_origin_x = normalized_region[0] + monitor_origin[0]
    screen_origin_y = normalized_region[1] + monitor_origin[1]

    backend.window_region = normalized_region
    backend.raw_window_rect = raw_region
    backend.crop_offset = (crop_x, crop_y)
    backend.screen_offset = (screen_origin_x, screen_origin_y)
    backend.screen_size = screen_size
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
        on_frame: Any | None = None,
    ) -> None:
        super().__init__(daemon=True, name=f"capture-{window_title or 'window'}")
        self.window_title = window_title
        self.fps = fps
        self.logger = log or logger
        self.on_frame = on_frame
        self.frame_queue: FrameQueue = FrameQueue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self.backend_name: str | None = None
        self.backend: Any = None
        self._mss_monitor: dict[str, int] | None = None
        self._capture_region: tuple[int, int, int, int] | None = None
        self._window_rect: tuple[int, int, int, int] | None = None
        self._crop_offset: tuple[int, int] = (0, 0)
        self._screen_offset: tuple[int, int] = (0, 0)

    def stop(self) -> None:
        self._stop_event.set()

    def _ensure_backend(self) -> None:
        # dxcam/mss hold thread-local OS handles, so create them on the thread that grabs frames.
        if self.backend is not None:
            return
        self.backend_name, self.backend = resolve_capture_backend(self.window_title, self.fps, self.logger)
        if self.backend_name == "dxcam":
            self._capture_region = getattr(self.backend, "window_region", None)
            self._window_rect = getattr(self.backend, "raw_window_rect", self._capture_region)
            self._crop_offset = getattr(self.backend, "crop_offset", (0, 0))
            self._screen_offset = getattr(self.backend, "screen_offset", (0, 0))
        elif self.backend_name == "mss":
            self._mss_monitor = _mss_monitor_for_window(self.window_title)
            self._capture_region = (
                self._mss_monitor["left"],
                self._mss_monitor["top"],
                self._mss_monitor["left"] + self._mss_monitor["width"],
                self._mss_monitor["top"] + self._mss_monitor["height"],
            )
            self._window_rect = self._capture_region
            self._crop_offset = (0, 0)
            self._screen_offset = (self._mss_monitor["left"], self._mss_monitor["top"])

    def _capture_once(self) -> Frame | None:
        self._ensure_backend()
        timestamp = time.time()
        captured_at_ms = int(time.time_ns() / 1_000_000)

        try:
            if self.backend_name == "dxcam":
                region = getattr(self.backend, "window_region", None)
                raw_frame = self.backend.grab(region=region) if hasattr(self.backend, "grab") else self.backend
            else:
                raw_frame = self.backend.grab(self._mss_monitor)
        except Exception as exc:  # noqa: BLE001 - capture failures are logged and retry later.
            self.logger.warning("capture failed for %s: %s", self.window_title, exc)
            return None

        if raw_frame is None:
            return None

        return Frame(
            window_title=self.window_title,
            frame=raw_frame,
            captured_at_ms=captured_at_ms,
            source=self.backend_name or "unknown",
            captured_at=timestamp,
            crop_offset=self._crop_offset,
            screen_offset=self._screen_offset,
            raw_window_rect=self._window_rect,
            capture_region=self._capture_region,
        )

    def run(self) -> None:
        interval = 1.0 / max(self.fps, 1)

        while not self._stop_event.is_set():
            started_at = time.monotonic()
            frame = self._capture_once()
            if frame is not None:
                if self.on_frame is None:
                    self.frame_queue.put_frame(frame)
                else:
                    self.on_frame(frame)

            elapsed = time.monotonic() - started_at
            remaining = max(0.0, interval - elapsed)
            if self._stop_event.wait(timeout=remaining):
                break


__all__ = ["CaptureThread", "Frame", "FrameQueue", "normalize_capture_region", "resolve_capture_backend"]
