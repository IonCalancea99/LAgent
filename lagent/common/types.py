"""
Canonical shared types for LAgent — single source of truth across all processes.

All six types defined here are exported only through lagent.common.__init__.
No subsystem re-exports or redefines these contracts.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, Any, Dict, List, Tuple


class Detection(BaseModel):
    """Object detection result from GPU inference.
    
    Coordinates are frame pixels with top-left origin.
    """
    class_name: str = Field(description="Detected class name")
    confidence: float = Field(gt=0.0, le=1.0, description="Detection confidence [0, 1]")
    bbox_xyxy: Tuple[int, int, int, int] = Field(description="Bounding box (x1, y1, x2, y2) in frame pixels")


class PerceptionResult(BaseModel):
    """Unified perception output: vision + OCR."""
    detections: List[Detection] = Field(default_factory=list, description="List of detected objects")
    ocr_values: Dict[str, str] = Field(default_factory=dict, description="OCR text map {region_key: text}")


class GameState(BaseModel):
    """Complete agent-owned game state updated each perception cycle.
    
    Owned exclusively by an Agent; not shared mutable state.
    Only PartyState subset crosses process boundaries.
    """
    hp_percent: float = Field(ge=0.0, le=100.0, description="Agent HP as percentage")
    mp_percent: float = Field(ge=0.0, le=100.0, description="Agent MP as percentage")
    active_buffs: List[str] = Field(default_factory=list, description="List of active buff names")
    mob_positions: Dict[str, Tuple[int, int]] = Field(
        default_factory=dict, 
        description="Map of mob_id to (x, y) coordinates"
    )
    loot_presence: bool = Field(default=False, description="Loot visible on ground")
    character_position: Tuple[int, int] = Field(description="Agent character (x, y) position")
    ui_mode: str = Field(description="Current UI mode (e.g., 'combat', 'town')")


class PartyState(BaseModel):
    """Cross-process state subset for synchronization.
    
    This is the only state intended to cross process boundaries.
    Serializable for ZeroMQ JSON and SQLite event payloads.
    """
    fsm_state: str = Field(description="Finite state machine state name")
    hp_percent: float = Field(ge=0.0, le=100.0, description="HP as percentage")
    mp_percent: float = Field(ge=0.0, le=100.0, description="MP as percentage")
    position: Tuple[int, int] = Field(description="(x, y) position")
    buff_presence: Dict[str, bool] = Field(
        default_factory=dict, 
        description="Map of buff_name to presence boolean"
    )
    heartbeat_timestamp: float = Field(description="Unix timestamp of last heartbeat")


class Action(BaseModel):
    """Policy-to-HSL contract: agent decision → OS input.
    
    Supports: mouse move, mouse click, key press, wait.
    """
    action_type: str = Field(
        description="Action type: 'mouse_move', 'mouse_click', 'key_press', or 'wait'"
    )
    # Mouse move parameters
    x: int | None = Field(default=None, description="X coordinate for mouse_move")
    y: int | None = Field(default=None, description="Y coordinate for mouse_move")
    
    # Mouse click parameters
    button: str | None = Field(default=None, description="Mouse button: 'left', 'middle', 'right'")
    clicks: int | None = Field(default=None, description="Number of clicks")
    
    # Key press parameters
    key: str | None = Field(default=None, description="Key name for key_press")
    
    # Wait parameters
    duration: float | None = Field(default=None, description="Wait duration in seconds")


class AgentProfile(BaseModel):
    """Shared profile contract: agent configuration and bindings.
    
    Profile loading and validation behavior is Story 1.2.
    Contains ROI positions, FSM bindings, skill key bindings, thresholds, flags.
    """
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(description="Agent profile name")
    
    # ROI positions (regions of interest for screen capture)
    roi_positions: Dict[str, Tuple[int, int, int, int]] = Field(
        default_factory=dict,
        alias="rois",
        description="Named ROIs: {roi_name: (x1, y1, x2, y2)}",
    )
    
    # FSM state bindings
    fsm_bindings: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        alias="fsm_states",
        description="FSM state configurations by state name"
    )
    
    # Skill key bindings
    skill_key_bindings: Dict[str, str] = Field(
        default_factory=dict,
        alias="skill_keys",
        description="Skill name to keyboard key mapping"
    )
    
    # Buff timer durations (seconds)
    buff_timer_durations: Dict[str, float] = Field(
        default_factory=dict,
        alias="buff_durations",
        description="Buff name to duration (seconds)"
    )

    confidence_thresholds: Dict[str, Annotated[float, Field(ge=0.0, le=1.0)]] = Field(
        default_factory=dict,
        description="Named detection confidence thresholds",
    )
    
    # Detection thresholds
    confidence_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Minimum detection confidence"
    )

    # Human simulation settings
    bezier_offset_range: Tuple[int, int] = Field(
        default=(15, 30),
        description="Minimum and maximum absolute cubic Bezier control-point offset in pixels",
    )
    skill_timing: Dict[str, Dict[str, float]] = Field(
        default_factory=lambda: {
            "default": {"mean": 0.18, "std": 0.05},
            "heal": {"mean": 0.20, "std": 0.06},
            "buff": {"mean": 0.22, "std": 0.07},
            "attack": {"mean": 0.16, "std": 0.04},
        },
        description="Per-skill Gaussian keystroke timing parameters keyed by skill name with mean/std in seconds",
    )
    fatigue_step: float = Field(default=0.05, ge=0.0, description="Increment added to the fatigue factor each fatigue interval")
    fatigue_ceiling: float = Field(default=1.5, ge=1.0, description="Maximum fatigue multiplier before a break is triggered")
    fatigue_interval: float | Tuple[float, float] = Field(
        default=(1800.0, 3600.0),
        description="Session seconds between fatigue increments; may also be provided as a (min, max) range",
    )
    break_duration_range: Tuple[float, float] = Field(
        default=(300.0, 900.0),
        description="Randomized break duration range in seconds",
    )
    
    # Mode flags
    enable_ocr: bool = Field(default=True, description="Enable OCR processing")
    enable_recording: bool = Field(default=False, description="Enable recording (reserved)")

    @property
    def bezier_offsets(self) -> Tuple[int, int]:
        """Backward-compatible plural access for path generator callers."""
        return self.bezier_offset_range

    @property
    def rois(self) -> Dict[str, Tuple[int, int, int, int]]:
        """Backward-compatible access for the Story 1.1 field name."""
        return self.roi_positions

    @property
    def fsm_states(self) -> Dict[str, Dict[str, Any]]:
        return self.fsm_bindings

    @property
    def skill_keys(self) -> Dict[str, str]:
        return self.skill_key_bindings

    @property
    def buff_durations(self) -> Dict[str, float]:
        return self.buff_timer_durations
