"""Deterministic Supply Check shadow replay and live acceptance gate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lagent.agent.quest.checkpoint import QuestCheckpointManager
from lagent.agent.quest.fsm import QuestFSM
from lagent.agent.quest.interactions import QuestInteractionController
from lagent.agent.quest.navigation import QuestNavigator, Waypoint
from lagent.agent.quest.state import QuestEvent, QuestState
from lagent.common import (
    Action,
    DialogueChoice,
    ObjectiveStep,
    QuestPerceptionEvidence,
    QuestPerceptionStatus,
    QuestResource,
)
from lagent.gpu_server.quest_fixture import SupplyCheckFixtureEvaluator, load_supply_check_fixture


_FIXTURE_PATH = Path(__file__).with_name("fixtures") / "supply_check_acceptance.json"


def build_supply_check_resource() -> QuestResource:
    return QuestResource(
        quest_id="marcela_supply_check",
        quest_name="Supply Check",
        starting_npc="Marcela",
        objective_sequence=[
            ObjectiveStep(order=1, id="talk_marcela", name="Speak to Marcela", target_npc="Marcela", type="dialogue", dialogue_choice="supply_check", retry_limit=2),
            ObjectiveStep(order=2, id="confirm_supply", name="Confirm supply", target_npc="Marcela", type="dialogue", dialogue_choice="supply_check", retry_limit=2),
        ],
        dialogue_options=[DialogueChoice(key="supply_check", text="I am here for the supply check.")],
        navigation_route=["marcela_platform"],
        timeouts={"travel": 10.0, "dialogue": 30.0},
        retries={"travel": 2, "dialogue": 2, "default": 2},
        safe_stop_conditions=["npc_not_found", "route_stuck", "ambiguous_dialogue"],
        completion_indicators=["quest_complete"],
    )


def load_supply_check_acceptance_fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _fingerprint(resource: QuestResource, profile_id: str) -> str:
    payload = {"profile_id": profile_id, "resource": resource.model_dump(mode="json")}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ReplayResult:
    success: bool
    terminal_state: str
    verified_objectives: list[int]
    completion_evidence: bool
    failure_reason: str | None
    validation_fingerprint: str


@dataclass(frozen=True)
class LiveGateDecision:
    allowed: bool
    reason: str


class LiveQuestGate:
    def validate(self, resource: QuestResource, profile_id: str, shadow_result: ReplayResult) -> LiveGateDecision:
        if not shadow_result.success:
            return LiveGateDecision(False, "shadow_validation_failed")
        if shadow_result.validation_fingerprint != _fingerprint(resource, profile_id):
            return LiveGateDecision(False, "shadow_contract_mismatch")
        return LiveGateDecision(True, "shadow_validation_passed")


class SupplyCheckReplayHarness:
    """Replay the bounded flow through the actual quest components."""

    def __init__(self, resource: QuestResource, *, profile_id: str, hsl: Any, db: Any, session_id: str) -> None:
        if not getattr(hsl, "shadow", False):
            raise ValueError("acceptance replay requires shadow HSL")
        self.resource = resource
        self.profile_id = profile_id
        self.hsl = hsl
        self.db = db
        self.session_id = session_id
        self.evaluator = SupplyCheckFixtureEvaluator()

    def _result(self, success: bool, state: str, verified: list[int], completion: bool = False, reason: str | None = None) -> ReplayResult:
        return ReplayResult(success, state, list(verified), completion, reason, _fingerprint(self.resource, self.profile_id))

    def _fail(self, checkpoints: QuestCheckpointManager, reason: str, objective_index: int, verified: list[int], state: str = "safe_stop") -> ReplayResult:
        checkpoints.log_failure(reason, objective_index=objective_index, retry_count=1)
        return self._result(False, state, verified, reason=reason)

    def run(self, fixture: dict[str, Any]) -> ReplayResult:
        fsm = QuestFSM(self.resource, session_id=self.session_id, db=self.db)
        checkpoints = QuestCheckpointManager(self.db, self.session_id, self.resource)
        verified: list[int] = []
        event_sequence = 1
        previous_fixture_sequence = -1
        fsm.handle(QuestEvent("resource", event_sequence, "resource_validated", 0))

        for objective_index, replay_step in enumerate(fixture.get("objectives", [])):
            fixture_sequence = replay_step.get("sequence")
            if not isinstance(fixture_sequence, int) or fixture_sequence <= previous_fixture_sequence:
                return self._fail(checkpoints, "stale_evidence", objective_index, verified)
            previous_fixture_sequence = fixture_sequence

            navigator = QuestNavigator(
                self.resource,
                {"marcela_platform": Waypoint("marcela_platform", "marcela_platform", Action(action_type="key_press", key="w"), "Marcela")},
                hsl=self.hsl,
                session_id=self.session_id,
                db=self.db,
                objective_index=objective_index,
            )
            navigator.dispatch_current()
            if not navigator.verify_position(area="marcela_platform", npc="Marcela"):
                return self._fail(checkpoints, navigator.failure_reason or "navigation_failed", objective_index, verified, navigator.status.value)
            event_sequence += 1
            fsm.handle(QuestEvent(f"navigation-{objective_index}", event_sequence, "navigation_verified", objective_index))

            npc = self.evaluator.evaluate(load_supply_check_fixture(replay_step["npc_fixture"]))
            prompt = self.evaluator.evaluate(load_supply_check_fixture(replay_step["prompt_fixture"]))
            interaction = QuestInteractionController(
                self.resource,
                hsl=self.hsl,
                interaction_action=Action(action_type="key_press", key="f"),
                dialogue_positions={"supply_check": (510, 420)},
                session_id=self.session_id,
                db=self.db,
                objective_index=objective_index,
            )
            interaction_outcome = interaction.begin_interaction(npc, prompt)
            if interaction_outcome.action is None:
                return self._fail(checkpoints, interaction_outcome.failure_reason or "interaction_failed", objective_index, verified, interaction.status.value)
            event_sequence += 1
            fsm.handle(QuestEvent(f"interaction-{objective_index}", event_sequence, "interaction_verified", objective_index))

            objective = QuestPerceptionEvidence(
                quest_id=self.resource.quest_id,
                evidence_type="objective",
                status=QuestPerceptionStatus.FOUND,
                confidence=0.99,
                raw_ocr_text=replay_step["objective_text"],
            )
            dialogue = self.evaluator.evaluate(load_supply_check_fixture(replay_step["dialogue_fixture"]))
            dialogue_outcome = interaction.select_dialogue(npc, objective, dialogue)
            if dialogue_outcome.action is None:
                return self._fail(checkpoints, dialogue_outcome.failure_reason or "ambiguous_dialogue", objective_index, verified, interaction.status.value)

            completion = self.evaluator.evaluate(load_supply_check_fixture(replay_step["completion_fixture"]))
            if completion.status is not QuestPerceptionStatus.FOUND:
                return self._fail(checkpoints, "completion_verify_failed", objective_index, verified)
            event_sequence += 1
            fsm.handle(QuestEvent(f"objective-{objective_index}", event_sequence, "objective_verified", objective_index, completion))
            checkpoints.checkpoint_objective(objective_index, verification_source="shadow_replay", evidence=completion)
            verified.append(objective_index)

        final_completion = bool(verified) and completion.evidence_type == "completion" and completion.safe_terminal
        success = fsm.state is QuestState.COMPLETE and final_completion
        return self._result(success, fsm.state.value if success else "safe_stop", verified, final_completion, None if success else "completion_verify_failed")