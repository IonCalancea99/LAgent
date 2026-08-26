"""lagent.agent - decision engine and behavior orchestration."""

from lagent.agent.profile import (
    ProfileValidationError,
    extract_roi_map,
    load_profile,
    validate_roi_positions,
)
from lagent.agent.inference import InferenceClient, PolicyQueue, frame_to_bytes
from lagent.agent.startup import (
    CharacterIdentifier,
    IdentificationResult,
    ProfileAssignment,
    StartupProfileResolver,
    scan_window,
)
from lagent.agent.fishing_fsm import FishingFSM
from lagent.agent.loop import AgentLoop


def main() -> None:
	"""Console-script compatibility wrapper."""
	from lagent.agent.__main__ import main as run_agent

	run_agent()

__all__ = [
    "InferenceClient",
    "PolicyQueue",
    "ProfileValidationError",
    "extract_roi_map",
    "frame_to_bytes",
    "load_profile",
    "CharacterIdentifier",
    "IdentificationResult",
    "ProfileAssignment",
    "StartupProfileResolver",
    "scan_window",
    "validate_roi_positions",
]
