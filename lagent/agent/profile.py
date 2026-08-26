"""YAML profile loading and startup validation."""

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from lagent.common import AgentProfile


REQUIRED_PROFILE_FIELDS = (
    "name",
    "roi_positions",
    "fsm_bindings",
    "skill_key_bindings",
    "buff_timer_durations",
    "confidence_thresholds",
    "skill_timing",
)


class ProfileValidationError(ValueError):
    """Raised when an agent profile cannot be loaded or validated."""


def _frame_size(frame: Any) -> tuple[int, int]:
    """Return (height, width) for a 2D or 3D image-like payload."""
    if hasattr(frame, "shape"):
        shape = tuple(frame.shape)
        if len(shape) >= 2:
            return int(shape[0]), int(shape[1])

    if isinstance(frame, (list, tuple)) and frame:
        height = len(frame)
        first_row = frame[0]
        width = len(first_row) if isinstance(first_row, (list, tuple)) else 0
        return height, width

    raise ProfileValidationError("frame must expose a 2D image shape for ROI extraction")


def validate_roi_positions(
    roi_positions: dict[str, Any] | Any,
    width: int,
    height: int,
) -> dict[str, tuple[int, int, int, int]]:
    """Validate ROI coordinates against a frame size and return normalized values."""
    if not isinstance(roi_positions, dict):
        raise ProfileValidationError(f"roi_positions must be a mapping, got {type(roi_positions).__name__}")

    normalized: dict[str, tuple[int, int, int, int]] = {}
    for name, raw_rect in roi_positions.items():
        if not isinstance(raw_rect, (list, tuple)) or len(raw_rect) != 4:
            raise ProfileValidationError(f"ROI '{name}' must be a 4-value tuple/list: {raw_rect!r}")

        try:
            x1, y1, x2, y2 = (int(value) for value in raw_rect)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive validation
            raise ProfileValidationError(f"ROI '{name}' contains non-integer coordinates: {raw_rect!r}") from exc

        if x1 < 0 or y1 < 0 or x2 < 0 or y2 < 0:
            raise ProfileValidationError(f"ROI '{name}' has negative coordinates: {(x1, y1, x2, y2)}")
        if x2 <= x1 or y2 <= y1:
            raise ProfileValidationError(f"ROI '{name}' must have x2 > x1 and y2 > y1: {(x1, y1, x2, y2)}")
        if x2 > width or y2 > height:
            raise ProfileValidationError(
                f"ROI '{name}' out of bounds for frame size {width}x{height}: {(x1, y1, x2, y2)}"
            )

        normalized[name] = (x1, y1, x2, y2)

    return normalized


def extract_roi_map(frame: Any, profile: AgentProfile | Any, *, width: int | None = None, height: int | None = None) -> dict[str, Any]:
    """Extract every named ROI from a frame using the active agent profile."""
    if hasattr(profile, "roi_positions"):
        roi_positions = profile.roi_positions
    elif isinstance(profile, dict):
        roi_positions = profile
    else:
        raise ProfileValidationError(f"unsupported profile object: {type(profile).__name__}")

    if width is None or height is None:
        height, width = _frame_size(frame)

    validated = validate_roi_positions(roi_positions, width=width, height=height)

    extracted: dict[str, Any] = {}
    for name, (x1, y1, x2, y2) in validated.items():
        if hasattr(frame, "__getitem__") and hasattr(frame, "shape"):
            extracted[name] = frame[y1:y2, x1:x2]
            continue

        extracted[name] = [row[x1:x2] for row in frame[y1:y2]]

    return extracted


def load_profile(
    profile_class: str,
    profiles_dir: Path | str | None = None,
    *,
    width: int | None = None,
    height: int | None = None,
) -> AgentProfile:
    """Read and validate one profile from disk without applying defaults."""
    profile_dir = Path(profiles_dir) if profiles_dir is not None else Path(__file__).parents[2] / "profiles"
    profile_path = profile_dir / f"{profile_class}.yaml"

    if not profile_path.is_file():
        raise ProfileValidationError(f"profile file not found: {profile_path}")

    raw_text = profile_path.read_text(encoding="utf-8")
    top_level_keys = {
        match.group(1)
        for line in raw_text.splitlines()
        if line and not line.startswith(" ") and not line.startswith("\t") and not line.lstrip().startswith("#")
        for match in [re.match(r"^([A-Za-z0-9_]+)\s*:", line.strip())]
        if match is not None and not line.lstrip().startswith("- ")
    }
    missing = [field for field in REQUIRED_PROFILE_FIELDS if field not in top_level_keys]
    if missing:
        fields = ", ".join(missing)
        raise ProfileValidationError(f"profile missing required field(s): {fields}")

    try:
        data: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as error:
        raise ProfileValidationError(f"invalid YAML in {profile_path}: {error}") from error

    if not isinstance(data, dict):
        raise ProfileValidationError("profile: expected a YAML mapping")

    missing = [field for field in REQUIRED_PROFILE_FIELDS if field not in data]
    if missing:
        fields = ", ".join(missing)
        raise ProfileValidationError(f"profile missing required field(s): {fields}")

    try:
        profile = AgentProfile.model_validate(data)
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
        raise ProfileValidationError(f"profile validation failed: {details}") from error

    if width is not None or height is not None:
        if width is None or height is None:
            raise ProfileValidationError("both width and height must be provided together for ROI validation")
        validate_roi_positions(profile.roi_positions, width=width, height=height)

    return profile