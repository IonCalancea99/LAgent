"""Tests for Story 6.4: Inventory-Full Detection and Town Return"""

from lagent.common import Action, Detection, PerceptionResult
from lagent.agent.lifecycle import detect_lifecycle_signal, InventoryReturnController, LifecycleSignal
from lagent.agent.warlord import WarlordCombatFSM


def fake_profile(return_actions=None, deposit_rules=None, drop_rules=None):
    """Create a fake profile with inventory return configuration."""
    return {
        "name": "warlord",
        "roi_positions": {},
        "fsm_bindings": {
            "pulling": {"frame_center": (500, 500), "melee_tolerance": 75.0},
            "looting": {"loot_timeout": 5.0},
        },
        "skill_key_bindings": {"pull": "1", "aoe": "2", "loot": "3"},
        "buff_timer_durations": {},
        "recovery": {"actions": []},
        "inventory": {
            "return_actions": return_actions or [
                {"action_type": "key_press", "key": "t"},
                {"action_type": "key_press", "key": "enter"},
            ],
            "deposit": deposit_rules or ["materials", "crafting"],
            "drop": drop_rules or ["junk", "trash"],
        },
        "aggro_risk_radius": 150.0,
        "retry_interval": 1.0,
    }


def fake_perception(detections=None, ocr_values=None):
    """Create a fake PerceptionResult."""
    if detections is None:
        detections = []
    if ocr_values is None:
        ocr_values = {}
    return PerceptionResult(detections=detections, ocr_values=ocr_values)


class FakeSessionDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def test_detect_inventory_full_signal_from_detections():
    """AC-1: Inventory-full signal detection from YOLO detections."""
    perception = PerceptionResult(
        detections=[Detection(class_name="inventory_full", confidence=0.9, bbox_xyxy=(0, 0, 100, 100))],
        ocr_values={},
    )
    signal = detect_lifecycle_signal(perception)
    assert signal is not None
    assert signal.name == "inventory_full"
    assert isinstance(signal.timestamp, float)


def test_detect_inventory_full_signal_from_ocr():
    """AC-1: Inventory-full signal detection from OCR values."""
    perception = PerceptionResult(
        detections=[],
        ocr_values={"inventory_full": "detected"},
    )
    signal = detect_lifecycle_signal(perception)
    assert signal is not None
    assert signal.name == "inventory_full"


def test_warlord_detects_inventory_full_and_transitions_to_returning():
    """AC-2: WL transitions to RETURNING and suspends combat."""
    profile = fake_profile()
    db = FakeSessionDB()
    
    wl = WarlordCombatFSM(profile=profile, session_id="test-session", db=db)
    
    # Start in FIGHTING state
    wl.state = "FIGHTING"
    inventory_full_perception = PerceptionResult(
        detections=[Detection(class_name="inventory_full", confidence=0.9, bbox_xyxy=(0, 0, 100, 100))],
        ocr_values={},
    )
    
    action = wl(inventory_full_perception, "FIGHTING")
    assert wl.state == "RETURNING"
    assert wl.inventory_return.state == "RETURNING"


def test_return_actions_dispatched_in_order():
    """AC-3: Town navigation action sequence dispatched in order."""
    return_actions = [
        {"action_type": "key_press", "key": "t"},
        {"action_type": "wait", "duration": 1.0},
        {"action_type": "key_press", "key": "enter"},
    ]
    profile = fake_profile(return_actions=return_actions)
    db = FakeSessionDB()
    
    wl = WarlordCombatFSM(profile=profile, session_id="test-session", db=db)
    
    inventory_full_perception = PerceptionResult(
        detections=[Detection(class_name="inventory_full", confidence=0.9, bbox_xyxy=(0, 0, 100, 100))],
        ocr_values={},
    )
    
    # Trigger inventory-full
    action1 = wl(inventory_full_perception, "IDLE")
    assert action1 is not None
    assert action1.action_type == "key_press"
    assert action1.key == "t"
    
    # Next action
    action2 = wl(inventory_full_perception, "RETURNING")
    assert action2 is not None
    assert action2.action_type == "wait"
    
    # Final action
    action3 = wl(inventory_full_perception, "RETURNING")
    assert action3 is not None
    assert action3.action_type == "key_press"
    assert action3.key == "enter"


def test_deposit_and_drop_rules_honored():
    """AC-4: Loot disposition rules are honored; no silent discard."""
    profile = fake_profile(
        deposit_rules=["materials", "ore"],
        drop_rules=["junk"],
    )
    db = FakeSessionDB()
    
    controller = InventoryReturnController(profile=profile, session_id="test-session", db=db)
    
    # Test deposit rule
    result = controller.dispose_loot("materials")
    assert result == "deposit"
    
    # Test drop rule
    result = controller.dispose_loot("junk")
    assert result == "drop"
    
    # Test no rule - should retain and log warning
    result = controller.dispose_loot("unknown_item")
    assert result == "retain"
    
    # Check that warning was logged
    warning_events = [e for e in db.events if e[2] == "loot_disposition_blocked"]
    assert len(warning_events) > 0


def test_inventory_return_idempotent_duplicate_signals():
    """AC-7: Duplicate inventory-full signals don't repeat return sequence."""
    profile = fake_profile()
    db = FakeSessionDB()
    
    wl = WarlordCombatFSM(profile=profile, session_id="test-session", db=db)
    
    inventory_full_perception = PerceptionResult(
        detections=[Detection(class_name="inventory_full", confidence=0.9, bbox_xyxy=(0, 0, 100, 100))],
        ocr_values={},
    )
    
    # First inventory-full signal
    action1 = wl(inventory_full_perception, "IDLE")
    assert wl.state == "RETURNING"
    action_count_before = len(wl.inventory_return._actions)
    
    # Second inventory-full signal - should not restart
    action2 = wl(inventory_full_perception, "RETURNING")
    action_count_after = len(wl.inventory_return._actions)
    
    # Action count should have decreased (we consumed one), not reset
    assert action_count_after < action_count_before


def test_resume_combat_after_town_return():
    """AC-6: Resume combat after town handling completes."""
    return_actions = [
        {"action_type": "key_press", "key": "t"},
        {"action_type": "wait", "duration": 1.0},
    ]
    profile = fake_profile(return_actions=return_actions)
    db = FakeSessionDB()
    
    wl = WarlordCombatFSM(profile=profile, session_id="test-session", db=db)
    
    inventory_full_perception = PerceptionResult(
        detections=[Detection(class_name="inventory_full", confidence=0.9, bbox_xyxy=(0, 0, 100, 100))],
        ocr_values={},
    )
    
    # Trigger inventory-full - first action dispatched
    action1 = wl(inventory_full_perception, "IDLE")
    assert action1 is not None
    assert action1.action_type == "key_press"
    
    # Dispatch second action
    action2 = wl(inventory_full_perception, "RETURNING")
    assert action2 is not None
    assert action2.action_type == "wait"
    
    # Call again after return sequence is complete - should return to IDLE
    action3 = wl(inventory_full_perception, "RETURNING")
    assert action3 is None
    assert wl.state == "IDLE"


def test_loot_disposition_events_logged():
    """AC-8: All loot disposition decisions logged."""
    profile = fake_profile(
        deposit_rules=["materials"],
        drop_rules=["junk"],
    )
    db = FakeSessionDB()
    
    controller = InventoryReturnController(profile=profile, session_id="test-session", db=db)
    
    # Dispose of items
    controller.dispose_loot("materials")
    controller.dispose_loot("junk")
    controller.dispose_loot("unknown")
    
    # Check event logs
    disposition_events = [e for e in db.events if e[2] == "loot_disposition"]
    assert len(disposition_events) == 2  # materials and junk
    
    blocked_events = [e for e in db.events if e[2] == "loot_disposition_blocked"]
    assert len(blocked_events) == 1  # unknown


def test_pp_defers_casts_while_wl_is_returning():
    """AC-5: PP defers casts while WL is RETURNING (via lifecycle suppression)."""
    from lagent.agent.prophet import ProphetBuffPolicy
    from lagent.common import GameState, PartyState
    import time
    
    profile = {
        "name": "prophet",
        "buff_timer_durations": {"haste": 1.0},
        "skill_key_bindings": {"buff": "2"},
        "aggro_risk_radius": 150.0,
        "retry_interval": 1.0,
    }
    game_state_provider = lambda _: GameState(
        hp_percent=100.0,
        mp_percent=100.0,
        active_buffs=[],
        character_position=(100, 100),
        ui_mode="combat",
        peer_party_state=PartyState(
            fsm_state="RETURNING",  # WL is RETURNING
            hp_percent=100.0,
            mp_percent=100.0,
            position=(0, 0),
            buff_presence={},
            heartbeat_timestamp=time.time(),
        ),
    )
    
    pp = ProphetBuffPolicy(
        profile=profile,
        game_state_provider=game_state_provider,
    )
    
    # PP in RETURNING state should suppress actions
    action = pp(PerceptionResult(detections=[], ocr_values={}), "RETURNING")
    assert action is None


def test_warlord_pulls_again_after_return():
    """Integration: WL can pull mobs after returning to IDLE."""
    profile = fake_profile()
    db = FakeSessionDB()
    
    wl = WarlordCombatFSM(profile=profile, session_id="test-session", db=db)
    
    # Trigger inventory-full from IDLE
    inventory_full_perception = PerceptionResult(
        detections=[Detection(class_name="inventory_full", confidence=0.9, bbox_xyxy=(0, 0, 100, 100))],
        ocr_values={},
    )
    
    wl(inventory_full_perception, "IDLE")
    assert wl.state == "RETURNING"
    
    # Complete return sequence
    while wl.state == "RETURNING":
        action = wl(inventory_full_perception, wl.state)
        if action is None:
            break
    
    # Should be back in IDLE
    assert wl.state == "IDLE"
    
    # Now should be able to pull mobs
    mob_perception = PerceptionResult(
        detections=[Detection(class_name="mob", confidence=0.9, bbox_xyxy=(400, 400, 600, 600))],
        ocr_values={},
    )
    action = wl(mob_perception, "IDLE")
    assert action is not None
    # Pull action should be returned, but state stays IDLE until next tick
    assert action.action_type == "key_press"
    assert action.key == "1"  # pull key
