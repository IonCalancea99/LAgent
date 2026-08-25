"""lagent.agent - decision engine and behavior orchestration."""

from lagent.agent.profile import (
    ProfileValidationError,
    extract_roi_map,
    load_profile,
    validate_roi_positions,
)


def main() -> None:
	"""Console-script compatibility wrapper."""
	from lagent.agent.__main__ import main as run_agent

	run_agent()

__all__ = ["ProfileValidationError", "load_profile", "validate_roi_positions", "extract_roi_map"]
