"""Human-like mouse paths and the single mouse movement entry point."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence

from lagent.common.types import Action

Point = tuple[float, float]
OffsetRange = tuple[int, int]


class MouseController(Protocol):
    def move(self, x: float, y: float) -> None:
        """Move the operating-system cursor to a point."""

    def click(self, button: Any = "left", clicks: int = 1) -> None:
        """Click a mouse button."""


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
                 sleeper: Callable[[float], None] = time.sleep, rng: random.Random | None = None,
                 clock: Callable[[], float] | None = None, mode: str = "active",
                 session_id: str | None = None, sessions_db: Any = None) -> None:
        if mode not in {"active", "shadow"}:
            raise ValueError("mode must be 'active' or 'shadow'")
        self.profile = profile
        self.controller = controller
        self.keyboard_controller = keyboard_controller
        self.sleeper = sleeper
        self.rng = rng or random.Random()
        self.clock = clock or time.monotonic
        self._mode = mode
        self.session_id = session_id
        self.sessions_db = sessions_db
        self.fatigue_factor = 1.0
        started_at = self.clock()
        self.break_active = False
        self.fatigue_state = {
            "started_at": started_at,
            "last_tick": started_at,
            "last_break_at": None,
            "increments": 0,
            "break_until": None,
            "elapsed_since_increment": 0.0,
            "fatigue_interval": self._resolve_fatigue_interval(),
        }
        self.cursor_position: Point = (0.0, 0.0)
        self.last_override: dict[str, Any] | None = None

    @property
    def mode(self) -> str:
        """Return the process-fixed input mode."""
        return self._mode

    @property
    def shadow(self) -> bool:
        return self._mode == "shadow"

    def _log_shadow_action(self, payload: dict[str, Any]) -> None:
        if self.shadow and self.session_id is not None and self.sessions_db is not None:
            self.sessions_db.append_event(self.session_id, "hsl", "action", payload)

    def _get_profile_value(self, name: str, default: object) -> object:
        if self.profile is None:
            return default
        if isinstance(self.profile, dict):
            return self.profile.get(name, default)
        return getattr(self.profile, name, default)

    def _resolve_break_range(self) -> tuple[float, float]:
        raw_range = self._get_profile_value("break_duration_range", (300.0, 900.0))
        if isinstance(raw_range, (list, tuple)) and len(raw_range) == 2:
            minimum, maximum = float(raw_range[0]), float(raw_range[1])
            if maximum < minimum:
                minimum, maximum = maximum, minimum
            return minimum, maximum
        return 300.0, 900.0

    def _resolve_fatigue_interval(self) -> float:
        raw_interval = self._get_profile_value("fatigue_interval", (1800.0, 3600.0))
        if isinstance(raw_interval, (list, tuple)) and len(raw_interval) == 2:
            minimum, maximum = sorted(float(value) for value in raw_interval)
            if maximum <= 0:
                return 1800.0
            return self.rng.uniform(minimum, maximum) if minimum != maximum else maximum
        interval = float(raw_interval)
        return interval if interval > 0 else 1800.0

    def _resolve_fatigue_step(self) -> float:
        value = float(self._get_profile_value("fatigue_step", 0.05))
        return value if value >= 0 else 0.0

    def _resolve_fatigue_ceiling(self) -> float:
        value = float(self._get_profile_value("fatigue_ceiling", 1.5))
        return value if value >= 1.0 else 1.0

    def _sample_break_duration(self) -> float:
        minimum, maximum = self._resolve_break_range()
        if maximum <= minimum:
            return float(minimum)
        return self.rng.uniform(minimum, maximum)

    def _resolve_micro_drift_magnitude(self) -> OffsetRange:
        raw_magnitude = self._get_profile_value("micro_drift_magnitude", (2, 8))
        if isinstance(raw_magnitude, (str, bytes)):
            raise ValueError("micro_drift_magnitude must contain two finite positive numbers")
        try:
            if len(raw_magnitude) != 2:
                raise ValueError
            values = tuple(float(value) for value in raw_magnitude)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("micro_drift_magnitude must contain two finite positive numbers") from error
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError("micro_drift_magnitude must contain two finite positive numbers")
        return tuple(sorted(int(value) for value in values))  # type: ignore[return-value]

    def _advance_fatigue(self, elapsed: float) -> None:
        if elapsed <= 0.0:
            return
        if self.break_active:
            return

        interval = self.fatigue_state["fatigue_interval"]
        if interval <= 0.0:
            return

        total_elapsed = self.fatigue_state["elapsed_since_increment"] + elapsed
        increments = int(total_elapsed // interval)
        self.fatigue_state["elapsed_since_increment"] = total_elapsed % interval
        if increments <= 0:
            return

        step = self._resolve_fatigue_step()
        ceiling = self._resolve_fatigue_ceiling()
        self.fatigue_state["increments"] += increments
        self.fatigue_factor = min(ceiling, 1.0 + (self.fatigue_state["increments"] * step))

        if self.fatigue_factor >= ceiling:
            self._trigger_break()

    def _trigger_break(self) -> None:
        if self.break_active:
            return
        self.break_active = True
        self.fatigue_state["break_until"] = self.clock() + self._sample_break_duration()
        self.fatigue_state["last_break_at"] = self.clock()

    def _finish_break(self, timestamp: float | None = None) -> None:
        if timestamp is None:
            timestamp = self.clock()
        self.break_active = False
        self.fatigue_factor = 1.0
        self.fatigue_state["break_until"] = None
        self.fatigue_state["increments"] = 0
        self.fatigue_state["elapsed_since_increment"] = 0.0
        self.fatigue_state["fatigue_interval"] = self._resolve_fatigue_interval()
        self.fatigue_state["started_at"] = timestamp
        self.fatigue_state["last_tick"] = timestamp

    def _tick_fatigue(self) -> None:
        now = self.clock()
        last_tick = self.fatigue_state["last_tick"]
        if self.break_active:
            if self.fatigue_state["break_until"] is not None and now >= self.fatigue_state["break_until"]:
                self._finish_break(now)
            self.fatigue_state["last_tick"] = now
            return
        elapsed = max(0.0, now - last_tick)
        self._advance_fatigue(elapsed)
        self.fatigue_state["last_tick"] = now

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

    def _click(self, button: str, clicks: int = 1) -> None:
        if self.shadow:
            return
        controller = self._get_controller()
        button_value = button
        controller_module = getattr(type(controller), "__module__", "")
        if controller_module.startswith("pynput"):
            try:
                from pynput.mouse import Button
                button_value = getattr(Button, button)
            except (ImportError, AttributeError):
                button_value = button
        controller.click(button_value, clicks=clicks)

    def _log_override(self, session_id: str | None, sessions_db: Any, payload: dict[str, Any]) -> None:
        if session_id is not None and sessions_db is not None:
            sessions_db.append_event(session_id, "hsl", "override", payload)

    def dispatch_action(self, action: Action | dict[str, Any], *, source: Sequence[float] | None = None,
                        skill_id: str = "default", session_id: str | None = None,
                        sessions_db: Any = None) -> Any:
        """Dispatch every policy action through HSL before it reaches OS input."""
        if isinstance(action, dict):
            action = Action.model_validate(action)
        action_source = self.cursor_position if source is None else (float(source[0]), float(source[1]))
        protected = tuple(self._get_profile_value("protected_action_types", ("key_press", "wait")))
        probability = float(self._get_profile_value("error_injection_probability", 0.0))
        should_override = (
            action.action_type == "mouse_click"
            and action.action_type not in protected
            and probability > 0.0
            and self.rng.random() < probability
            and action.x is not None
            and action.y is not None
        )
        if should_override:
            minimum, maximum = self._resolve_micro_drift_magnitude()
            distance = self.rng.randint(minimum, maximum)
            wrong_target = (action.x + self.rng.choice((-distance, distance)), action.y + self.rng.choice((-distance, distance)))
            self.move_mouse(action_source, wrong_target)
            self._click(action.button or "left", action.clicks or 1)
            self.move_mouse(wrong_target, (action.x, action.y))
            self._click(action.button or "left", action.clicks or 1)
            self.last_override = {"action_type": action.action_type, "target": [action.x, action.y], "wrong_target": list(wrong_target)}
            self._log_override(session_id, sessions_db, self.last_override)
            self.cursor_position = (float(action.x), float(action.y))
            return self.last_override

        if action.action_type == "mouse_move":
            if action.x is None or action.y is None:
                raise ValueError("mouse_move requires x and y")
            result = self.move_mouse(action_source, (action.x, action.y))
            self.cursor_position = (float(action.x), float(action.y))
            self._log_shadow_action({
                "action_type": action.action_type,
                "target": [action.x, action.y],
                "bezier_path": self._path_payload(result),
                "timing_value": sum(result.delays) * self.fatigue_factor,
                "fatigue_factor": self.fatigue_factor,
            })
            return result
        if action.action_type == "mouse_click":
            if action.x is not None and action.y is not None:
                path = self.move_mouse(action_source, (action.x, action.y))
                self.cursor_position = (float(action.x), float(action.y))
            else:
                path = None
            self._click(action.button or "left", action.clicks or 1)
            self._log_shadow_action({
                "action_type": action.action_type,
                "target": [action.x, action.y] if action.x is not None and action.y is not None else None,
                "button": action.button or "left",
                "clicks": action.clicks or 1,
                "bezier_path": self._path_payload(path),
                "timing_value": sum(path.delays) * self.fatigue_factor if path is not None else 0.0,
                "fatigue_factor": self.fatigue_factor,
            })
            return None
        if action.action_type == "key_press":
            if not action.key:
                raise ValueError("key_press requires key")
            delay = self.press_key(skill_id, action.key)
            self._log_shadow_action({
                "action_type": action.action_type,
                "key": action.key,
                "timing_value": delay,
                "fatigue_factor": self.fatigue_factor,
            })
            return delay
        if action.action_type == "wait":
            self._tick_fatigue()
            delay = max(0.0, action.duration or 0.0) * self.fatigue_factor
            if not self.break_active:
                self.sleeper(delay)
            self._log_shadow_action({
                "action_type": action.action_type,
                "timing_value": delay,
                "fatigue_factor": self.fatigue_factor,
            })
            return delay
        raise ValueError(f"unsupported action type: {action.action_type}")

    def dispatch_actions(self, actions: Sequence[Action | dict[str, Any]], **kwargs: Any) -> list[Any]:
        """Dispatch a policy-produced sequence through this HSL instance."""
        return [self.dispatch_action(action, **kwargs) for action in actions]

    def idle(self, position: Sequence[float] | None = None, *, camera_drift: Callable[[], None] | None = None) -> bool:
        """Apply one optional cursor/camera drift while the agent is idle."""
        self._tick_fatigue()
        if self.break_active:
            return False
        origin = self.cursor_position if position is None else (float(position[0]), float(position[1]))
        drifted = bool(self._get_profile_value("micro_drift_enabled", False)) and self.rng.random() < float(self._get_profile_value("micro_drift_frequency", 0.05))
        if drifted:
            minimum, maximum = self._resolve_micro_drift_magnitude()
            target = (origin[0] + self.rng.randint(minimum, maximum) * self.rng.choice((-1, 1)),
                      origin[1] + self.rng.randint(minimum, maximum) * self.rng.choice((-1, 1)))
            self.move_mouse(origin, target, samples=8, duration=0.08)
            self.move_mouse(target, origin, samples=8, duration=0.08)
            self.cursor_position = origin
        if (bool(self._get_profile_value("camera_drift_enabled", False)) and camera_drift is not None
                and self.rng.random() < float(self._get_profile_value("camera_drift_rate", 0.0))):
            camera_drift()
        return drifted

    dispatch = dispatch_action

    @staticmethod
    def _path_payload(path: BezierPath | None) -> dict[str, Any] | None:
        if path is None:
            return None
        return {
            "points": [list(point) for point in path.points],
            "delays": list(path.delays),
            "control_points": [list(point) for point in path.control_points],
        }

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
        return max(0.0, sampled) * self.fatigue_factor

    def press_key(self, skill_id: str, key: str) -> float:
        self._tick_fatigue()
        if self.break_active:
            return 0.0

        delay = self._sample_skill_delay(skill_id)
        if not self.shadow:
            self._get_keyboard_controller().press(key)
        self.sleeper(delay)
        return delay

    def move_mouse(self, source: Sequence[float], target: Sequence[float], *, samples: int = 24,
                   duration: float | None = None) -> BezierPath:
        self._tick_fatigue()
        offset_range = getattr(self.profile, "bezier_offset_range", (15, 30))
        path = generate_bezier_path(source, target, offset_range=offset_range, samples=samples,
                                    duration=duration, rng=self.rng)
        if self.break_active:
            return path

        if not self.shadow:
            controller = self._get_controller()
            for point, delay in zip(path.points[1:], path.delays):
                controller.move(*point)
                self.sleeper(delay * self.fatigue_factor)
        return path
        