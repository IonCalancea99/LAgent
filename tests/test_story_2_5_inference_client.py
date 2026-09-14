import logging
import time

import pytest

from lagent.agent.capture import Frame, FrameQueue
from lagent.agent.inference import InferenceClient, PolicyQueue, frame_to_bytes
from lagent.common import Detection, PerceptionResult
from lagent.common.transport import InferenceResponse


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []
        self.connected = False

    def connect(self):
        self.connected = True

    def request_inference(self, frame_bytes, roi_map, timeout):
        self.requests.append((frame_bytes, roi_map, timeout))
        if self.error:
            raise self.error
        return self.response


def _frame(frame=b"encoded-frame"):
    return Frame("Lineage II", frame, int(time.time() * 1000), "test", time.time())


def test_policy_queue_evicts_oldest_result_without_blocking():
    policy_queue = PolicyQueue(maxsize=2)
    first = PerceptionResult(ocr_values={"hp": "1"})
    second = PerceptionResult(ocr_values={"hp": "2"})
    third = PerceptionResult(ocr_values={"hp": "3"})

    policy_queue.put(first)
    policy_queue.put(second)
    started = time.perf_counter()
    policy_queue.put(third)

    assert (time.perf_counter() - started) < 0.05
    assert [policy_queue.get_nowait(), policy_queue.get_nowait()] == [second, third]


def test_inference_client_pushes_result_and_logs_debug_details(caplog):
    result = PerceptionResult(
        detections=[Detection(class_name="mob", confidence=0.91, bbox_xyxy=(1, 2, 3, 4))],
        ocr_values={"hp": "95%"},
    )
    transport = FakeTransport(InferenceResponse("warlord", result, 4.2))
    frames = FrameQueue(maxsize=2)
    frames.put(_frame())
    policy_queue = PolicyQueue(maxsize=2)
    client = InferenceClient("warlord", frames, policy_queue, transport=transport, debug=True)

    with caplog.at_level(logging.INFO):
        assert client.process_once() is True

    assert policy_queue.get_nowait() == result
    assert transport.connected is False
    assert "PerceptionResult" in caplog.text
    assert "mob" in caplog.text
    assert "95%" in caplog.text
    assert "latency_ms" in caplog.text


def test_inference_client_encodes_extracted_numpy_roi_crops():
    numpy = pytest.importorskip("numpy")
    pytest.importorskip("PIL")

    frame = numpy.zeros((4, 4, 3), dtype=numpy.uint8)
    result = PerceptionResult()
    transport = FakeTransport(InferenceResponse("warlord", result, 1.0))
    frames = FrameQueue(maxsize=2)
    frames.put(_frame(frame))
    policy_queue = PolicyQueue(maxsize=2)
    profile = {"hp": (0, 0, 2, 2)}
    client = InferenceClient("warlord", frames, policy_queue, transport=transport, profile=profile)

    assert client.process_once() is True

    frame_bytes, roi_map, _ = transport.requests[0]
    assert frame_bytes == frame_to_bytes(frame)
    assert isinstance(roi_map["hp"], bytes)


def test_inference_client_drops_timed_out_frame_and_logs_warning(caplog):
    transport = FakeTransport(error=TimeoutError("GPU unavailable"))
    frames = FrameQueue(maxsize=2)
    frames.put(_frame())
    policy_queue = PolicyQueue(maxsize=2)
    client = InferenceClient("warlord", frames, policy_queue, transport=transport)

    with caplog.at_level(logging.WARNING):
        assert client.process_once() is False

    assert policy_queue.empty()
    assert "inference request timed out" in caplog.text