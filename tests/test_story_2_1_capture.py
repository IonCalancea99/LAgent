import logging
import sys
import time
import pytest

from lagent.agent.capture import (
    CaptureThread,
    Frame,
    FrameQueue,
    _get_dxcam_output_dimensions,
    _load_dxcam_backend,
    _resolve_window_region,
    _validate_dxcam_region,
    normalize_capture_region,
    resolve_capture_backend,
)


class FakeDxcam:
    def __init__(self, width: int = 1920, height: int = 1080):
        self.calls = 0
        self.regions = []
        self.width = width
        self.height = height

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


# --- Story 2.1 DXCam Coordinate Normalization and Dynamic Bounds Tests ---


def test_normalize_capture_region_asterios_negative_coords():
    """Asterios window (-1, 32, 1919, 1044) on 1920x1080 screen normalizes to (0, 32, 1919, 1044)."""
    window = (-1, 32, 1919, 1044)
    screen = (1920, 1080)
    normalized = normalize_capture_region(window, screen)
    assert normalized == (0, 32, 1919, 1044)
    # Check strict invariants
    assert 0 <= normalized[0] < normalized[2] <= screen[0]
    assert 0 <= normalized[1] < normalized[3] <= screen[1]


def test_normalize_capture_region_completely_inside():
    """Window completely inside screen bounds retains exact coordinates."""
    window = (100, 100, 900, 700)
    screen = (1920, 1080)
    normalized = normalize_capture_region(window, screen)
    assert normalized == (100, 100, 900, 700)
    assert 0 <= normalized[0] < normalized[2] <= screen[0]
    assert 0 <= normalized[1] < normalized[3] <= screen[1]


def test_normalize_capture_region_partially_outside_left():
    """Window extending past the left screen edge is clamped at left=0."""
    window = (-50, 50, 500, 600)
    screen = (1920, 1080)
    normalized = normalize_capture_region(window, screen)
    assert normalized == (0, 50, 500, 600)
    assert 0 <= normalized[0] < normalized[2] <= screen[0]
    assert 0 <= normalized[1] < normalized[3] <= screen[1]


def test_normalize_capture_region_partially_outside_top():
    """Window extending above the top screen edge is clamped at top=0."""
    window = (50, -20, 500, 600)
    screen = (1920, 1080)
    normalized = normalize_capture_region(window, screen)
    assert normalized == (50, 0, 500, 600)
    assert 0 <= normalized[0] < normalized[2] <= screen[0]
    assert 0 <= normalized[1] < normalized[3] <= screen[1]


def test_normalize_capture_region_partially_outside_right():
    """Window extending past the right screen edge is clamped at right=screen_width."""
    window = (1500, 100, 2000, 800)
    screen = (1920, 1080)
    normalized = normalize_capture_region(window, screen)
    assert normalized == (1500, 100, 1920, 800)
    assert 0 <= normalized[0] < normalized[2] <= screen[0]
    assert 0 <= normalized[1] < normalized[3] <= screen[1]


def test_normalize_capture_region_partially_outside_bottom():
    """Window extending below the bottom screen edge is clamped at bottom=screen_height."""
    window = (100, 800, 900, 1200)
    screen = (1920, 1080)
    normalized = normalize_capture_region(window, screen)
    assert normalized == (100, 800, 900, 1080)
    assert 0 <= normalized[0] < normalized[2] <= screen[0]
    assert 0 <= normalized[1] < normalized[3] <= screen[1]


@pytest.mark.parametrize(
    "outside_window",
    [
        (-500, 100, -100, 600),   # completely to the left
        (2000, 100, 2500, 600),   # completely to the right
        (100, -500, 600, -100),   # completely above
        (100, 1200, 600, 1500),   # completely below
    ],
)
def test_normalize_capture_region_completely_outside_raises(outside_window):
    """Windows with no visible intersection with the display raise RuntimeError."""
    screen = (1920, 1080)
    with pytest.raises(RuntimeError, match="outside display bounds"):
        normalize_capture_region(outside_window, screen)


def test_normalize_capture_region_invalid_inputs():
    """Invalid window coordinates or non-positive screen sizes raise errors."""
    with pytest.raises(RuntimeError, match="invalid or empty rect"):
        normalize_capture_region((500, 100, 400, 600), (1920, 1080))

    with pytest.raises(RuntimeError, match="invalid or empty rect"):
        normalize_capture_region((100, 500, 400, 400), (1920, 1080))

    with pytest.raises(ValueError, match="invalid screen dimensions"):
        normalize_capture_region((0, 0, 100, 100), (0, 1080))

    with pytest.raises(ValueError, match="invalid screen dimensions"):
        normalize_capture_region((0, 0, 100, 100), (1920, -10))


def test_normalize_capture_region_multi_monitor_offset():
    """Window on secondary monitor with non-zero monitor origin is correctly normalized."""
    window_virtual = (1919, 32, 3839, 1044)  # 1px left of monitor 2
    screen_size = (1920, 1080)
    monitor_origin = (1920, 0)

    normalized = normalize_capture_region(window_virtual, screen_size, monitor_origin=monitor_origin)
    assert normalized == (0, 32, 1919, 1044)
    assert 0 <= normalized[0] < normalized[2] <= screen_size[0]
    assert 0 <= normalized[1] < normalized[3] <= screen_size[1]


def test_get_dxcam_output_dimensions_dynamic():
    """DXCam output dimensions are detected dynamically from backend attributes or OS metrics."""
    # 1. From backend width/height (e.g. 2560x1440 monitor)
    backend = FakeDxcam(width=2560, height=1440)
    assert _get_dxcam_output_dimensions(backend=backend) == (2560, 1440)

    # 2. From backend.output attribute
    class DummyOutput:
        width = 3840
        height = 2160

    backend_with_output = type("Camera", (), {"output": DummyOutput()})()
    assert _get_dxcam_output_dimensions(backend=backend_with_output) == (3840, 2160)

    # 3. Fallback default for mock environments without backend/OS
    assert _get_dxcam_output_dimensions(backend=None) == (1920, 1080)


def test_validate_dxcam_region():
    """_validate_dxcam_region validates strict inequalities and bounds."""
    # Valid
    _validate_dxcam_region((0, 0, 1920, 1080), screen_size=(1920, 1080))
    _validate_dxcam_region((0, 32, 1919, 1044), screen_size=(1920, 1080))

    # Invalid cases
    with pytest.raises(RuntimeError):
        _validate_dxcam_region((-1, 32, 1919, 1044), screen_size=(1920, 1080))

    with pytest.raises(RuntimeError):
        _validate_dxcam_region((0, -5, 1919, 1044), screen_size=(1920, 1080))

    with pytest.raises(RuntimeError):
        _validate_dxcam_region((0, 32, 1921, 1044), screen_size=(1920, 1080))

    with pytest.raises(RuntimeError):
        _validate_dxcam_region((0, 32, 1919, 1081), screen_size=(1920, 1080))

    with pytest.raises(RuntimeError):
        _validate_dxcam_region((500, 32, 500, 1044), screen_size=(1920, 1080))


def test_frame_coordinate_translation():
    """Frame helper methods correctly translate between frame, client, and screen coordinates."""
    # Simulating Asterios cropped by 1px on left and top at 32
    frame_obj = Frame(
        window_title="Asterios",
        frame={"data": "dummy"},
        captured_at_ms=1000,
        source="dxcam",
        captured_at=1.0,
        crop_offset=(1, 0),
        screen_offset=(0, 32),
        raw_window_rect=(-1, 32, 1919, 1044),
        capture_region=(0, 32, 1919, 1044),
    )

    # Frame pixel (0, 0)
    assert frame_obj.frame_to_screen(0, 0) == (0, 32)
    assert frame_obj.frame_to_client(0, 0) == (1, 0)

    # Frame pixel (100, 200)
    assert frame_obj.frame_to_screen(100, 200) == (100, 232)
    assert frame_obj.frame_to_client(100, 200) == (101, 200)

    # Screen to frame inverse
    assert frame_obj.screen_to_frame(100, 232) == (100, 200)
    assert frame_obj.screen_to_frame(0, 32) == (0, 0)

    # Client to frame inverse
    assert frame_obj.client_to_frame(101, 200) == (100, 200)
    assert frame_obj.client_to_frame(1, 0) == (0, 0)
    assert frame_obj.client_to_frame(0, 0) == (-1, 0)  # Off-frame on left


def test_load_dxcam_backend_accepts_asterios_negative_coords(monkeypatch):
    """_load_dxcam_backend normalizes (-1, 32, 1919, 1044) and successfully initializes DXCam."""
    fake = FakeDxcam(width=1920, height=1080)
    fake_module = type("DxcamModule", (), {"create": staticmethod(lambda: fake)})

    monkeypatch.setitem(sys.modules, "dxcam", fake_module)
    monkeypatch.setattr(
        "lagent.agent.capture._resolve_window_region",
        lambda title: (-1, 32, 1919, 1044),
    )

    backend = _load_dxcam_backend("Asterios", fps=10)
    assert backend is fake
    assert backend.window_region == (0, 32, 1919, 1044)
    assert backend.crop_offset == (1, 0)
    assert backend.screen_offset == (0, 32)
    assert backend.screen_size == (1920, 1080)


def test_load_dxcam_backend_debug_logging(caplog, monkeypatch):
    """_load_dxcam_backend logs window rect, dxcam output size, and normalized capture region."""
    fake = FakeDxcam(width=1920, height=1080)
    fake_module = type("DxcamModule", (), {"create": staticmethod(lambda: fake)})

    monkeypatch.setitem(sys.modules, "dxcam", fake_module)
    monkeypatch.setattr(
        "lagent.agent.capture._resolve_window_region",
        lambda title: (-1, 32, 1919, 1044),
    )

    with caplog.at_level(logging.DEBUG):
        _load_dxcam_backend("Asterios", fps=10)

    log_text = caplog.text
    assert "Asterios window rect: (-1, 32, 1919, 1044)" in log_text
    assert "DXCam output size: (1920, 1080)" in log_text
    assert "Normalized capture region: (0, 32, 1919, 1044)" in log_text
