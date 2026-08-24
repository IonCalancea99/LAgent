"""YAML profile loading and startup validation."""

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
)


class ProfileValidationError(ValueError):
    """Raised when an agent profile cannot be loaded or validated."""


def load_profile(profile_class: str, profiles_dir: Path | str | None = None) -> AgentProfile:
    """Read and validate one profile from disk without applying defaults."""
    profile_dir = Path(profiles_dir) if profiles_dir is not None else Path(__file__).parents[2] / "profiles"
    profile_path = profile_dir / f"{profile_class}.yaml"

    if not profile_path.is_file():
        raise ProfileValidationError(f"profile file not found: {profile_path}")

    try:
        data: Any = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ProfileValidationError(f"invalid YAML in {profile_path}: {error}") from error

    if not isinstance(data, dict):
        raise ProfileValidationError("profile: expected a YAML mapping")

    missing = [field for field in REQUIRED_PROFILE_FIELDS if field not in data]
    if missing:
        fields = ", ".join(missing)
        raise ProfileValidationError(f"profile missing required field(s): {fields}")

    try:
        return AgentProfile.model_validate(data)
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
        raise ProfileValidationError(f"profile validation failed: {details}") from error