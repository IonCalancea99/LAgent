import logging

import lagent.agent.__main__ as agent_main
from lagent.agent.startup import CharacterIdentifier, StartupProfileResolver
from lagent.common import Detection, PerceptionResult


def test_high_confidence_skill_fingerprint_assigns_warlord():
    identifier = CharacterIdentifier()

    result = identifier.identify(
        PerceptionResult(
            detections=[Detection(class_name="warlord_skill", confidence=0.82, bbox_xyxy=(1, 2, 3, 4))]
        )
    )

    assert result.profile_class == "warlord"
    assert result.confidence == 0.82
    assert result.is_confident


def test_low_confidence_identification_requires_manual_selection(caplog):
    identifier = CharacterIdentifier()
    resolver = StartupProfileResolver(identifier=identifier, profile_loader=lambda profile_class: profile_class)

    with caplog.at_level(logging.INFO):
        assignment = resolver.resolve(
            scan=lambda: PerceptionResult(
                detections=[Detection(class_name="warlord_skill", confidence=0.5, bbox_xyxy=(1, 2, 3, 4))]
            ),
            confirm=lambda result: "prophet",
        )

    assert assignment.profile == "prophet"
    assert assignment.manual_fallback
    assert "manual fallback" in caplog.text


def test_explicit_override_skips_scanning():
    calls = []
    resolver = StartupProfileResolver(profile_loader=lambda profile_class: profile_class)

    assignment = resolver.resolve(override="warlord", scan=lambda: calls.append(True))

    assert assignment.profile == "warlord"
    assert assignment.explicit_override
    assert calls == []


def test_equal_confidence_fingerprints_require_manual_selection():
    identifier = CharacterIdentifier()

    result = identifier.identify(
        PerceptionResult(
            detections=[
                Detection(class_name="warlord_skill", confidence=0.8, bbox_xyxy=(1, 2, 3, 4)),
                Detection(class_name="prophet_skill", confidence=0.8, bbox_xyxy=(5, 6, 7, 8)),
            ]
        )
    )

    assert result.profile_class is None
    assert not result.is_confident


def test_invalid_manual_selection_is_retried():
    selections = iter(("unknown", "prophet"))
    resolver = StartupProfileResolver(
        identifier=CharacterIdentifier(),
        profile_loader=lambda profile_class: profile_class,
    )

    assignment = resolver.resolve(
        scan=lambda: [],
        confirm=lambda result: next(selections),
    )

    assert assignment.profile == "prophet"


def test_manual_assignment_is_recorded_in_session_db():
    class FakeDB:
        def __init__(self):
            self.events = []

        def append_event(self, session_id, source, event_type, payload):
            self.events.append((session_id, source, event_type, payload))

    db = FakeDB()
    resolver = StartupProfileResolver(identifier=CharacterIdentifier(), profile_loader=lambda value: value)
    assignment = resolver.resolve(
        session_id="session-42",
        db=db,
        scan=lambda: [],
        confirm=lambda result: "prophet",
    )

    assert assignment.profile == "prophet"
    assert db.events[0][2] == "character_identification"
    assert db.events[0][3]["fallback"] == "manual"
    assert db.events[0][3]["chosen_profile"] == "prophet"


def test_main_passes_session_context_to_profile_resolver(monkeypatch):
    class FakeProfile:
        name = "warlord"

    class FakeAssignment:
        def __init__(self):
            self.profile = FakeProfile()
            self.profile_class = "warlord"
            self.identification = None
            self.manual_fallback = False
            self.explicit_override = False

    captured = {}

    class FakeDB:
        def __init__(self, *_args, **_kwargs):
            self.events = []

        def log_session_start(self, **_kwargs):
            return None

        def append_event(self, *args, **kwargs):
            self.events.append((args, kwargs))

        def close(self):
            return None

    monkeypatch.setattr("sys.argv", ["lagent", "--window-title", "Test Window", "--gpu-endpoint", "http://example"])
    monkeypatch.setattr(agent_main, "SessionsDB", FakeDB)

    def fake_resolve(self, **kwargs):
        captured.update(kwargs)
        return FakeAssignment()

    monkeypatch.setattr(agent_main.StartupProfileResolver, "resolve", fake_resolve)
    monkeypatch.setattr(agent_main, "scan_window", lambda *args, **kwargs: agent_main.PerceptionResult())

    agent_main.main()

    assert captured["session_id"] is not None
    assert captured["db"] is not None
    assert captured["override"] is None