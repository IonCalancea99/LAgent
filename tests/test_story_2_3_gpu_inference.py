import threading
import time

from lagent.common.transport import AgentTransport, make_endpoint
from lagent.gpu_server.server import GpuInferenceServer, YoloInference


class FakeBoxes:
    def __init__(self, rows):
        self.xyxy = [row[0] for row in rows]
        self.conf = [row[1] for row in rows]
        self.cls = [row[2] for row in rows]


class FakeResult:
    def __init__(self, rows, names):
        self.boxes = FakeBoxes(rows)
        self.names = names


class FakeModel:
    def __init__(self, rows, names):
        self.rows = rows
        self.names = names
        self.calls = []

    def __call__(self, frame, **kwargs):
        self.calls.append((frame, kwargs))
        return [FakeResult(self.rows, self.names)]


def test_yolo_inference_merges_models_and_filters_confidence():
    common = FakeModel([(([1.2, 2.8, 30.4, 40.9]), 0.9, 0)], {0: "mob"})
    class_model = FakeModel(
        [(([5, 6, 7, 8]), 0.4, 0), (([9, 10, 11, 12]), 0.8, 1)],
        {0: "ignored", 1: "warlord_skill"},
    )
    inference = YoloInference(
        models={"common": common, "warlord": class_model},
        confidence_threshold=0.5,
    )

    result = inference.detect("frame-bytes", agent_id="warlord")

    assert [d.class_name for d in result.detections] == ["mob", "warlord_skill"]
    assert [d.bbox_xyxy for d in result.detections] == [(1, 2, 30, 40), (9, 10, 11, 12)]
    assert all(model.calls[0][0] == "frame-bytes" for model in (common, class_model))


def test_server_routes_each_inference_result_to_its_agent():
    common = FakeModel([(([1, 2, 3, 4]), 0.9, 0)], {0: "common"})
    warlord = FakeModel([(([5, 6, 7, 8]), 0.9, 0)], {0: "warlord"})
    prophet = FakeModel([(([9, 10, 11, 12]), 0.9, 0)], {0: "prophet"})
    server_endpoint = make_endpoint()
    server = GpuInferenceServer(
        server_endpoint,
        inference=YoloInference(
            models={"common": common, "warlord": warlord, "prophet": prophet},
            confidence_threshold=0.5,
        ),
    )
    thread = threading.Thread(target=server.serve, daemon=True)
    thread.start()
    time.sleep(0.03)
    clients = [AgentTransport("warlord", server_endpoint), AgentTransport("prophet", server_endpoint)]
    try:
        for client in clients:
            client.connect()
        results = [None, None]

        def request(index):
            results[index] = clients[index].request_inference(b"frame", {}, timeout=0.1)

        request_threads = [threading.Thread(target=request, args=(index,)) for index in range(2)]
        started = time.perf_counter()
        for request_thread in request_threads:
            request_thread.start()
        for request_thread in request_threads:
            request_thread.join(timeout=1)
        elapsed_ms = (time.perf_counter() - started) * 1000

        assert all(result is not None for result in results)
        assert elapsed_ms < 100
        assert [result.agent_id for result in results] == ["warlord", "prophet"]
        assert [result.result.detections[1].class_name for result in results] == ["warlord", "prophet"]
    finally:
        for client in clients:
            client.close()
        server.stop()
        thread.join(timeout=1)