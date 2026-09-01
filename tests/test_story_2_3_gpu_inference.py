import sys
import threading
import time

from lagent.common.transport import AgentTransport, make_endpoint
from lagent.gpu_server.server import GpuInferenceServer, YoloInference


def _cleanup_server(clients, server, thread, server_errors):
    cleanup_errors = []
    for agent_id, client in clients.items():
        try:
            client.close()
        except Exception as exc:
            exc.add_note(f"Failed to close {agent_id} transport")
            cleanup_errors.append(exc)
    try:
        server.stop()
    except Exception as exc:
        exc.add_note("Failed to stop GPU server")
        cleanup_errors.append(exc)
    thread.join(timeout=1.0)
    if thread.is_alive():
        cleanup_errors.append(
            AssertionError("GPU server thread did not terminate after bounded join")
        )
    for error in server_errors:
        error.add_note("GPU server thread failed")
        cleanup_errors.append(error)

    primary_error = sys.exception()
    if primary_error is not None:
        for error in cleanup_errors:
            primary_error.add_note(f"Cleanup failure: {error!r}")
    elif cleanup_errors:
        raise ExceptionGroup("Transport cleanup failed", cleanup_errors)


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
    server_errors = []

    def serve():
        try:
            server.serve()
        except Exception as exc:
            server_errors.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    time.sleep(0.03)
    clients = {
        agent_id: AgentTransport(agent_id, server_endpoint)
        for agent_id in ("warlord", "prophet")
    }
    try:
        for client in clients.values():
            client.connect()
        results = {}
        errors = {}
        request_timeout = 0.1
        start_barrier = threading.Barrier(len(clients))

        def request(agent_id):
            try:
                start_barrier.wait(timeout=1.0)
                results[agent_id] = clients[agent_id].request_inference(
                    b"frame", {}, timeout=request_timeout
                )
            except Exception as exc:
                errors[agent_id] = exc

        request_threads = {
            agent_id: threading.Thread(
                target=request,
                args=(agent_id,),
                daemon=True,
            )
            for agent_id in clients
        }
        started = time.perf_counter()
        for request_thread in request_threads.values():
            request_thread.start()
        for request_thread in request_threads.values():
            request_thread.join(timeout=request_timeout + 0.5)
        elapsed_ms = (time.perf_counter() - started) * 1000

        request_failures = []
        for agent_id, request_thread in request_threads.items():
            if request_thread.is_alive():
                request_failures.append(
                    AssertionError(
                        f"{agent_id} request thread did not terminate after bounded join"
                    )
                )
            if agent_id in errors:
                errors[agent_id].add_note(f"{agent_id} inference request failed")
                request_failures.append(errors[agent_id])
        if request_failures:
            raise ExceptionGroup("Inference requests failed", request_failures)

        for agent_id in clients:
            assert agent_id in results, f"{agent_id} inference request produced no result"
            result = results[agent_id]
            assert result.agent_id == agent_id, (
                f"{agent_id} received response for {result.agent_id}"
            )
            assert len(result.result.detections) > 1, (
                f"{agent_id} response omitted its class-specific detection"
            )
            class_name = result.result.detections[1].class_name
            assert class_name == agent_id, (
                f"{agent_id} received class-specific detection {class_name!r}"
            )
        assert elapsed_ms < 100, (
            f"concurrent inference requests took {elapsed_ms:.1f}ms, expected under 100ms"
        )
    finally:
        _cleanup_server(clients, server, thread, server_errors)