"""Human-like mouse paths and the single mouse movement entry point."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

Point = tuple[float, float]
OffsetRange = tuple[int, int]


class MouseController(Protocol):
    def move(self, x: float, y: float) -> None:
        """Move the operating-system cursor to a point."""


class KeyboardController(Protocol):
    def press(self, key: str) -> None:
        """Send a key press to the operating system."""


@dataclass(frozen=True)
class BezierPath:
    """A sampled cubic path and the delay before each sampled point."""

    points: tuple[Point, ...]
    delays: tuple[float, ...]
    control_points: tuple[Point, Point]


def _validate_offset_range(offset_range: Sequence[int | float]) -> OffsetRange:
    if len(offset_range) != 2:
        raise ValueError("bezier_offset_range must contain minimum and maximum values")
    minimum, maximum = (int(value) for value in offset_range)
    if minimum <= 0 or maximum <= 0:
        raise ValueError("bezier_offset_range must be strictly positive to avoid straight-line mouse moves")
    if maximum < minimum:
        raise ValueError("bezier_offset_range must satisfy 0 < minimum <= maximum")
    return minimum, maximum


def _control_points(source: Point, target: Point, offset_range: OffsetRange, rng: random.Random) -> tuple[Point, Point]:
    dx = target[0] - source[0]
    dy = target[1] - source[1]
    distance = math.hypot(dx, dy)
    if distance == 0:
        return source, target

    perpendicular = (-dy / distance, dx / distance)
    minimum, maximum = offset_range
    first_offset = rng.uniform(minimum, maximum) * rng.choice((-1, 1))
    second_offset = rng.uniform(minimum, maximum) * rng.choice((-1, 1))
    first_base = (source[0] + dx / 3, source[1] + dy / 3)
    second_base = (source[0] + dx * 2 / 3, source[1] + dy * 2 / 3)
    return (
        (first_base[0] + perpendicular[0] * first_offset, first_base[1] + perpendicular[1] * first_offset),
        (second_base[0] + perpendicular[0] * second_offset, second_base[1] + perpendicular[1] * second_offset),
    )


def _cubic(source: Point, first_control: Point, second_control: Point, target: Point, progress: float) -> Point:
    inverse = 1.0 - progress
    return (
        inverse**3 * source[0]
        + 3 * inverse**2 * progress * first_control[0]
        + 3 * inverse * progress**2 * second_control[0]
        + progress**3 * target[0],
        inverse**3 * source[1]
        + 3 * inverse**2 * progress * first_control[1]
        + 3 * inverse * progress**2 * second_control[1]
        + progress**3 * target[1],
    )


def generate_bezier_path(
    source: Sequence[float],
    target: Sequence[float],
    *,
    offset_range: Sequence[int | float] = (15, 30),
    samples: int = 24,
    duration: float | None = None,
    rng: random.Random | None = None,
) -> BezierPath:
    """Generate a randomized cubic path with slow-fast-slow timing."""
    if len(source) != 2 or len(target) != 2:
        raise ValueError("source and target must each contain x and y")
    if samples < 2:
        raise ValueError("samples must be at least 2")
    if duration is not None and duration <= 0:
        raise ValueError("duration must be positive")

    source_point = (float(source[0]), float(source[1]))
    target_point = (float(target[0]), float(target[1]))
    generator = rng or random.Random()
    controls = _control_points(source_point, target_point, _validate_offset_range(offset_range), generator)
    points = tuple(
        _cubic(source_point, controls[0], controls[1], target_point, index / (samples - 1))
        for index in range(samples)
    )

    total_duration = duration if duration is not None else max(0.08, math.dist(source_point, target_point) / 1200)
    variance = generator.uniform(0.9, 1.1)
    weights = tuple(1.0 + 2.0 * (2 * index / (samples - 1) - 1) ** 2 for index in range(samples - 1))
    weight_total = sum(weights)
    delays = tuple(total_duration * variance * weight / weight_total for weight in weights)
    return BezierPath(points=points, delays=delays, control_points=controls)


class HSL:
    """Human-simulation layer; mouse movement has no alternate direct path."""

    def __init__(self, profile: object | None = None, *, controller: MouseController | None = None,
                 keyboard_controller: KeyboardController | None = None,
                 sleeper: Callable[[float], None] = time.sleep, rng: random.Random | None = None) -> None:
        self.profile = profile
        self.controller = controller
        self.keyboard_controller = keyboard_controller
        self.sleeper = sleeper
        self.rng = rng

    def _get_controller(self) -> MouseController:
        if self.controller is None:
            try:
                from pynput.mouse import Controller
            except ImportError as error:  # pragma: no cover - dependency is declared in project metadata
                raise RuntimeError("pynput is required for OS mouse output") from error
            self.controller = Controller()
        return self.controller

    def _get_keyboard_controller(self) -> KeyboardController:
        if self.keyboard_controller is not None:
            return self.keyboard_controller
        if self.controller is not None and hasattr(self.controller, "press"):
            self.keyboard_controller = self.controller
            return self.keyboard_controller
        try:
            from pynput.keyboard import Controller
        except ImportError as error:  # pragma: no cover - dependency is declared in project metadata
            raise RuntimeError("pynput is required for OS keyboard output") from error
        self.keyboard_controller = Controller()
        return self.keyboard_controller

    def _sample_skill_delay(self, skill_id: str) -> float:
        if self.profile is None:
            return self.rng.gauss(0.18, 0.05) if self.rng is not None else random.gauss(0.18, 0.05)

        raw_timing = getattr(self.profile, "skill_timing", None)
        if raw_timing is None and isinstance(self.profile, dict):
            raw_timing = self.profile.get("skill_timing")

        if isinstance(raw_timing, dict):
            params = raw_timing.get(skill_id) or raw_timing.get("default") or {"mean": 0.18, "std": 0.05}
            if isinstance(params, (list, tuple)) and len(params) == 2:
                mean, std = float(params[0]), float(params[1])
            else:
                mean = float(params.get("mean", 0.18))
                std = float(params.get("std", 0.05))
        else:
            mean, std = 0.18, 0.05

        if std < 0:
            raise ValueError("skill timing std must be non-negative")
        if std == 0:
            std = 0.01 if mean > 0 else 0.05
        sampled = self.rng.gauss(mean, std) if self.rng is not None else random.gauss(mean, std)
        return max(0.0, sampled)

    def press_key(self, skill_id: str, key: str) -> float:
        controller = self._get_keyboard_controller()
        delay = self._sample_skill_delay(skill_id)
        controller.press(key)
        self.sleeper(delay)
        return delay

    def move_mouse(self, source: Sequence[float], target: Sequence[float], *, samples: int = 24,
                   duration: float | None = None) -> BezierPath:
        offset_range = getattr(self.profile, "bezier_offset_range", (15, 30))
        path = generate_bezier_path(source, target, offset_range=offset_range, samples=samples,
                                    duration=duration, rng=self.rng)
        controller = self._get_controller()
        for point, delay in zip(path.points[1:], path.delays):
            controller.move(*point)
            self.sleeper(delay)
        return path