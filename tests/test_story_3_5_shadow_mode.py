import random

from lagent.common import Action
from lagent.common.sessions_db import SessionsDB
from lagent.hsl import HSL


class FailingController:
    def move(self, x, y):
        raise AssertionError("shadow mode emitted mouse movement")

    def click(self, button="left", clicks=1):
        raise AssertionError("shadow mode emitted mouse click")

    def press(self, key):
        raise AssertionError("shadow mode emitted keyboard input")


def test_shadow_shapes_and_logs_actions_without_os_output(tmp_path):
    db = SessionsDB(str(tmp_path / "sessions.db"))
    db.log_session_start("shadow-session", "prophet", "shadow")
    hsl = HSL(
        {"skill_timing": {"default": {"mean": 0.2, "std": 0.0}}},
        controller=FailingController(),
        keyboard_controller=FailingController(),
        sleeper=lambda _: None,
        rng=random.Random(3),
        mode="shadow",
        session_id="shadow-session",
        sessions_db=db,
    )

    hsl.dispatch_actions([
        Action(action_type="mouse_move", x=100, y=80),
        Action(action_type="mouse_click", x=100, y=80),
        Action(action_type="key_press", key="1"),
        Action(action_type="wait", duration=0.1),
    ])

    events = db.get_events_by_type("shadow-session", "action")
    db.close()
    assert [event["payload"]["action_type"] for event in events] == [
        "mouse_move", "mouse_click", "key_press", "wait"
    ]
    assert events[0]["payload"]["bezier_path"]["points"]
    assert events[0]["payload"]["timing_value"] > 0
    assert all(event["payload"]["fatigue_factor"] >= 1.0 for event in events)


def test_shadow_mode_is_fixed_for_hsl_instance():
    hsl = HSL(mode="shadow")

    assert hsl.mode == "shadow"
    try:
        hsl.mode = "active"
    except AttributeError:
        pass
    else:
        raise AssertionError("shadow mode must not be mutable")