"""GPU inference server and YOLO detection adapter."""

from __future__ import annotations

import io
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

from lagent.common import Detection, PerceptionResult
from lagent.common.transport import GPU_ENDPOINT, decode, encode

logger = logging.getLogger(__name__)


def _as_list(value: Any) -> list[Any]:
    return value.tolist() if hasattr(value, "tolist") else list(value)


def _box_iou(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


class YoloInference:
    """Run the common model and the requesting agent's class model."""

    def __init__(
        self,
        models: dict[str, Any] | None = None,
        model_root: str | Path = "models",
        confidence_threshold: float = 0.5,
        thresholds: dict[str, float] | None = None,
        model_loader: Callable[[str], Any] | None = None,
        nms_iou_threshold: float = 0.5,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.thresholds = thresholds or {}
        self.nms_iou_threshold = nms_iou_threshold
        self.models = dict(models or {})
        self.model_root = Path(model_root)
        self._model_loader = model_loader or self._load_yolo_model
        self._load_available_models()

    @staticmethod
    def _load_yolo_model(path: str) -> Any:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("ultralytics is required when YOLO weights are configured") from exc
        return YOLO(path)

    def _load_available_models(self) -> None:
        model_dirs = [self.model_root / "common"]
        model_dirs.extend(path for path in self.model_root.iterdir() if path.is_dir() and path.name != "common") if self.model_root.exists() else None
        for model_dir in model_dirs:
            model_path = model_dir / "current.pt"
            if model_dir.name not in self.models and model_path.exists():
                self.models[model_dir.name] = self._model_loader(str(model_path))

    def _threshold(self, family: str) -> float:
        return self.thresholds.get(family, self.confidence_threshold)

    def _detections_from_result(self, result: Any, family: str) -> list[Detection]:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []
        coordinates = _as_list(getattr(boxes, "xyxy", []))
        confidences = _as_list(getattr(boxes, "conf", []))
        classes = _as_list(getattr(boxes, "cls", []))
        names = getattr(result, "names", {})
        detections = []
        for coordinate, confidence, class_id in zip(coordinates, confidences, classes):
            confidence = float(confidence)
            if confidence < self._threshold(family):
                continue
            class_id = int(class_id)
            class_name = names[class_id] if isinstance(names, (dict, list, tuple)) else str(class_id)
            bbox = tuple(int(value) for value in coordinate[:4])
            detections.append(Detection(class_name=str(class_name), confidence=confidence, bbox_xyxy=bbox))
        return self._nms(detections)

    def _nms(self, detections: list[Detection]) -> list[Detection]:
        kept: list[Detection] = []
        for detection in sorted(detections, key=lambda item: item.confidence, reverse=True):
            if all(_box_iou(detection.bbox_xyxy, existing.bbox_xyxy) < self.nms_iou_threshold for existing in kept):
                kept.append(detection)
        return kept

    def detect(self, frame: Any, agent_id: str) -> PerceptionResult:
        if isinstance(frame, bytes):
            try:
                from PIL import Image

                frame = Image.open(io.BytesIO(frame))
            except (ImportError, OSError):
                pass
        detections: list[Detection] = []
        for family in ("common", agent_id):
            model = self.models.get(family)
            if model is None:
                continue
            outputs = model(frame, conf=self._threshold(family), verbose=False)
            for output in outputs:
                detections.extend(self._detections_from_result(output, family))
        return PerceptionResult(detections=detections)


class GpuInferenceServer:
    def __init__(
        self,
        endpoint: str = GPU_ENDPOINT,
        context=None,
        inference: YoloInference | None = None,
    ):
        import zmq

        self._owns_context = context is None
        self.context = context or zmq.Context()
        self.endpoint = endpoint
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.bind(endpoint)
        self.inference = inference or YoloInference()
        self._stopped = threading.Event()

    def serve(self, once: bool = False) -> None:
        import zmq

        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        try:
            while not self._stopped.is_set():
                for _, _ in poller.poll(50):
                    identity, payload = self.socket.recv_multipart()
                    request = decode(payload)
                    agent_id = request.get("agent_id")
                    if not isinstance(agent_id, str) or not agent_id:
                        logger.warning("Ignoring inference request without a valid agent_id")
                        continue
                    started = time.perf_counter()
                    result = self.inference.detect(request.get("frame_bytes", b""), agent_id)
                    latency_ms = (time.perf_counter() - started) * 1000
                    logger.info("YOLO inference agent=%s latency_ms=%.2f", agent_id, latency_ms)
                    self.socket.send_multipart([identity, encode({
                        "agent_id": agent_id,
                        "result": result.model_dump(mode="json"),
                    })])
                    if once:
                        return
        finally:
            self.socket.close(linger=0)
            if self._owns_context:
                self.context.term()

    def stop(self) -> None:
        self._stopped.set()