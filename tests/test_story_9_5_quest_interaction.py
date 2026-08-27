"""Acceptance tests for Story 9.5: bounded Marcela interaction."""

from lagent.agent.quest.dialogue import DialogueSelector
from lagent.agent.quest.interactions import InteractionStatus, QuestInteractionController
from lagent.common import (
    Action,
    DialogueChoice,
    ObjectiveStep,
    QuestPerceptionEvidence,
    QuestPerceptionStatus,
    QuestResource,
)


class FakeHSL:
    def __init__(self):
        self.actions = []

    def dispatch_action(self, action):
        self.actions.append(action)
        return action


class EventDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def make_resource(retries=2):
    return QuestResource(
        quest_id="marcela_supply_check",
        quest_name="Supply Check",
        starting_npc="Marcela",
        objective_sequence=[
            ObjectiveStep(
                order=1,
                id="talk_marcela",
                name="Speak to Marcela",
                target_npc="Marcela",
                type="dialogue",
                dialogue_choice="supply_check",
            )
        ],
        dialogue_options=[
            DialogueChoice(key="supply_check", text="I am here for the supply check."),
            DialogueChoice(key="leave", text="Maybe later."),
        ],
        navigation_route=["marcela_steps"],
        timeouts={"dialogue": 30.0},
        retries={"dialogue": retries},
        safe_stop_conditions=["npc_not_found", "ambiguous_dialogue"],
    )


def evidence(evidence_type, *, status=QuestPerceptionStatus.FOUND, confidence=0.95, raw=None, observed=None, choice=None):
    return QuestPerceptionEvidence(
        quest_id="marcela_supply_check",
        evidence_type=evidence_type,
        status=status,
        confidence=confidence,
        raw_ocr_text=raw,
        observed_value=observed,
        selected_dialogue_key=choice,
    )


def make_controller(*, retries=2, clock=lambda: 0.0, db=None):
    hsl = FakeHSL()
    controller = QuestInteractionController(
        make_resource(retries),
        hsl=hsl,
        interaction_action=Action(action_type="key_press", key="f"),
        dialogue_positions={"supply_check": (510, 420), "leave": (510, 460)},
        session_id="session-9",
        db=db,
        objective_index=0,
        clock=clock,
    )
    return controller, hsl


def test_successful_interaction_and_resource_validated_dialogue_choice_use_hsl():
    controller, hsl = make_controller()
    npc = evidence("npc", observed="Marcela")
    prompt = evidence("interaction_prompt", raw="Talk to Marcela")

    interaction = controller.begin_interaction(npc, prompt)
    selection = controller.select_dialogue(
        npc,
        evidence("objective", raw="Supply Check: Speak to Marcela"),
        evidence("dialogue", raw="I am here for the supply check.", choice="supply_check"),
    )

    assert interaction.event_type == "interaction_verified"
    assert interaction.action.key == "f"
    assert selection.event_type == "objective_verified"
    assert selection.action == Action(action_type="mouse_click", x=510, y=420, button="left", clicks=1)
    assert hsl.actions == [interaction.action, selection.action]
    assert controller.status is InteractionStatus.COMPLETE


def test_absent_or_wrong_npc_never_dispatches_interaction():
    controller, hsl = make_controller()
    missing = evidence("npc", status=QuestPerceptionStatus.NOT_FOUND, confidence=0.0)

    result = controller.begin_interaction(missing, evidence("interaction_prompt"))

    assert result.action is None
    assert result.failure_reason == "npc_not_found"
    assert hsl.actions == []


def test_dialogue_selector_rejects_low_confidence_ambiguous_and_mismatched_context():
    selector = DialogueSelector(make_resource(), confidence_threshold=0.8)
    npc = evidence("npc", observed="Marcela")
    objective = evidence("objective", raw="Supply Check: Speak to Marcela")

    low = selector.select(npc, objective, evidence("dialogue", confidence=0.4, raw="I am here for the supply check.", choice="supply_check"))
    wrong_npc = selector.select(evidence("npc", observed="Mira"), objective, evidence("dialogue", raw="I am here for the supply check.", choice="supply_check"))
    wrong_objective = selector.select(npc, evidence("objective", raw="Unrelated quest"), evidence("dialogue", raw="I am here for the supply check.", choice="supply_check"))

    assert low.failure_reason == "ambiguous_dialogue"
    assert wrong_npc.failure_reason == "npc_mismatch"
    assert wrong_objective.failure_reason == "objective_mismatch"
    assert low.choice is None and wrong_npc.choice is None and wrong_objective.choice is None


def test_retry_exhaustion_safe_stops_and_preserves_trace_in_telemetry():
    database = EventDB()
    controller, hsl = make_controller(retries=2, db=database)
    missing = evidence("npc", status=QuestPerceptionStatus.NOT_FOUND, confidence=0.0)

    first = controller.begin_interaction(missing, evidence("interaction_prompt"))
    second = controller.begin_interaction(missing, evidence("interaction_prompt"))

    assert first.terminal is False
    assert second.terminal is True
    assert controller.status is InteractionStatus.SAFE_STOP
    assert hsl.actions == []
    _, _, event_type, payload = database.events[-1]
    assert event_type == "quest_interaction_failure"
    assert payload["session_id"] == "session-9"
    assert payload["objective_index"] == 0
    assert payload["reason"] == "npc_not_found_retry_exhausted"
    assert payload["retries_remaining"] == 0


def test_quest_deadline_stops_retries_with_interaction_timeout():
    now = [0.0]
    controller, hsl = make_controller(retries=3, clock=lambda: now[0])
    now[0] = 31.0

    result = controller.begin_interaction(evidence("npc", observed="Marcela"), evidence("interaction_prompt"))

    assert result.terminal is True
    assert result.failure_reason == "interaction_timeout"
    assert controller.status is InteractionStatus.SAFE_STOP
    assert hsl.actions == []