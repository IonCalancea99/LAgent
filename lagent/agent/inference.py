"""Agent-side frame to perception-result pipeline."""

from __future__ import annotations

import io
import logging
import queue
import threading
import time
from typing import Any

from lagent.agent.capture import Frame, FrameQueue
from lagent.agent.profile import extract_roi_map
from lagent.common import PerceptionResult
from lagent.common.transport import AgentTransport, InferenceResponse

logger = logging.getLogger(__name__)


class PolicyQueue(queue.Queue):
    """Bounded result queue that evicts the oldest result when full."""

    def _put_latest(self, result: PerceptionResult) -> None:
        with self.not_full:
            if self.maxsize > 0 and self._qsize() >= self.maxsize:
                self._get()
                self.unfinished_tasks = max(0, self.unfinished_tasks - 1)
            self._put(result)
            self.unfinished_tasks += 1
            self.not_empty.notify()

    def put(
        self,
        item: PerceptionResult,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        del block, timeout
        self._put_latest(item)

    def put_nowait(self, item: PerceptionResult) -> None:
        self._put_latest(item)


def frame_to_bytes(frame: Any) -> bytes:
    """Encode a captured frame as PNG bytes for the GPU transport."""

    if isinstance(frame, bytes):
        return frame
    if isinstance(frame, (bytearray, memoryview)):
        return bytes(frame)

    try:
        from PIL import Image

        if isinstance(frame, Image.Image):
            image = frame
        elif hasattr(frame, "shape"):
            image = Image.fromarray(frame)
        else:
            raise TypeError
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
    except (ImportError, TypeError, ValueError, OSError) as exc:
        raise TypeError("frame must be bytes or an image-like object") from exc


class InferenceClient(threading.Thread):
    """Pop captured frames, request inference, and publish policy results."""

    def __init__(
        self,
        agent_id: str,
        frame_queue: FrameQueue,
        policy_queue: PolicyQueue,
        *,
        endpoint: str | None = None,
        transport: AgentTransport | Any | None = None,
        profile: Any | None = None,
        timeout: float = 0.05,
        debug: bool = False,
        log: logging.Logger | None = None,
    ) -> None:
        super().__init__(daemon=True, name=f"inference-{agent_id}")
        self.agent_id = agent_id
        self.frame_queue = frame_queue
        self.policy_queue = policy_queue
        self.transport = transport or AgentTransport(agent_id, endpoint=endpoint) if endpoint else transport
        if self.transport is None:
            self.transport = AgentTransport(agent_id)
        self.profile = profile
        self.timeout = timeout
        self.debug = debug
        self.logger = log or logger
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def _roi_map(self, frame: Frame) -> dict[str, Any]:
        if frame.roi_map is not None:
            return frame.roi_map
        if self.profile is None:
            return {}
        return extract_roi_map(frame.frame, self.profile, width=frame.width, height=frame.height)

    def process_once(self) -> bool:
        """Process one available frame; return whether a result was published."""

        try:
            captured = self.frame_queue.get_nowait()
        except queue.Empty:
            if self.debug:
                self.logger.debug("inference tick skipped: no frame available")
            return False

        try:
            started = time.perf_counter()
            frame_bytes = frame_to_bytes(captured.frame)
            roi_map = self._roi_map(captured)
            send_latency_ms = max(0.0, (time.time() - captured.captured_at) * 1000)
            response: InferenceResponse = self.transport.request_inference(
                frame_bytes, roi_map, timeout=self.timeout
            )
            received_at = time.perf_counter()
            self.policy_queue.put_nowait(response.result)
            push_latency_ms = (time.perf_counter() - received_at) * 1000
            if self.debug:
                self.logger.info(
                    "PerceptionResult detections=%s ocr_values=%s "
                    "capture_to_send_ms=%.2f gpu_latency_ms=%.2f recv_to_push_ms=%.2f",
                    [
                        {
                            "class": detection.class_name,
                            "confidence": detection.confidence,
                            "bbox": detection.bbox_xyxy,
                        }
                        for detection in response.result.detections
                    ],
                    response.result.ocr_values,
                    send_latency_ms,
                    response.latency_ms,
                    push_latency_ms,
                )
            return True
        except TimeoutError as exc:
            self.logger.warning("inference request timed out; dropping frame: %s", exc)
            return False
        except (TypeError, ValueError, OSError) as exc:
            self.logger.warning("inference frame dropped: %s", exc)
            return False
        finally:
            self.frame_queue.task_done()

    def run(self) -> None:
        self.transport.connect()
        try:
            while not self._stop_event.is_set():
                self.process_once()
                self._stop_event.wait(0.001)
        finally:
            self.transport.close()


__all__ = ["InferenceClient", "PolicyQueue", "frame_to_bytes"]