import random

from lagent.hsl import HSL, generate_bezier_path


class FakeController:
    def __init__(self):
        self.points = []

    def move(self, x, y):
        self.points.append((x, y))


def test_generate_bezier_path_preserves_endpoints_and_is_not_straight():
    path = generate_bezier_path((0, 0), (300, 0), rng=random.Random(4))

    assert path.points[0] == (0.0, 0.0)
    assert path.points[-1] == (300.0, 0.0)
    assert any(abs(y) > 0.01 for _, y in path.points[1:-1])


def test_generate_bezier_path_has_slow_fast_slow_timing():
    path = generate_bezier_path((0, 0), (300, 100), duration=1.0, rng=random.Random(4))
    middle = len(path.delays) // 2

    assert path.delays[0] > path.delays[middle]
    assert path.delays[-1] > path.delays[middle]
    assert sum(path.delays) > 0.9


def test_repeated_paths_are_randomized():
    paths = [generate_bezier_path((0, 0), (300, 100)) for _ in range(100)]

    assert len({path.points for path in paths}) == 100


def test_zero_offset_range_is_rejected():
    try:
        generate_bezier_path((0, 0), (300, 0), offset_range=(0, 0), rng=random.Random(4))
        raise AssertionError("zero offset range should be rejected")
    except ValueError:
        pass


def test_hsl_uses_profile_range_and_routes_every_sample_to_controller():
    controller = FakeController()
    profile = type("Profile", (), {"bezier_offset_range": (40, 40)})()
    path = HSL(profile, controller=controller, sleeper=lambda _: None).move_mouse(
        (0, 0), (300, 0), samples=8, duration=0.1
    )

    assert controller.points == list(path.points[1:])
    assert all(abs(point[1]) == 40 for point in path.control_points)