"""Non-blocking local recording of frames and manual input events."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Any, Callable

from lagent.agent.capture import Frame

logger = logging.getLogger(__name__)


def _frame_bytes(frame: Any) -> bytes:
    if isinstance(frame, bytes):
        return frame
    if isinstance(frame, (bytearray, memoryview)):
        return bytes(frame)

    try:
        from PIL import Image

        image = frame if isinstance(frame, Image.Image) else Image.fromarray(frame)
        from io import BytesIO

        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
    except (AttributeError, TypeError, ValueError) as exc:
        raise TypeError("frame must be bytes or an image-like object") from exc


class RecordingSession:
    """Archive frames asynchronously while forwarding them to the pipeline."""

    def __init__(self, session_id: str, recordings_root: str | Path = "recordings") -> None:
        if not session_id or Path(session_id).name != session_id or session_id in {".", ".."}:
            raise ValueError("session_id must be a single safe path component")
        self.session_id = session_id
        self.session_dir = Path(recordings_root) / session_id
        self.frames_dir = self.session_dir / "frames"
        self.inputs_path = self.session_dir / "inputs.jsonl"
        self._frame_queue: queue.Queue[tuple[int, Frame] | None] = queue.Queue(maxsize=128)
        self._stop_event = threading.Event()
        self._writer: threading.Thread | None = None
        self._input_file: Any = None
        self._pipeline_callback: Callable[[Frame], None] | None = None
        self._next_frame_number = 0
        self._last_frame_number = 0
        self._input_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._closed = False

    @property
    def frame_count(self) -> int:
        return self._next_frame_number

    def start(self, pipeline_callback: Callable[[Frame], None]) -> None:
        with self._state_lock:
            if self._input_file is not None:
                raise RuntimeError("recording session is already started")
            self.frames_dir.mkdir(parents=True, exist_ok=True)
            try:
                self._input_file = self.inputs_path.open("a", encoding="utf-8")
            except OSError:
                self._input_file = None
                raise
            self._pipeline_callback = pipeline_callback
            self._closed = False
            self._writer = threading.Thread(target=self._write_frames, name=f"recording-{self.session_id}")
            self._writer.start()

    def publish(self, frame: Frame) -> None:
        with self._state_lock:
            pipeline_callback = self._pipeline_callback
            if pipeline_callback is None:
                raise RuntimeError("recording session is not started")
            if self._closed:
                pipeline_callback(frame)
                return
            frame_number = self._next_frame_number
            self._next_frame_number += 1
            self._last_frame_number = frame_number
        pipeline_callback(frame)
        try:
            self._frame_queue.put_nowait((frame_number, frame))
        except queue.Full:
            logger.warning("recording frame queue full; dropping archive frame %s", frame_number)

    def log_input(self, event_type: str, key_or_position: Any, state: str, *, timestamp: float | None = None) -> None:
        with self._input_lock:
            if self._input_file is None or self._closed:
                raise RuntimeError("recording session is not started")
            event = {
                "timestamp": time.time() if timestamp is None else timestamp,
                "event_type": event_type,
                "key_or_position": key_or_position,
                "state": state,
                "frame_number": self._last_frame_number,
            }
            self._input_file.write(json.dumps(event, separators=(",", ":")) + "\n")
            self._input_file.flush()

    def close(self) -> None:
        with self._input_lock:
            with self._state_lock:
                if self._closed:
                    return
                self._closed = True
            if self._writer is not None:
                self._frame_queue.join()
                self._frame_queue.put(None)
                self._writer.join()
                self._writer = None
            if self._input_file is not None:
                self._input_file.flush()
                self._input_file.close()
                self._input_file = None

    def _write_frames(self) -> None:
        while True:
            item = self._frame_queue.get()
            try:
                if item is None:
                    return
                frame_number, frame = item
                try:
                    (self.frames_dir / f"{frame_number:06d}.png").write_bytes(_frame_bytes(frame.frame))
                except (OSError, TypeError, ValueError) as exc:
                    logger.error("failed to archive frame %s for %s: %s", frame_number, self.session_id, exc)
            finally:
                self._frame_queue.task_done()


class PynputInputListener:
    """Translate pynput callbacks into the recording JSONL schema."""

    def __init__(self, recording: RecordingSession) -> None:
        self.recording = recording
        self._keyboard = None
        self._mouse = None
        self._hotkey = None

    def start(self) -> None:
        try:
            from pynput import keyboard, mouse
        except ImportError as exc:  # pragma: no cover - optional platform dependency
            raise RuntimeError("pynput is required for recording input capture") from exc

        self._keyboard = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
        self._mouse = mouse.Listener(on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll)
        self._hotkey = keyboard.GlobalHotKeys({"<ctrl>+<shift>+r": self._stop_recording})
        self._keyboard.start()
        self._mouse.start()
        self._hotkey.start()

    def stop(self) -> None:
        for listener in (self._keyboard, self._mouse, self._hotkey):
            if listener is not None:
                listener.stop()
        self._keyboard = self._mouse = self._hotkey = None

    def _stop_recording(self) -> None:
        self.recording.close()
        self.stop()

    def _on_key_press(self, key: Any) -> None:
        self.recording.log_input("keyboard", self._key_value(key), "pressed")

    def _on_key_release(self, key: Any) -> None:
        self.recording.log_input("keyboard", self._key_value(key), "released")

    def _on_move(self, x: int, y: int) -> None:
        self.recording.log_input("mouse", {"x": x, "y": y}, "moved")

    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        self.recording.log_input("mouse", {"x": x, "y": y, "button": str(button)}, "pressed" if pressed else "released")

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        self.recording.log_input("mouse", {"x": x, "y": y, "dx": dx, "dy": dy}, "scrolled")

    @staticmethod
    def _key_value(key: Any) -> str:
        return getattr(key, "char", None) or str(key)


__all__ = ["PynputInputListener", "RecordingSession"]