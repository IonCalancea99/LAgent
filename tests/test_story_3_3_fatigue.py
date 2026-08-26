import random

from lagent.hsl import HSL


class FakeKeyboardController:
    def __init__(self):
        self.pressed = []

    def press(self, key):
        self.pressed.append(key)


class FakeController:
    def __init__(self):
        self.points = []

    def move(self, x, y):
        self.points.append((x, y))


class FakeClock:
    def __init__(self):
        self.timestamp = 0.0

    def __call__(self):
        return self.timestamp


class MeanRandom:
    def gauss(self, mean, _std):
        return mean

    def uniform(self, minimum, _maximum):
        return minimum


def test_hsl_updates_fatigue_monotonically_over_time():
    profile = type(
        "Profile",
        (),
        {
            "fatigue_step": 0.25,
            "fatigue_ceiling": 1.5,
            "fatigue_interval": 10.0,
            "break_duration_range": (0.1, 0.2),
        },
    )()
    hsl = HSL(profile, controller=FakeController(), keyboard_controller=FakeKeyboardController(), sleeper=lambda _: None, rng=random.Random(3), clock=lambda: 0.0)

    hsl._advance_fatigue(10.0)
    assert hsl.fatigue_factor == 1.25

    hsl._advance_fatigue(10.0)
    assert hsl.fatigue_factor == 1.5


def test_hsl_triggers_break_and_resets_after_break():
    profile = type(
        "Profile",
        (),
        {
            "fatigue_step": 0.25,
            "fatigue_ceiling": 1.25,
            "fatigue_interval": 10.0,
            "break_duration_range": (0.1, 0.1),
        },
    )()
    keyboard = FakeKeyboardController()
    hsl = HSL(profile, controller=FakeController(), keyboard_controller=keyboard, sleeper=lambda _: None, rng=random.Random(5), clock=lambda: 0.0)

    hsl._advance_fatigue(10.0)
    assert hsl.fatigue_factor == 1.25
    assert hsl.break_active is True
    assert keyboard.pressed == []

    hsl._finish_break(0.1)
    assert hsl.break_active is False
    assert hsl.fatigue_factor == 1.0


def test_hsl_fatigue_state_is_isolated_by_instance():
    profile = type(
        "Profile",
        (),
        {
            "fatigue_step": 0.5,
            "fatigue_ceiling": 1.5,
            "fatigue_interval": 10.0,
            "break_duration_range": (0.0, 0.0),
        },
    )()
    first = HSL(profile, controller=FakeController(), keyboard_controller=FakeKeyboardController(), sleeper=lambda _: None, rng=random.Random(11), clock=lambda: 0.0)
    second = HSL(profile, controller=FakeController(), keyboard_controller=FakeKeyboardController(), sleeper=lambda _: None, rng=random.Random(17), clock=lambda: 0.0)

    first._advance_fatigue(10.0)
    second._advance_fatigue(20.0)

    assert first.fatigue_factor == 1.5
    assert second.fatigue_factor == 1.5
    assert first.fatigue_state is not second.fatigue_state


def test_hsl_accumulates_elapsed_time_between_ticks():
    profile = {
        "fatigue_step": 0.25,
        "fatigue_ceiling": 2.0,
        "fatigue_interval": 10.0,
        "break_duration_range": (1.0, 1.0),
    }
    hsl = HSL(profile, clock=lambda: 0.0)

    hsl._advance_fatigue(6.0)
    hsl._advance_fatigue(6.0)

    assert hsl.fatigue_factor == 1.25


def test_hsl_scales_keyboard_latency_by_fatigue_factor():
    delays = []
    profile = {"skill_timing": {"default": {"mean": 1.0, "std": 0.01}}}
    hsl = HSL(profile, keyboard_controller=FakeKeyboardController(), sleeper=delays.append,
              rng=MeanRandom(), clock=lambda: 0.0)
    hsl.fatigue_factor = 1.5

    delay = hsl.press_key("attack", "x")

    assert delay == 1.5
    assert delays == [1.5]


def test_hsl_suppresses_actions_during_break_and_expires_it():
    clock = FakeClock()
    keyboard = FakeKeyboardController()
    controller = FakeController()
    profile = {
        "fatigue_step": 0.5,
        "fatigue_ceiling": 1.5,
        "fatigue_interval": 10.0,
        "break_duration_range": (5.0, 5.0),
    }
    hsl = HSL(profile, controller=controller, keyboard_controller=keyboard,
              sleeper=lambda _: None, clock=clock)

    clock.timestamp = 20.0
    assert hsl.press_key("attack", "x") == 0.0
    hsl.move_mouse((0, 0), (10, 10))
    assert keyboard.pressed == []
    assert controller.points == []

    clock.timestamp = 25.0
    hsl._tick_fatigue()
    assert hsl.break_active is False
    assert hsl.fatigue_factor == 1.0
