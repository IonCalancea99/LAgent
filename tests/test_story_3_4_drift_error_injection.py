import random

import pytest

from lagent.common import Action
from lagent.common.sessions_db import SessionsDB
from lagent.hsl import HSL


class FakeController:
    def __init__(self):
        self.points = []
        self.clicks = []

    def move(self, x, y):
        self.points.append((x, y))

    def click(self, button="left", clicks=1):
        self.clicks.append((button, clicks))


def test_idle_micro_drift_is_off_by_default():
    controller = FakeController()
    hsl = HSL({}, controller=controller, sleeper=lambda _: None, rng=random.Random(4))

    assert hsl.idle((100, 100)) is False
    assert controller.points == []


def test_idle_micro_drift_returns_to_origin_and_can_drift_camera():
    controller = FakeController()
    camera_calls = []
    profile = {
        "micro_drift_enabled": True,
        "micro_drift_frequency": 1.0,
        "micro_drift_magnitude": (3, 3),
        "camera_drift_enabled": True,
        "camera_drift_rate": 1.0,
    }
    hsl = HSL(profile, controller=controller, sleeper=lambda _: None, rng=random.Random(4))

    assert hsl.idle((100, 100), camera_drift=lambda: camera_calls.append(True)) is True
    assert controller.points[-1] == (100.0, 100.0)
    assert hsl.cursor_position == (100.0, 100.0)
    assert camera_calls == [True]


def test_dispatch_actions_keeps_policy_sequence_inside_hsl():
    controller = FakeController()
    hsl = HSL({}, controller=controller, sleeper=lambda _: None, rng=random.Random(4))

    results = hsl.dispatch_actions([
        Action(action_type="mouse_move", x=10, y=20),
        Action(action_type="mouse_click", x=10, y=20),
    ])

    assert len(results) == 2
    assert controller.clicks == [("left", 1)]


def test_invalid_micro_drift_magnitude_is_rejected():
    hsl = HSL({"micro_drift_enabled": True, "micro_drift_frequency": 1.0, "micro_drift_magnitude": (0, 0)},
              controller=FakeController(), sleeper=lambda _: None, rng=random.Random(4))

    with pytest.raises(ValueError, match="micro_drift_magnitude"):
        hsl.idle((100, 100))


def test_dispatch_injects_corrective_click_and_logs_override(tmp_path):
    controller = FakeController()
    profile = {
        "error_injection_probability": 0.02,
        "micro_drift_magnitude": (4, 4),
    }
    hsl = HSL(profile, controller=controller, sleeper=lambda _: None, rng=random.Random(7))
    db = SessionsDB(str(tmp_path / "sessions.db"))
    db.log_session_start("session", "prophet", "active")

    overrides = 0
    for _ in range(200):
        result = hsl.dispatch_action(
            Action(action_type="mouse_click", x=100, y=100, button="left"),
            session_id="session",
            sessions_db=db,
        )
        overrides += result is not None

    events = db.get_events_by_type("session", "override")
    db.close()
    assert 2 <= overrides <= 6
    assert len(events) == overrides
    assert all(len(event["payload"]["wrong_target"]) == 2 for event in events)
    assert len(controller.clicks) == 200 + overrides


def test_dispatch_protects_key_presses_from_error_injection():
    keyboard = type("Keyboard", (), {"pressed": [], "press": lambda self, key: self.pressed.append(key)})()
    profile = {"error_injection_probability": 1.0}
    hsl = HSL(profile, keyboard_controller=keyboard, sleeper=lambda _: None, rng=random.Random(1))

    hsl.dispatch_action(Action(action_type="key_press", key="x"))

    assert keyboard.pressed == ["x"]
    assert hsl.last_override is None