"""lagent.agent - decision engine and behavior orchestration."""

from lagent.agent.profile import ProfileValidationError, load_profile


def main() -> None:
	"""Console-script compatibility wrapper."""
	from lagent.agent.__main__ import main as run_agent

	run_agent()

__all__ = ["ProfileValidationError", "load_profile"]
