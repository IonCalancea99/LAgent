"""Deterministic Supply Check perception fixture evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from lagent.common import QuestPerceptionEvidence, QuestPerceptionStatus


_FIXTURE_PATH = Path(__file__).with_name("supply_check_fixtures.json")
_QUEST_ID = "marcela_supply_check"


def load_supply_check_fixture(name: str) -> dict[str, Any]:
    """Load one named replay fixture from the immutable fixture set."""

    fixtures = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    try:
        fixture = fixtures[name]
    except KeyError as exc:
        raise ValueError(f"unknown Supply Check fixture: {name}") from exc
    return dict(fixture)


class SupplyCheckFixtureEvaluator:
    """Normalize replayed inference/OCR values into canonical quest evidence."""

    def __init__(self, confidence_threshold: float = 0.8) -> None:
        if not 0.0 < confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be in (0, 1]")
        self.confidence_threshold = confidence_threshold

    def evaluate(self, fixture: Mapping[str, Any]) -> QuestPerceptionEvidence:
        evidence_type = str(fixture.get("evidence_type", ""))
        confidence = float(fixture.get("confidence", 0.0))
        common = {
            "quest_id": _QUEST_ID,
            "evidence_type": evidence_type,
            "confidence": confidence,
        }

        if evidence_type == "npc":
            target = str(fixture.get("target", ""))
            if not target:
                status = QuestPerceptionStatus.NOT_FOUND
            elif fixture.get("occluded") or confidence < self.confidence_threshold:
                status = QuestPerceptionStatus.AMBIGUOUS
            else:
                status = QuestPerceptionStatus.FOUND if target.casefold() == "marcela" else QuestPerceptionStatus.NOT_FOUND
            return QuestPerceptionEvidence(status=status, observed_value=target or None, **common)

        if evidence_type in {"objective", "interaction_prompt"}:
            raw_text = str(fixture.get("raw_ocr_text", ""))
            expected_text = str(fixture.get("expected_text", ""))
            if fixture.get("occluded") or confidence < self.confidence_threshold:
                status = QuestPerceptionStatus.AMBIGUOUS
            elif raw_text and expected_text.casefold() in raw_text.casefold():
                status = QuestPerceptionStatus.FOUND
            else:
                status = QuestPerceptionStatus.NOT_FOUND
            return QuestPerceptionEvidence(status=status, raw_ocr_text=raw_text or None, **common)

        if evidence_type == "dialogue":
            raw_text = str(fixture.get("raw_ocr_text", ""))
            choice_key = fixture.get("choice_key")
            verified = (
                not fixture.get("occluded")
                and confidence >= self.confidence_threshold
                and choice_key == "supply_check"
                and "supply check" in raw_text.casefold()
            )
            return QuestPerceptionEvidence(
                status=QuestPerceptionStatus.FOUND if verified else QuestPerceptionStatus.VERIFY_FAILED,
                raw_ocr_text=raw_text or None,
                selected_dialogue_key=choice_key if verified else None,
                **common,
            )

        if evidence_type == "completion":
            raw_text = str(fixture.get("raw_ocr_text", ""))
            transitioned = fixture.get("objective_transition") is True
            explicit = fixture.get("explicit_completion") is True and "complete" in raw_text.casefold()
            verified = transitioned and explicit and confidence >= self.confidence_threshold
            return QuestPerceptionEvidence(
                status=QuestPerceptionStatus.FOUND if verified else QuestPerceptionStatus.VERIFY_FAILED,
                raw_ocr_text=raw_text or None,
                objective_transition=transitioned,
                safe_terminal=verified,
                **common,
            )

        return QuestPerceptionEvidence(status=QuestPerceptionStatus.NOT_FOUND, **common)