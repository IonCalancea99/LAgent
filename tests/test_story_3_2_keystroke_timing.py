import random

from lagent.hsl import HSL


class FakeKeyboardController:
    def __init__(self):
        self.pressed = []

    def press(self, key):
        self.pressed.append(key)


def test_hsl_uses_per_skill_gaussian_delay_for_key_presses():
    controller = FakeKeyboardController()
    profile = type(
        "Profile",
        (),
        {"skill_timing": {"heal": {"mean": 0.18, "std": 0.06}}},
    )()
    hsl = HSL(profile, controller=controller, sleeper=lambda _: None, rng=random.Random(7))

    first = hsl.press_key("heal", "1")
    second = hsl.press_key("heal", "1")

    assert controller.pressed == ["1", "1"]
    assert isinstance(first, float)
    assert isinstance(second, float)
    assert first > 0
    assert second > 0
    assert first != second


def test_hsl_uses_updated_skill_timing_params():
    controller = FakeKeyboardController()
    profile = type(
        "Profile",
        (),
        {"skill_timing": {"heal": {"mean": 0.10, "std": 0.01}}},
    )()
    hsl = HSL(profile, controller=controller, sleeper=lambda _: None, rng=random.Random(9))

    delay = hsl.press_key("heal", "2")

    assert 0.05 <= delay <= 0.20


def test_hsl_replaces_zero_variance_with_positive_noise():
    controller = FakeKeyboardController()
    profile = type(
        "Profile",
        (),
        {"skill_timing": {"heal": {"mean": 0.18, "std": 0.0}}},
    )()
    hsl = HSL(profile, controller=controller, sleeper=lambda _: None, rng=random.Random(13))

    first = hsl.press_key("heal", "3")
    second = hsl.press_key("heal", "3")

    assert first > 0.0
    assert second > 0.0
    assert first != second
