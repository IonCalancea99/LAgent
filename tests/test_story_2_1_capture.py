import logging
import sys
import time

from lagent.agent.capture import (
    CaptureThread,
    Frame,
    FrameQueue,
    _load_dxcam_backend,
    _resolve_window_region,
    resolve_capture_backend,
)


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
    monkeypatch.setattr("lagent.agent.capture._validate_dxcam_region", lambda region: None)

    backend = _load_dxcam_backend("Lineage II", fps=10)
    backend.grab(region=backend.window_region)

    assert backend.window_region == (1, 2, 101, 202)
    assert fake.regions == [(1, 2, 101, 202)]


def test_dxcam_backend_falls_back_when_window_exceeds_primary_output(monkeypatch):
    fake_module = type("DxcamModule", (), {"create": staticmethod(FakeDxcam)})
    fake_mss = FakeMss()

    monkeypatch.setitem(sys.modules, "dxcam", fake_module)
    monkeypatch.setattr("lagent.agent.capture._resolve_window_region", lambda title: (8, 31, 1928, 1111))
    monkeypatch.setattr(
        "lagent.agent.capture._validate_dxcam_region",
        lambda region: (_ for _ in ()).throw(RuntimeError("region exceeds output")),
    )
    monkeypatch.setattr("lagent.agent.capture._load_mss_backend", lambda: fake_mss)

    backend_name, backend = resolve_capture_backend("Asterios", fps=10)

    assert backend_name == "mss"
    assert backend is fake_mss


def test_capture_thread_uses_client_region_with_mss(monkeypatch):
    fake_mss = FakeMss()

    monkeypatch.setattr(
        "lagent.agent.capture.resolve_capture_backend",
        lambda window_title, fps, log: ("mss", fake_mss),
    )
    monkeypatch.setattr(
        "lagent.agent.capture._mss_monitor_for_window",
        lambda title: {"left": 8, "top": 31, "width": 1920, "height": 1080},
    )

    thread = CaptureThread(window_title="Asterios")
    frame = thread._capture_once()

    assert frame is not None
    assert fake_mss.calls == 1
    assert frame.frame["region"] == {"left": 8, "top": 31, "width": 1920, "height": 1080}


def test_resolve_window_region_uses_client_bounds_within_screen(monkeypatch):
    class FakeWin32Gui:
        @staticmethod
        def FindWindow(class_name, window_title):
            assert class_name is None
            assert window_title == "Asterios"
            return 1

        @staticmethod
        def GetWindowRect(handle):
            raise AssertionError("capture must not use outer window bounds")

        @staticmethod
        def GetClientRect(handle):
            assert handle == 1
            return (0, 0, 1920, 1080)

        @staticmethod
        def ClientToScreen(handle, point):
            assert handle == 1
            return point

    monkeypatch.setitem(sys.modules, "win32gui", FakeWin32Gui)

    assert _resolve_window_region("Asterios") == (0, 0, 1920, 1080)


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
