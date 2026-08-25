import logging
import time

from lagent.agent.capture import CaptureThread, Frame, FrameQueue, _load_dxcam_backend, resolve_capture_backend


class FakeDxcam:
    def __init__(self):
        self.calls = 0
        self.regions = []

    def grab(self, region=None):
        self.calls += 1
        self.regions.append(region)
        return {"frame_id": self.calls, "kind": "dxcam"}


class FakeMss:
    def __init__(self):
        self.calls = 0

    def grab(self, region):
        self.calls += 1
        return {"frame_id": self.calls, "kind": "mss", "region": region}


def test_resolve_capture_backend_uses_dxcam_when_available(monkeypatch):
    fake = FakeDxcam()

    def fake_dxcam_factory():
        return fake

    monkeypatch.setattr("lagent.agent.capture._load_dxcam_backend", lambda window_title, fps: fake)
    monkeypatch.setattr("lagent.agent.capture._load_mss_backend", lambda: FakeMss())

    backend_name, backend = resolve_capture_backend("Lineage II", fps=10)

    assert backend_name == "dxcam"
    assert backend is fake


def test_dxcam_backend_is_bound_to_window_region(monkeypatch):
    fake = FakeDxcam()
    fake_module = type("DxcamModule", (), {"create": staticmethod(lambda: fake)})

    monkeypatch.setitem(__import__("sys").modules, "dxcam", fake_module)
    monkeypatch.setattr("lagent.agent.capture._resolve_window_region", lambda title: (1, 2, 101, 202))

    backend = _load_dxcam_backend("Lineage II", fps=10)
    backend.grab(region=backend.window_region)

    assert backend.window_region == (1, 2, 101, 202)
    assert fake.regions == [(1, 2, 101, 202)]


def test_frame_queue_put_and_put_nowait_evict_oldest_without_blocking():
    frame_queue = FrameQueue(maxsize=2)
    frames = [Frame("Lineage II", index, index, "test", float(index)) for index in range(3)]

    frame_queue.put(frames[0])
    frame_queue.put_nowait(frames[1])
    frame_queue.put(frames[2], block=True, timeout=30)

    assert [frame.frame for frame in (frame_queue.get_nowait(), frame_queue.get_nowait())] == [1, 2]


def test_capture_thread_uses_oldest_frame_eviction_and_records_timestamp(monkeypatch):
    fake = FakeDxcam()

    monkeypatch.setattr("lagent.agent.capture._load_dxcam_backend", lambda window_title, fps: fake)
    monkeypatch.setattr("lagent.agent.capture._load_mss_backend", lambda: FakeMss())

    thread = CaptureThread(window_title="Lineage II", fps=10, max_queue_size=2)
    thread.start()
    time.sleep(0.12)
    thread.stop()
    thread.join(timeout=1.0)

    assert thread.frame_queue.qsize() >= 1
    frame = thread.frame_queue.get_nowait()
    assert frame.window_title == "Lineage II"
    assert frame.captured_at_ms > 0
    assert frame.frame["kind"] in {"dxcam", "mss"}


def test_resolve_capture_backend_falls_back_to_mss_and_logs(caplog, monkeypatch):
    def fail_dxcam():
        raise RuntimeError("dxcam unavailable")

    fake_mss = FakeMss()

    monkeypatch.setattr("lagent.agent.capture._load_dxcam_backend", lambda window_title, fps: fail_dxcam())
    monkeypatch.setattr("lagent.agent.capture._load_mss_backend", lambda: fake_mss)

    with caplog.at_level(logging.INFO):
        backend_name, backend = resolve_capture_backend("Lineage II", fps=10)

    assert backend_name == "mss"
    assert backend is fake_mss
    assert "fallback" in caplog.text.lower()
