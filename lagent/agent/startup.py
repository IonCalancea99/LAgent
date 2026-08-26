"""Startup character identification and profile assignment."""

from __future__ import annotations

import logging
import queue
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from lagent.agent.capture import CaptureThread
from lagent.agent.inference import frame_to_bytes
from lagent.common import Detection, PerceptionResult
from lagent.common.transport import AgentTransport

logger = logging.getLogger(__name__)
SUPPORTED_PROFILES = ("warlord", "prophet", "fishing")


@dataclass(frozen=True)
class IdentificationResult:
    """Class fingerprint and confidence produced by the startup scan."""

    profile_class: str | None
    confidence: float
    detection_count: int = 0
    threshold: float = 0.75

    @property
    def is_confident(self) -> bool:
        return self.profile_class is not None and self.confidence >= self.threshold


@dataclass(frozen=True)
class ProfileAssignment:
    """Profile selected for the current agent session."""

    profile: Any
    profile_class: str
    identification: IdentificationResult | None
    explicit_override: bool = False
    manual_fallback: bool = False


class CharacterIdentifier:
    """Identify a character from class-specific skill-bar detections."""

    def __init__(self, *, threshold: float = 0.75, profiles: Iterable[str] = SUPPORTED_PROFILES) -> None:
        self.threshold = threshold
        self.profiles = tuple(profiles)

    def identify(self, perception: PerceptionResult | Iterable[Detection]) -> IdentificationResult:
        detections = perception.detections if isinstance(perception, PerceptionResult) else list(perception)
        scores = {
            profile: max(
                (detection.confidence for detection in detections if self._matches(detection, profile)),
                default=0.0,
            )
            for profile in self.profiles
        }
        profile_class, confidence = max(scores.items(), key=lambda item: item[1], default=(None, 0.0))
        top_profiles = [profile for profile, score in scores.items() if score == confidence and score > 0.0]
        if len(top_profiles) > 1:
            profile_class = None
        if confidence == 0.0:
            profile_class = None
        return IdentificationResult(profile_class, confidence, len(detections), self.threshold)

    @staticmethod
    def _matches(detection: Detection, profile: str) -> bool:
        name = detection.class_name.lower()
        return profile.lower() in name and "skill" in name


class StartupProfileResolver:
    """Resolve an explicit, automatic, or operator-confirmed startup profile."""

    def __init__(
        self,
        *,
        identifier: CharacterIdentifier | None = None,
        profile_loader: Callable[[str], Any] | None = None,
    ) -> None:
        self.identifier = identifier or CharacterIdentifier()
        if profile_loader is None:
            from lagent.agent.profile import load_profile

            profile_loader = load_profile
        self.profile_loader = profile_loader

    def resolve(
        self,
        *,
        override: str | None = None,
        scan: Callable[[], PerceptionResult | Iterable[Detection]] | None = None,
        confirm: Callable[[IdentificationResult], str] | None = None,
        session_id: str | None = None,
        db: Any | None = None,
    ) -> ProfileAssignment:
        if override is not None:
            self._validate_profile(override)
            logger.info("Profile override selected explicitly: %s", override)
            return ProfileAssignment(self.profile_loader(override), override, None, explicit_override=True)
        if scan is None:
            raise ValueError("a startup scan is required when --class is not provided")

        identification = self.identifier.identify(scan())
        if identification.is_confident:
            selected = identification.profile_class
            logger.info("Startup identification: %s (confidence=%.3f)", selected, identification.confidence)
            self._record(db, session_id, identification, selected, "automatic")
            return ProfileAssignment(self.profile_loader(selected), selected, identification)

        logger.warning(
            "Startup identification below threshold: %s (confidence=%.3f); manual fallback required",
            identification.profile_class or "unknown",
            identification.confidence,
        )
        if confirm is None:
            raise RuntimeError("startup identification is ambiguous; manual profile confirmation is required")
        while True:
            selected = confirm(identification)
            try:
                self._validate_profile(selected)
                break
            except ValueError:
                logger.warning("Unsupported profile '%s'; manual confirmation required", selected)
        self._record(db, session_id, identification, selected, "manual")
        return ProfileAssignment(self.profile_loader(selected), selected, identification, manual_fallback=True)

    def _record(self, db: Any | None, session_id: str | None, result: IdentificationResult, selected: str, fallback: str) -> None:
        if db is not None and session_id is not None:
            db.append_event(
                session_id,
                "agent",
                "character_identification",
                {
                    "detected_profile": result.profile_class,
                    "confidence": result.confidence,
                    "threshold": result.threshold,
                    "chosen_profile": selected,
                    "fallback": fallback,
                },
            )

    @staticmethod
    def _validate_profile(profile_class: str) -> None:
        if profile_class not in SUPPORTED_PROFILES:
            raise ValueError(f"unsupported profile class: {profile_class}")


def scan_window(
    window_title: str,
    *,
    endpoint: str,
    fps: int = 10,
    timeout: float = 0.5,
) -> PerceptionResult:
    """Capture one frame and run it through each class model for fingerprinting."""
    capture = CaptureThread(window_title, fps=fps, max_queue_size=1)
    transports = [AgentTransport(profile, endpoint=endpoint) for profile in SUPPORTED_PROFILES]
    try:
        capture.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                frame = capture.frame_queue.get_nowait()
                break
            except queue.Empty:
                time.sleep(0.01)
        else:
            raise TimeoutError(f"startup scan timed out waiting for window: {window_title}")

        results: list[PerceptionResult] = []
        try:
            encoded = frame_to_bytes(frame.frame)
            for transport in transports:
                transport.connect()
                try:
                    results.append(transport.request_inference(encoded, {}, timeout=timeout).result)
                finally:
                    transport.close()
        finally:
            capture.frame_queue.task_done()
        detections = [detection for result in results for detection in result.detections]
        return PerceptionResult(detections=detections)
    finally:
        capture.stop()
        capture.join(timeout=1.0)


__all__ = ["CharacterIdentifier", "IdentificationResult", "ProfileAssignment", "StartupProfileResolver"]