"""
Acceptance tests for Story 1.1: Project Scaffold & lagent.common Shared Types

Tests verify:
1. All six types import from lagent.common
2. Each is a Pydantic v2 model
3. Representative construction/serialization works
4. Entry points exit cleanly
5. AD-12: types are not re-exported from other subsystems
"""

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel


class TestSharedTypesImport:
    """AC-1: Shared type import and canonical contracts."""
    
    def test_import_all_six_symbols(self):
        """All six symbols import without error from lagent.common."""
        from lagent.common import (
            GameState,
            PartyState,
            PerceptionResult,
            Detection,
            Action,
            AgentProfile,
        )
        assert GameState is not None
        assert PartyState is not None
        assert PerceptionResult is not None
        assert Detection is not None
        assert Action is not None
        assert AgentProfile is not None
    
    def test_all_are_pydantic_v2_models(self):
        """Each symbol is a Pydantic v2 model."""
        from lagent.common import (
            GameState,
            PartyState,
            PerceptionResult,
            Detection,
            Action,
            AgentProfile,
        )
        for symbol in [GameState, PartyState, PerceptionResult, Detection, Action, AgentProfile]:
            assert issubclass(symbol, BaseModel), f"{symbol.__name__} is not a Pydantic model"


class TestDetectionModel:
    """Validate Detection with required fields: class_name, confidence, bbox_xyxy."""
    
    def test_detection_construction(self):
        """Detection can be constructed with required fields."""
        from lagent.common import Detection
        
        det = Detection(
            class_name="enemy",
            confidence=0.95,
            bbox_xyxy=(100, 200, 300, 400)
        )
        assert det.class_name == "enemy"
        assert det.confidence == 0.95
        assert det.bbox_xyxy == (100, 200, 300, 400)
    
    def test_detection_bbox_uses_frame_pixels(self):
        """bbox_xyxy represents frame pixels with top-left origin."""
        from lagent.common import Detection
        
        # Top-left corner pixel to bottom-right corner
        det = Detection(
            class_name="item",
            confidence=0.8,
            bbox_xyxy=(0, 0, 1920, 1080)
        )
        assert det.bbox_xyxy[0] == 0  # x1 at left
        assert det.bbox_xyxy[1] == 0  # y1 at top
    
    def test_detection_validation(self):
        """Detection validates confidence in [0, 1]."""
        from lagent.common import Detection
        
        # Valid confidence
        Detection(class_name="test", confidence=0.5, bbox_xyxy=(0, 0, 10, 10))
        
        # Invalid confidence should raise
        with pytest.raises(Exception):  # ValidationError
            Detection(class_name="test", confidence=1.5, bbox_xyxy=(0, 0, 10, 10))


class TestPerceptionResultModel:
    """Validate PerceptionResult with detections and OCR values."""
    
    def test_perception_result_construction(self):
        """PerceptionResult contains detections and OCR values."""
        from lagent.common import Detection, PerceptionResult
        
        det1 = Detection(class_name="enemy", confidence=0.9, bbox_xyxy=(10, 20, 100, 120))
        det2 = Detection(class_name="loot", confidence=0.85, bbox_xyxy=(50, 60, 150, 160))
        
        result = PerceptionResult(
            detections=[det1, det2],
            ocr_values={"health_bar": "95%", "mana_bar": "60%"}
        )
        
        assert len(result.detections) == 2
        assert result.ocr_values["health_bar"] == "95%"
    
    def test_perception_result_defaults(self):
        """PerceptionResult has empty lists/dicts by default."""
        from lagent.common import PerceptionResult
        
        result = PerceptionResult()
        assert result.detections == []
        assert result.ocr_values == {}


class TestGameStateModel:
    """Validate GameState with agent-owned game state fields."""
    
    def test_game_state_construction(self):
        """GameState contains HP, MP, buffs, mob positions, loot, position, UI mode."""
        from lagent.common import GameState
        
        gs = GameState(
            hp_percent=85.5,
            mp_percent=60.0,
            active_buffs=["Haste", "Protect"],
            mob_positions={"mob_1": (100, 200), "mob_2": (500, 300)},
            loot_presence=True,
            character_position=(250, 400),
            ui_mode="combat"
        )
        
        assert gs.hp_percent == 85.5
        assert "Haste" in gs.active_buffs
        assert gs.mob_positions["mob_1"] == (100, 200)
        assert gs.ui_mode == "combat"
    
    def test_game_state_hp_range(self):
        """GameState validates HP/MP in [0, 100]."""
        from lagent.common import GameState
        
        # Valid
        GameState(
            hp_percent=50.0, mp_percent=100.0,
            character_position=(0, 0), ui_mode="town"
        )
        
        # Invalid HP
        with pytest.raises(Exception):  # ValidationError
            GameState(
                hp_percent=150.0, mp_percent=50.0,
                character_position=(0, 0), ui_mode="town"
            )


class TestPartyStateModel:
    """Validate PartyState as cross-process subset."""
    
    def test_party_state_construction(self):
        """PartyState contains FSM state, HP, MP, position, buff presence, heartbeat."""
        from lagent.common import PartyState
        
        import time
        timestamp = time.time()
        
        ps = PartyState(
            fsm_state="combat_engaged",
            hp_percent=75.0,
            mp_percent=80.0,
            position=(300, 400),
            buff_presence={"Haste": True, "Protect": False},
            heartbeat_timestamp=timestamp
        )
        
        assert ps.fsm_state == "combat_engaged"
        assert ps.position == (300, 400)
        assert ps.heartbeat_timestamp == timestamp


class TestActionModel:
    """Validate Action with mouse move, click, key press, and wait support."""
    
    def test_action_mouse_move(self):
        """Action supports mouse_move with x, y coordinates."""
        from lagent.common import Action
        
        action = Action(
            action_type="mouse_move",
            x=100,
            y=200
        )
        assert action.action_type == "mouse_move"
        assert action.x == 100
        assert action.y == 200
    
    def test_action_mouse_click(self):
        """Action supports mouse_click with button and clicks count."""
        from lagent.common import Action
        
        action = Action(
            action_type="mouse_click",
            button="left",
            clicks=2
        )
        assert action.action_type == "mouse_click"
        assert action.button == "left"
        assert action.clicks == 2
    
    def test_action_key_press(self):
        """Action supports key_press with key name."""
        from lagent.common import Action
        
        action = Action(
            action_type="key_press",
            key="space"
        )
        assert action.action_type == "key_press"
        assert action.key == "space"
    
    def test_action_wait(self):
        """Action supports wait with duration."""
        from lagent.common import Action
        
        action = Action(
            action_type="wait",
            duration=1.5
        )
        assert action.action_type == "wait"
        assert action.duration == 1.5


class TestAgentProfileModel:
    """Validate AgentProfile with config contracts."""
    
    def test_agent_profile_construction(self):
        """AgentProfile contains ROIs, FSM state bindings, skill keys, etc."""
        from lagent.common import AgentProfile
        
        profile = AgentProfile(
            name="warlord_pvp",
            rois={
                "health_bar": (100, 20, 200, 40),
                "mana_bar": (100, 45, 200, 65)
            },
            fsm_states={
                "idle": {},
                "combat": {"mode": "aggressive"}
            },
            skill_keys={
                "fireball": "1",
                "shield": "2"
            },
            buff_durations={
                "Haste": 30.0,
                "Protect": 60.0
            },
            confidence_threshold=0.6,
            enable_ocr=True
        )
        
        assert profile.name == "warlord_pvp"
        assert profile.rois["health_bar"] == (100, 20, 200, 40)
        assert profile.skill_keys["fireball"] == "1"
        assert profile.confidence_threshold == 0.6


class TestStructuralSeed:
    """AC-2: Structural seed and runnable stubs."""
    
    def test_required_directories_exist(self):
        """Required directories exist per architecture structural seed."""
        repo_root = Path(__file__).parent.parent
        required_dirs = [
            "lagent/common",
            "lagent/hsl",
            "lagent/agent/warlord",
            "lagent/agent/prophet",
            "lagent/gpu_server",
            "lagent/orchestrator",
            "lagent/ui",
            "lagent/train",
            "models/common",
            "models/warlord",
            "models/prophet",
            "profiles",
            "recordings",
            "data"
        ]
        
        for dir_path in required_dirs:
            assert (repo_root / dir_path).exists(), f"Missing directory: {dir_path}"
    
    def test_entry_point_files_exist(self):
        """__main__.py exists for agent, gpu_server, orchestrator, ui."""
        repo_root = Path(__file__).parent.parent
        entry_points = [
            "lagent/agent/__main__.py",
            "lagent/gpu_server/__main__.py",
            "lagent/orchestrator/__main__.py",
            "lagent/ui/__main__.py"
        ]
        
        for entry_point in entry_points:
            assert (repo_root / entry_point).exists(), f"Missing entry point: {entry_point}"


class TestEntryPoints:
    """AC-2: Entry points start and exit immediately with code 0."""
    
    def test_agent_entry_point(self):
        """python -m lagent.agent --check exits with code 0."""
        result = subprocess.run(
            [sys.executable, "-m", "lagent.agent", "--check"],
            cwd=Path(__file__).parent.parent,
            capture_output=True
        )
        assert result.returncode == 0, f"Agent failed: {result.stderr.decode()}"
    
    def test_gpu_server_entry_point(self):
        """python -m lagent.gpu_server --check exits with code 0."""
        result = subprocess.run(
            [sys.executable, "-m", "lagent.gpu_server", "--check"],
            cwd=Path(__file__).parent.parent,
            capture_output=True
        )
        assert result.returncode == 0, f"GPU server failed: {result.stderr.decode()}"
    
    def test_orchestrator_entry_point(self):
        """python -m lagent.orchestrator --check exits with code 0."""
        result = subprocess.run(
            [sys.executable, "-m", "lagent.orchestrator", "--check"],
            cwd=Path(__file__).parent.parent,
            capture_output=True
        )
        assert result.returncode == 0, f"Orchestrator failed: {result.stderr.decode()}"
    
    def test_ui_entry_point(self):
        """python -m lagent.ui exits with code 0."""
        result = subprocess.run(
            [sys.executable, "-m", "lagent.ui"],
            cwd=Path(__file__).parent.parent,
            capture_output=True
        )
        assert result.returncode == 0, f"UI failed: {result.stderr.decode()}"


class TestAD12Guard:
    """AC-1: AD-12 guard — shared types not re-exported from other subsystems."""
    
    def test_no_re_export_from_hsl(self):
        """Shared types are not in lagent.hsl.__all__."""
        from lagent import hsl
        
        # lagent.hsl should not re-export shared types
        if hasattr(hsl, "__all__"):
            assert "GameState" not in hsl.__all__
            assert "Detection" not in hsl.__all__
    
    def test_no_re_export_from_agent(self):
        """Shared types are not in lagent.agent.__all__."""
        from lagent import agent
        
        # lagent.agent should not re-export shared types
        if hasattr(agent, "__all__"):
            assert "GameState" not in agent.__all__
            assert "Detection" not in agent.__all__
    
    def test_no_re_export_from_gpu_server(self):
        """Shared types are not in lagent.gpu_server.__all__."""
        from lagent import gpu_server
        
        # lagent.gpu_server should not re-export shared types
        if hasattr(gpu_server, "__all__"):
            assert "GameState" not in gpu_server.__all__
            assert "Detection" not in gpu_server.__all__
    
    def test_no_re_export_from_orchestrator(self):
        """Shared types are not in lagent.orchestrator.__all__."""
        from lagent import orchestrator
        
        # lagent.orchestrator should not re-export shared types
        if hasattr(orchestrator, "__all__"):
            assert "GameState" not in orchestrator.__all__
            assert "Detection" not in orchestrator.__all__
    
    def test_no_re_export_from_ui(self):
        """Shared types are not in lagent.ui.__all__."""
        from lagent import ui
        
        # lagent.ui should not re-export shared types
        if hasattr(ui, "__all__"):
            assert "GameState" not in ui.__all__
            assert "Detection" not in ui.__all__


class TestModelSerialization:
    """Verify models are serializable for ZeroMQ JSON and SQLite payloads."""
    
    def test_detection_serializable(self):
        """Detection serializes to dict."""
        from lagent.common import Detection
        
        det = Detection(class_name="enemy", confidence=0.9, bbox_xyxy=(0, 0, 100, 100))
        data = det.model_dump()
        
        assert data["class_name"] == "enemy"
        assert data["confidence"] == 0.9
        assert data["bbox_xyxy"] == (0, 0, 100, 100)
    
    def test_perception_result_serializable(self):
        """PerceptionResult serializes to dict."""
        from lagent.common import Detection, PerceptionResult
        
        result = PerceptionResult(
            detections=[
                Detection(class_name="test", confidence=0.5, bbox_xyxy=(0, 0, 10, 10))
            ],
            ocr_values={"test": "value"}
        )
        data = result.model_dump()
        
        assert len(data["detections"]) == 1
        assert data["ocr_values"]["test"] == "value"
    
    def test_game_state_serializable(self):
        """GameState serializes to dict."""
        from lagent.common import GameState
        
        gs = GameState(
            hp_percent=50.0, mp_percent=75.0,
            character_position=(100, 200), ui_mode="combat"
        )
        data = gs.model_dump()
        
        assert data["hp_percent"] == 50.0
        assert data["ui_mode"] == "combat"
    
    def test_action_serializable(self):
        """Action serializes to dict."""
        from lagent.common import Action
        
        action = Action(action_type="mouse_move", x=100, y=200)
        data = action.model_dump()
        
        assert data["action_type"] == "mouse_move"
        assert data["x"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
