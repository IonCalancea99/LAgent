"""
Canonical shared types for LAgent — single source of truth across all processes.

All six types defined here are exported only through lagent.common.__init__.
No subsystem re-exports or redefines these contracts.
"""

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from enum import Enum
from typing import Annotated, Any, Dict, List, Tuple


class QuestResourceValidationError(ValueError):
    """Raised when an external quest resource or profile cannot be safely used."""


class DialogueChoice(BaseModel):
    """A single dialogue option permitted by the quest contract."""
    key: str = Field(description="Choice key or short code")
    text: str = Field(description="Dialogue text shown to the player")
    requires_confirmation: bool = Field(default=False, description="Whether this choice requires a confirmation step")


class ObjectiveStep(BaseModel):
    """A single ordered objective in the quest flow."""
    order: int = Field(ge=1, description="One-based objective order")
    id: str = Field(description="Stable objective identifier")
    name: str = Field(description="Human-readable objective label")
    target_npc: str = Field(description="NPC expected to be involved in this objective")
    type: str = Field(description="Objective type such as dialogue or travel")
    completion_indicators: List[str] = Field(default_factory=list, description="Signals that mark this objective complete")
    dialogue_choice: str | None = Field(default=None, description="Dialogue option key used for this objective")
    route_hint: str | None = Field(default=None, description="Optional navigation route hint")
    timeout_seconds: float | None = Field(default=None, ge=0.0, description="Objective timeout in seconds")
    retry_limit: int | None = Field(default=None, ge=0, description="Maximum retries for this objective")


class QuestCheckpoint(BaseModel):
    """A verified state boundary that must be met before the quest can proceed."""
    name: str = Field(description="Checkpoint name")
    required_state: str = Field(description="Required runtime condition")
    safe_stop_on_failure: bool = Field(default=True, description="Whether this checkpoint halts the quest when invalid")
    session_id: str = Field(default="", description="Session that owns this checkpoint")
    quest_id: str = Field(default="", description="Quest contract identity")
    objective_index: int = Field(default=0, ge=0, description="Verified zero-based objective index")
    status: str = Field(default="pending", description="Checkpoint verification status")
    verification_source: str = Field(default="", description="Evidence source that verified the boundary")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Last positive evidence snapshot")


class QuestResource(BaseModel):
    """Canonical runtime contract for a selected quest resource."""
    quest_id: str = Field(description="Stable quest identifier")
    quest_name: str = Field(description="Human-readable quest name")
    starting_npc: str = Field(description="NPC that initiates the quest")
    objective_sequence: List[ObjectiveStep] = Field(default_factory=list, description="Ordered objective list")
    dialogue_options: List[DialogueChoice] = Field(default_factory=list, description="Allowed dialogue choices")
    navigation_route: List[str] = Field(default_factory=list, description="Route segments for the quest")
    timeouts: Dict[str, float] = Field(default_factory=dict, description="Named timeout map")
    retries: Dict[str, int] = Field(default_factory=dict, description="Named retry map")
    safe_stop_conditions: List[str] = Field(default_factory=list, description="Conditions that trigger a safe stop")
    completion_indicators: List[str] = Field(default_factory=list, description="Quest-level completion signals")


class QuestPerceptionStatus(str, Enum):
    """Fail-closed outcome of evaluating quest perception evidence."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    VERIFY_FAILED = "verify_failed"


class QuestPerceptionEvidence(BaseModel):
    """Normalized quest evidence emitted by the perception boundary."""

    quest_id: str
    evidence_type: str
    status: QuestPerceptionStatus
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_ocr_text: str | None = None
    observed_value: str | None = None
    selected_dialogue_key: str | None = None
    objective_transition: bool = False
    safe_terminal: bool = False


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
    _frame_id: str | None = PrivateAttr(default=None)


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
    peer_party_state: "PartyState | None" = Field(
        default=None,
        description="Read-only snapshot of the peer agent's last valid PartyState; local GameState remains authoritative.",
    )

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "peer_party_state" and name in self.__dict__ and self.__dict__[name] is not None:
            raise AttributeError("peer_party_state is read-only")
        super().__setattr__(name, value)


class PartyState(BaseModel):
    """Cross-process state subset for synchronization.
    
    This is the only state intended to cross process boundaries.
    Serializable for ZeroMQ JSON and SQLite event payloads.
    """
    fsm_state: str = Field(default="IDLE", description="Finite state machine state name")
    hp_percent: float = Field(default=100.0, ge=0.0, le=100.0, description="HP as percentage")
    mp_percent: float = Field(default=100.0, ge=0.0, le=100.0, description="MP as percentage")
    position: Tuple[int, int] = Field(default=(0, 0), description="(x, y) position")
    buff_presence: Dict[str, bool] = Field(
        default_factory=dict, 
        description="Map of buff_name to presence boolean"
    )
    heartbeat_timestamp: float = Field(default=0.0, description="Unix timestamp of last heartbeat")


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

    # PP buff Safety Check policy constants (frame-pixel radius + retry cadence)
    aggro_risk_radius: float = Field(
        default=150.0,
        ge=0.0,
        description="Maximum mob-to-PP distance in pixels before a timed buff cast is considered unsafe",
    )
    retry_interval: float = Field(
        default=1.0,
        ge=0.0,
        description="Seconds to wait before re-evaluating a deferred PP buff cast",
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
    recovery: Dict[str, Any] = Field(default_factory=dict, description="Profile-driven death recovery action sequence")
    inventory: Dict[str, Any] = Field(default_factory=dict, description="Profile-driven town return and loot rules")
    session_cap_duration: float | None = Field(default=None, ge=0.0, description="Optional monotonic session cap in seconds")
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
    micro_drift_enabled: bool = Field(default=False, description="Enable idle cursor micro-drift")
    micro_drift_frequency: float = Field(default=0.05, ge=0.0, le=1.0, description="Probability of drift per idle cycle")
    micro_drift_magnitude: Tuple[int, int] = Field(default=(2, 8), description="Minimum and maximum drift offset in pixels")
    camera_drift_enabled: bool = Field(default=False, description="Enable camera drift callback during idle cycles")
    camera_drift_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Probability of camera drift per idle cycle")
    error_injection_probability: float = Field(default=0.0, ge=0.0, le=1.0, description="Probability of an eligible click override")
    protected_action_types: Tuple[str, ...] = Field(
        default=("key_press", "wait"),
        description="Action types that error injection must never alter",
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

    @property
    def buff_retry_interval(self) -> float:
        return self.retry_interval
