---
stepsCompleted: [step-01, step-02, step-03, step-04]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-LAgent-2026-08-04/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-LAgent-2026-08-04/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/architecture/architecture-LAgent-2026-08-04/solution-design.md
  - _bmad-output/planning-artifacts/briefs/brief-LAgent-2026-08-04/brief.md
  - _bmad-output/planning-artifacts/briefs/brief-LAgent-2026-08-04/addendum.md
---

# LAgent - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for LAgent, decomposing the requirements from the PRD, Architecture, Solution Design, Brief, Addendum, and verbal UX specification into implementable stories.

---

## Requirements Inventory

### Functional Requirements

```
FR-1:  Per-window screen capture — capture each bound game window at configurable rate (default 10 FPS); frame available within 10 ms of capture; each window independent.
FR-2:  ROI extraction — extract configurable named ROIs from each captured frame per class YAML profile before passing to detection.
FR-3:  Object and state detection — apply Common Model (class-agnostic) and Class Model (class-specific) YOLO families per frame; merge into GameState; inference ≤100 ms/frame/window on target hardware.
FR-4:  Numeric OCR — apply OCR to HP bar, MP bar, and buff-timer ROIs; values included in GameState; GPU when available, degrades to CPU gracefully.
FR-5:  Combined FSM + BC behavior policy — per-Agent FSM for high-level state management (IDLE→PULLING→FIGHTING→LOOTING→RETURNING→DEAD→BUFFING); BC Policy for within-state action selection; states, transitions, and BC bindings enumerated in YAML profile.
FR-6:  Party State + PP buff Safety Check — Agents subscribe to Party Bus; PP manages timed buff cycle independently; PP Safety Check gates all timed casts (aggro-risk radius + WL state); cast deferred on fail, never skipped.
FR-7:  Per-class YAML agent profile — FSM transitions, skill key bindings, buff timer durations, ROI positions, confidence thresholds in YAML; validated by Pydantic v2 schema at startup; hot-reloadable between sessions.
FR-8:  Bézier mouse paths — all mouse moves follow cubic Bézier with randomized control points (±15–30 px); bell-curve speed profile with ±10% random variance; zero straight-line moves.
FR-9:  Keystroke timing noise — inter-key delays drawn from per-skill Gaussian distribution; mean and std captured from recordings during Training Pipeline; defaults at bootstrap.
FR-10: Fatigue model — action latency multiplied by monotonically growing Fatigue Factor over session time; Break triggered at ceiling or session cap; no input during Break (randomized 5–15 min).
FR-11: Micro-drift — occasional small cursor movements to non-target positions and rare camera rotations between actions; frequency and magnitude configurable; off-by-default.
FR-12: Error injection — configurable low probability (default 1–3%) deliberate misclick; system detects resulting GameState anomaly; corrective action within one decision cycle; logged as override event.
FR-13: Party Bus relay — Orchestrator relays Agent state events between WL and PP with sub-10 ms latency; loss of connectivity triggers PAUSED on both agents.
FR-14: Session health monitoring — Orchestrator monitors heartbeats; N missed consecutive heartbeats (configurable, default 3) triggers session halt; halt logged and surfaced on next launch.
FR-15: Character identification on startup — scan each game window, determine active class via skill bar layout fingerprinting; assign correct agent profile before control loop; ≥95% first-attempt success; manual fallback prompt on failure.
FR-16: Death detection and recovery — DEAD FSM state: respawn sequence → navigate to buff spot → PP rebuffs WL → resume prior FSM state; full party recovery ≤60 seconds; death logged with GameState snapshot.
FR-17: Inventory-full detection and town return — detect full inventory; suspend combat loop; safe return to town; deposit/drop per configured rules; no silent discard without authorized rule; no human intervention required.
FR-18: Session cap and shutdown — configurable max duration (default 4–6 hours); clean shutdown: return to safe location, PP final buff cycle, both characters idle before input stops; enforced even mid-combat-cycle.
FR-19: Recording Mode — simultaneous frame capture + Ion's keyboard/mouse input log with timestamps; no interference with manual play; overhead <30 FPS degradation; hotkey activation/deactivation.
FR-20: Auto-prelabeling — post-recording, apply current YOLO models to all captured frames; produce prelabeled annotation file in Label Studio import format; ≥2× real-time prelabeling speed.
FR-21: Model training — fine-tune YOLO vision model and update keystroke timing from labeled recording; new behavior model trainable to functional quality within 2 hours; tracked in local MLflow; prior version not overwritten until new version validated.
FR-22: YouTube frame ingestion — accept YouTube URL; download via yt-dlp; extract frames at configurable FPS; feed to Label Pipeline; 10-min video processed in ≤5 minutes; no credentials required; frames indistinguishable from recorded frames in label queue.
FR-24: Shadow Mode — startup flag or UI toggle; routes all actions through HSL for logging; suppresses OS input API calls; cannot be toggled mid-session; sessions clearly labelled in log.
FR-25: Fishing cast-and-reel loop — Fishing Mode FSM: detect idle → cast → wait for bite → detect tension (YOLO-based) → execute reel → return to idle; sustain 1-hour uninterrupted session as Phase 1 gate; missed bite returns to idle cleanly.
```

### Non-Functional Requirements

```
NFR-1:  Local-only — all inference, training, storage, and telemetry runs on Ion's local machine; zero cloud services; zero external data exposure.
NFR-2:  Windows platform — L2 client, dxcam, pynput, win32api are Windows-native; system targets Windows exclusively.
NFR-3:  Hardware envelope — GTX 1070 Ti (8 GB VRAM); runtime inference VRAM budget ~2.5–3.5 GB (comfortable on 8 GB); training is offline only and uses 4–6 GB VRAM; must not run concurrently with a live session.
NFR-4:  No client modification — zero interaction with L2 client internals, memory space, or network packets — ever.
NFR-5:  End-to-end latency — perception-to-action ≤200 ms; capture-to-frame-available ≤10 ms; YOLO+OCR inference ≤100 ms/frame/window.
NFR-6:  Anti-detection — behavioral fingerprint indistinguishable from human play at OS and network level; action timing distributions within 1 standard deviation of Ion's recorded play (validated via Shadow Mode); zero bans in 30-day continuous operation.
NFR-7:  Session autonomy — sustain WL+PP farming session ≥4 hours without human intervention.
NFR-8:  Capture rate — 10 FPS per window sufficient for L2's skill cast times (≥0.5 s); each window captured independently.
NFR-9:  No shared memory across processes — all cross-process coupling via ZeroMQ only (AD-1).
NFR-10: Fail-fast config loading — invalid YAML profile raises schema validation error at startup before any session begins; no runtime fallback to defaults.
```

### Additional Requirements (from Architecture)

```
- Project structure: greenfield Python 3.12 package `lagent/` with submodules: common, hsl, agent (warlord/prophet), gpu_server, orchestrator, ui, train. No starter template — structure defined in ARCHITECTURE-SPINE.md § Structural Seed.
- Shared types only in lagent.common (GameState, PartyState, PerceptionResult, Action, AgentProfile) — no other cross-process imports (AD-12).
- All processes append to single WAL-mode SQLite `data/sessions.db` (one connection per process); schema: sessions(session_id, started_at, profile, mode) + events(id, session_id, ts, source, type, payload_json) (AD-9).
- Model versioning: Training Pipeline writes validated model to `models/<class>/current.pt` via temp-write + os.replace(); GPU Inference Server loads at startup only — no in-session reload (AD-7).
- Training Pipeline is a separate CLI (`python -m lagent.train <subcommand>`); never co-runs with a live session (AD-6).
- All spatial proximity and radius calculations use frame-pixel coordinates (origin top-left, matching Detection.bbox_xyxy); no game-world coordinate space (AD-10b).
- ZeroMQ socket patterns fixed: Agent→GPU uses DEALER/ROUTER; Party Bus uses PUB/SUB; heartbeat piggybacked on Party Bus PUB; no REQ/REP anywhere in runtime (AD-11).
- HSL is instantiated once per Agent process; fatigue_state and timing_params are instance-level, never module-level globals; Shadow Mode is implemented inside HSL (AD-8).
- Tray/UI is the sole process launcher for all runtime child processes (AD-5).
- Every bounded internal queue uses oldest-frame eviction; max depth 2 frames per stage per agent (AD-3).
- Recording Mode: --record flag at process launch switches capture thread to dual-write and activates pynput listener; mutually exclusive with live Session Mode at process launch (AD-13).
- Logging: structlog JSON lines to stdout per process; FSM transitions and session events additionally written to sessions.db (consistency conventions).
```

### UX Design Requirements

```
UX-1: System tray icon — Windows system tray (notification area) icon as the primary control surface; no main window or taskbar presence during normal operation.
UX-2: Tray context menu — right-click tray icon reveals a minimal context menu with: Start Session (with profile submenu: Fishing / Combat / Shadow), Stop Session, Recording Mode toggle, Open Status Overlay, Exit.
UX-3: Status overlay — small always-on-top borderless window (Windows native style, semi-transparent); displays per-agent row: FSM state label, HP% bar, MP% bar, session timer; toggled from tray menu or hotkey.
UX-4: Minimal footprint — overlay and tray consume negligible CPU/GPU; no heavy framework rendering on the live session critical path (consistent with AD-5 Tray/UI isolation rule).
UX-5: Windows visual style — native Windows look-and-feel using PyQt6 with system palette; no custom theming; readable at small size (overlay is peripheral, not primary focus during session).
UX-6: Ion-only operator model — no login, no user management, no settings wizard; all configuration is via YAML profile files; UI surfaces operational state only.
```

---

### FR Coverage Map

| FR | Epic |
|---|---|
| FR-1 | Epic 2 — Capture thread |
| FR-2 | Epic 2 — ROI extraction |
| FR-3 | Epic 2 — YOLO detection |
| FR-4 | Epic 2 — EasyOCR |
| FR-5 | Epic 4 (Fishing FSM base) + Epic 6 (Combat FSM extension) |
| FR-6 | Epic 5 — Party Bus + PP Safety Check |
| FR-7 | Epic 1 — YAML profiles + Pydantic |
| FR-8 | Epic 3 — Bézier mouse |
| FR-9 | Epic 3 — Keystroke timing |
| FR-10 | Epic 3 — Fatigue model |
| FR-11 | Epic 3 — Micro-drift |
| FR-12 | Epic 3 — Error injection |
| FR-13 | Epic 5 — Party Bus relay |
| FR-14 | Epic 5 — Orchestrator heartbeat |
| FR-15 | Epic 4 — Character identification |
| FR-16 | Epic 6 — Death recovery |
| FR-17 | Epic 6 — Inventory + town return |
| FR-18 | Epic 6 — Session cap + shutdown |
| FR-19 | Epic 7 — Recording Mode |
| FR-20 | Epic 7 — Auto-prelabeling |
| FR-21 | Epic 7 — Model training |
| FR-22 | Epic 7 — YouTube ingestion |
| FR-24 | Epic 3 — Shadow Mode (inside HSL) |
| FR-25 | Epic 4 — Fishing cast-and-reel loop |
| FR-26 | Epic 9 — Quest resource discovery from `lineage.ru` |
| FR-27 | Epic 9 — Supply Check conversational execution |
| FR-28 | Epic 9 — Quest perception and completion verification |
| FR-29 | Epic 9 — Quest failure and lifecycle recovery |
| UX-1–6 | Epic 8 — Tray UI + overlay |

---

## Epic List

### Epic 1: Runnable Foundation
Ion can launch `python -m lagent.ui`, see the tray icon, and have all 4 runtime processes (WL Agent, PP Agent, GPU Server, Orchestrator) spawn and exchange ZeroMQ messages successfully. Sessions are logged to SQLite. YAML profiles load and validate at startup.
**FRs covered:** FR-7, NFR-9, NFR-10, AD-9 (sessions.db), AD-12 (lagent.common types)

### Epic 2: Perception Pipeline
Ion can run a single Agent window in debug mode and see real-time YOLO detections + OCR values for a live game frame. The full capture → GPU inference → PerceptionResult path works at target latency.
**FRs covered:** FR-1, FR-2, FR-3, FR-4

### Epic 3: Human Simulation Layer & Shadow Mode
Ion can run Shadow Mode and review the session log to verify that action timing distributions, mouse paths, and fatigue behavior are within human-play bounds before any live session.
**FRs covered:** FR-8, FR-9, FR-10, FR-11, FR-12, FR-24

### Epic 4: Fishing Mode (Phase 1 Gate)
Ion can start an automated fishing session on a single game window. The bot casts, detects fish tension via YOLO, reels in, and loops for a full 1-hour uninterrupted session. Character identification works on startup. This is the Phase 1 gate.
**FRs covered:** FR-5 (Fishing FSM + BC Policy base), FR-15, FR-25

### Epic 5: Party Orchestration
WL Agent and PP Agent exchange state over the Party Bus. PP buff Safety Check works correctly. The Orchestrator monitors heartbeats and halts both agents on missed heartbeats.
**FRs covered:** FR-6, FR-13, FR-14

### Epic 6: Combat Mode & Session Lifecycle
Ion can start a full WL+PP combat farming session. The bot handles the complete lifecycle: combat loop, death recovery, inventory-full town return, and clean session cap shutdown — running for 4+ hours without intervention.
**FRs covered:** FR-5 (Combat FSM + BC Policy for WL/PP), FR-16, FR-17, FR-18

### Epic 7: Training Pipeline
Ion can record a gameplay session, run auto-prelabeling, correct labels in Label Studio, retrain a YOLO + BC model, and have the new model atomically deployed. YouTube footage can be ingested into the label queue.
**FRs covered:** FR-19, FR-20, FR-21, FR-22

### Epic 8: Tray UI & Status Overlay
Ion can control sessions entirely from the system tray: start/stop sessions with profile selection, toggle Recording Mode, and monitor per-agent FSM state + HP/MP + session timer in a minimal always-on-top overlay.
**UX covered:** UX-1, UX-2, UX-3, UX-4, UX-5, UX-6

### Epic 9: Quest Mode (V1, Phase 1 Supply Check)
Ion can run the simple conversational Supply Check quest beginning with NPC Marcela in Kamael village using a level-3 Orc Fighter. The Agent scrapes and validates quest metadata from `lineage.ru`, discovers the objective and dialogue sequence, navigates and interacts using verified perception, logs progress, and stops safely on ambiguity. Phase 1 is single-agent and requires no combat.
**FRs covered:** FR-26, FR-27, FR-28, FR-29
**Dependencies:** Epics 1–3, Story 4.1 agent loop, Story 4.2 character identification, Epic 6 lifecycle recovery, and Epic 8 operational status.

#### Epic 9 Stories

- **Story 9.1:** Lineage resource adapter and validated quest state/profile contract
- **Story 9.2:** Supply Check perception fixtures for Marcela, dialogue, objectives, and completion
- **Story 9.3:** Deterministic Quest FSM and positive objective verification
- **Story 9.4:** Resource-driven Kamael village navigation and stuck detection
- **Story 9.5:** Marcela interaction and dialogue selection with bounded retries
- **Story 9.6:** Quest checkpoint, failure, and lifecycle recovery
- **Story 9.7:** Quest telemetry and tray/overlay status
- **Story 9.8:** Shadow-mode and live Supply Check acceptance fixture

---

## Epic 1: Runnable Foundation

Ion can launch `python -m lagent.ui`, see the tray icon, and have all 4 runtime processes (WL Agent, PP Agent, GPU Server, Orchestrator) spawn and exchange ZeroMQ messages successfully. Sessions log to SQLite. YAML profiles load and validate at startup.

### Story 1.1: Project Scaffold & lagent.common Shared Types

As Ion (sole developer),
I want the full `lagent/` package structure created with all Pydantic v2 shared types defined in `lagent.common`,
So that every downstream process has a single import source for `GameState`, `PartyState`, `PerceptionResult`, `Detection`, `Action`, and `AgentProfile` and the module graph rule (AD-12) is enforced from day one.

**Acceptance Criteria:**

**Given** the repository is freshly cloned with `pyproject.toml` listing all runtime dependencies
**When** `python -c "from lagent.common import GameState, PartyState, PerceptionResult, Detection, Action, AgentProfile"` is run
**Then** all types import without error; each is a Pydantic v2 model with fields matching the canonical definitions in AD-10 and AD-12
**And** `lagent.common` is the only module with `__init__.py` exports of shared types; no other submodule re-exports them

**Given** the structural seed directories (`lagent/agent/warlord`, `lagent/agent/prophet`, `lagent/gpu_server`, `lagent/orchestrator`, `lagent/ui`, `lagent/hsl`, `lagent/train`, `models/common`, `models/warlord`, `models/prophet`, `profiles/`, `recordings/`, `data/`) exist
**When** `python -m lagent.agent`, `python -m lagent.gpu_server`, `python -m lagent.orchestrator`, `python -m lagent.ui` are each run
**Then** each process starts and immediately exits with code 0 (stub `__main__.py`)

---

### Story 1.2: YAML Agent Profile Loader & Validation

As Ion,
I want stub `warlord.yaml` and `prophet.yaml` profiles loaded and validated by a Pydantic v2 schema at process startup,
So that invalid profile configurations fail fast with a clear error before any session begins (FR-7).

**Acceptance Criteria:**

**Given** `profiles/warlord.yaml` contains all required fields (ROI positions, FSM bindings, skill key bindings, buff timer durations, confidence thresholds)
**When** `python -m lagent.agent --class warlord` is run
**Then** the profile loads, passes Pydantic schema validation, and logs "Profile loaded: warlord" to stdout

**Given** `profiles/warlord.yaml` is missing a required field (e.g., `roi_positions`)
**When** `python -m lagent.agent --class warlord` is run
**Then** a `ProfileValidationError` is raised and the process exits with a non-zero code before any session begins
**And** the error message clearly identifies the missing or invalid field

**Given** a valid profile is on disk
**When** the profile file is updated and the process is restarted between sessions
**Then** new profile values are picked up on next startup without code changes

---

### Story 1.3: Session Database — WAL-mode SQLite Setup

As Ion,
I want `data/sessions.db` auto-created on first write with the WAL-mode SQLite schema,
So that all runtime processes can append session telemetry and events independently without exclusive locks (AD-9).

**Acceptance Criteria:**

**Given** `data/sessions.db` does not yet exist
**When** any process calls the db writer for the first time
**Then** `sessions.db` is created automatically with WAL journal mode enabled; tables `sessions(session_id, started_at, profile, mode)` and `events(id, session_id, ts, source, type, payload_json)` exist

**Given** two processes (WL Agent and PP Agent) each hold a separate SQLite connection in WAL mode
**When** both write events concurrently
**Then** no "database is locked" error occurs; both events appear in the `events` table

**Given** a session is started
**When** the db writer logs a session start event
**Then** a row appears in `sessions` with correct `session_id`, `started_at`, `profile`, and `mode` values

---

### Story 1.4: ZeroMQ Channel Wiring & All Processes Running

As Ion,
I want all 5 runtime processes to start, establish their ZeroMQ connections per the fixed socket pattern rules, and exchange a startup handshake,
So that I can verify inter-process wiring is correct before any real logic is added (AD-1, AD-11).

**Acceptance Criteria:**

**Given** GPU Server is started first (binds ROUTER socket), then WL Agent and PP Agent start (each connects DEALER socket)
**When** each Agent sends a test inference request `{agent_id, frame_bytes: b"", roi_map: {}}`
**Then** the GPU Server receives both requests identified by `agent_id` and returns a stub `PerceptionResult` to each originating agent within 50 ms

**Given** WL Agent and PP Agent are both running with PUB sockets bound
**When** each agent publishes a stub `PartyState` message
**Then** the peer agent's SUB socket receives the message; Orchestrator's SUB socket also receives the heartbeat-tagged message

**Given** Orchestrator is running and subscribed to both agents' PUB sockets
**When** an agent stops publishing (process killed)
**Then** Orchestrator logs a "heartbeat missed" warning after the configured interval

---

### Epic 2: Perception Pipeline

Ion can run a single Agent window in debug mode and see real-time YOLO detections and OCR values for a live game frame. Stories 2.1–2.4 provide the capture, ROI, model, and OCR components; Story 2.5 must connect them into the full capture → GPU inference → PerceptionResult path and verify target latency.

### Story 2.1: Screen Capture Thread — dxcam Primary, mss Fallback

As Ion,
I want the Agent capture thread to grab game window frames at ~10 FPS using dxcam (with mss fallback) and push them to a bounded FrameQueue,
So that frames are available for the inference pipeline within 10 ms of capture without ever blocking the capture thread (FR-1, AD-3).

**Acceptance Criteria:**

**Given** a Lineage 2 game window is open and bound by window title in the agent profile
**When** the Agent starts in debug mode
**Then** the capture thread captures frames at the configured rate (default 10 FPS); each frame is pushed to FrameQueue within 10 ms of capture

**Given** the FrameQueue is already full (maxsize=2)
**When** the capture thread produces a new frame
**Then** the oldest frame is evicted and replaced by the new frame; the capture thread is never blocked by a slow downstream stage

**Given** dxcam is unavailable (import fails)
**When** the Agent starts
**Then** the capture thread falls back to mss silently; a log message notes the fallback; capture continues at target rate

---

### Story 2.2: ROI Extraction from Agent Profile

As Ion,
I want named ROI crops extracted from each captured frame using coordinates from the YAML agent profile,
So that downstream detection runs only on relevant screen regions and ROI positions can be changed via profile update without code changes (FR-2).

**Acceptance Criteria:**

**Given** `warlord.yaml` defines ROIs: `hp_bar`, `mp_bar`, `buff_strip`, `mob_area`
**When** a frame is captured
**Then** each named ROI is extracted as a pixel-accurate crop matching the profile coordinates

**Given** the ROI coordinates in the profile are updated and the Agent restarted
**When** a new frame is captured
**Then** the extraction uses the new coordinates without any code change

**Given** a ROI coordinate is out of bounds for the current window resolution
**When** the Agent starts
**Then** a validation error is raised at startup identifying the offending ROI name and value

---

### Story 2.3: GPU Inference Server — YOLO Detection (Common + Class Models)

As Ion,
I want the GPU Inference Server to accept frame + ROI map from each Agent over DEALER/ROUTER ZeroMQ and return a merged Detection list from both Common Model and Class Model YOLOv8-nano inference,
So that both agents get class-agnostic and class-specific detections within the 100 ms per-frame budget on the GTX 1070 Ti (FR-3, AD-2).

**Acceptance Criteria:**

**Given** `models/common/current.pt` and `models/warlord/current.pt` exist (stub YOLOv8-nano weights)
**When** the GPU Server receives `{agent_id: "warlord", frame_bytes: <bytes>, roi_map: {...}}`
**Then** both models run inference; detections are merged into a single list; each `Detection` has `class_name: str`, `confidence: float`, `bbox_xyxy: tuple[int,int,int,int]` (pixel coords, origin top-left per AD-10b)
**And** combined inference completes in ≤100 ms per frame on the GTX 1070 Ti

**Given** both WL Agent and PP Agent send concurrent inference requests
**When** the GPU Server processes them
**Then** each agent receives only its own `PerceptionResult`; correlation by `agent_id` is correct; no cross-agent result contamination

**Given** a detection falls below the configured confidence threshold
**When** the result list is assembled
**Then** that detection is excluded from `PerceptionResult.detections`

---

### Story 2.4: EasyOCR Integration — HP/MP/Buff Numeric Values

As Ion,
I want the GPU Inference Server to run EasyOCR on the HP bar, MP bar, and buff-timer ROI crops and include the extracted values in `PerceptionResult.ocr_values`,
So that Agents have current numeric HP%, MP%, and buff counts in their GameState without running OCR locally (FR-4, AD-10).

**Acceptance Criteria:**

**Given** valid HP bar and MP bar ROI crops from a live game frame
**When** EasyOCR runs on those crops
**Then** `ocr_values` dict contains keys `hp`, `mp`, and at least one `buff_*` key with string-encoded numeric values

**Given** a CUDA-capable GPU is present
**When** the GPU Server starts
**Then** EasyOCR runs on GPU; a log line confirms "OCR device: cuda"

**Given** no CUDA device is available
**When** the GPU Server starts
**Then** EasyOCR falls back to CPU; a log line confirms "OCR device: cpu"; inference continues without error

---

### Story 2.5: Inference Client, PolicyQueue & Debug Perception Display

As Ion,
I want the Agent's Inference Client to pop frames from FrameQueue, send them to the GPU Server, and push the returned `PerceptionResult` to PolicyQueue — with a debug mode that logs detections and OCR values to stdout each tick,
So that I can visually verify the full capture → inference → result pipeline on a live game window before writing any policy logic (AD-3).

**Acceptance Criteria:**

**Given** an Agent is started with `--debug` flag against a live game window
**When** the inference loop runs
**Then** stdout shows a `PerceptionResult` log line per tick (~10/s) listing all detections with class, confidence, bbox, and all OCR values

**Given** PolicyQueue is full (maxsize=2) when a new `PerceptionResult` arrives
**When** the Inference Client pushes the result
**Then** the oldest result is evicted; no blocking occurs on the inference path

**Given** the GPU Server is unreachable
**When** the Agent's Inference Client attempts to send a frame
**Then** the request times out; the frame is dropped; the capture thread is not blocked; a warning is logged

---

Epic 2 has 5 stories. All FRs (FR-1 through FR-4) are covered. Proceeding to Epic 3.

---

## Epic 3: Human Simulation Layer & Shadow Mode

Ion can run Shadow Mode and review the session log to verify that action timing distributions, mouse paths, and fatigue behavior are within human-play bounds before any live session.

### Story 3.1: Bézier Mouse Path Generator

As Ion,
I want all mouse moves routed through a cubic Bézier path generator with randomized control point offsets and a bell-curve speed profile,
So that no straight-line mouse movement is ever produced by the bot and cursor paths look human under visual inspection (FR-8).

**Acceptance Criteria:**

**Given** a source position and a target position
**When** `HSL.move_mouse(src, dst)` is called
**Then** the cursor follows a cubic Bézier path; control point offsets are drawn from the configured range (default ±15–30 px); no straight-line path is produced

**Given** 100 mouse moves are generated between the same two points
**When** their paths are inspected
**Then** no two paths are identical; speed profiles follow a bell curve (slow-fast-slow) with ±10% per-path variance

**Given** the `bezier_offset_range` is changed in the profile
**When** new moves are generated
**Then** control point offsets reflect the new range without code changes

---

### Story 3.2: Keystroke Timing Noise

As Ion,
I want inter-key delays for all skill key sequences drawn from a per-skill Gaussian distribution,
So that keystroke timing is statistically human-like and never mechanically uniform (FR-9).

**Acceptance Criteria:**

**Given** a skill key sequence is executed
**When** `HSL.press_key(skill_id, key)` is called
**Then** the inter-key delay is sampled from the Gaussian distribution for that `skill_id` (mean + std from profile defaults)

**Given** 50 presses of the same skill key
**When** their delays are measured
**Then** the distribution has non-zero standard deviation; no two consecutive delays are identical

**Given** a training run updates timing params for a skill
**When** the updated params are loaded
**Then** subsequent key presses for that skill use the new mean and std

---

### Story 3.3: Fatigue Model

As Ion,
I want the Fatigue Factor to grow monotonically over session time and trigger an automatic Break that resets it, with all parameters configurable in the agent profile,
So that action latency variation mimics human tiredness patterns over a long session (FR-10).

**Acceptance Criteria:**

**Given** a session starts
**When** time progresses past each fatigue increment interval (default: every 30–60 min)
**Then** `HSL.fatigue_factor` increases by the configured step; all action latencies are multiplied by the current factor

**Given** `HSL.fatigue_factor` reaches the configured ceiling
**When** the ceiling is hit
**Then** a Break is triggered automatically; no mouse or keyboard input is produced for a randomized duration within the configured break-length range (default 5–15 min); after the Break, `fatigue_factor` resets to 1.0

**Given** two Agent processes are running (WL and PP)
**When** both have HSL instances
**Then** each instance has independent `fatigue_state`; WL fatigue does not affect PP fatigue

---

### Story 3.4: Micro-drift & Error Injection

As Ion,
I want occasional small cursor movements to non-target positions (micro-drift) and rare deliberate misclick-and-correct sequences (error injection) wired into the HSL,
So that the bot's idle and action patterns are statistically indistinguishable from natural human imprecision (FR-11, FR-12, AD-8).

**Acceptance Criteria:**

**Given** micro-drift is enabled in the profile (off-by-default)
**When** the Agent is idle between actions
**Then** small cursor movements to non-target positions occur at the configured frequency and magnitude; camera drift occurs at the configured rate

**Given** error injection probability is set to 2% in the profile
**When** 200 actions are executed
**Then** approximately 2–6 deliberate misclicks occur; each is followed by a corrective action within one decision cycle; each override is logged as an `override` event in `sessions.db`

**Given** an `Action` is produced by the FSM policy
**When** it is dispatched
**Then** it must pass through the caller's `HSL` instance before reaching the OS input API; no code path bypasses HSL (AD-8)

---

### Story 3.5: Shadow Mode — Full HSL Shaping Without OS Output

As Ion,
I want a `--shadow` launch flag that runs the full HSL shaping pipeline but suppresses all OS input API calls,
So that I can validate the bot's behavioral fingerprint against my recorded play before any live session (FR-24).

**Acceptance Criteria:**

**Given** an Agent is started with `--shadow` flag
**When** the policy produces actions
**Then** all actions pass through HSL (Bézier path computed, timing sampled, fatigue applied) and are written to the session log; no mouse or keyboard events are sent to Windows

**Given** a Shadow Mode session completes
**When** the session log is inspected
**Then** the session record has `mode: shadow`; all shaped actions (including Bézier path, timing value, fatigue factor) are logged; the log is clearly distinguishable from a live session

**Given** `--shadow` flag is present at launch
**When** the Agent is running
**Then** there is no runtime mechanism to switch to live mode; mode is fixed at process start

---

## Epic 4: Fishing Mode (Phase 1 Gate)

Ion can start an automated fishing session on a single game window. The bot casts, detects fish tension via YOLO, reels in, and loops for a full 1-hour uninterrupted session. Character identification works on startup. This is the Phase 1 gate.

> Execution-readiness note: Epic 4 is the correct Phase 1 gate, but it is not ready for execution as a single story bundle. Story 4.1 must be decomposed into smaller implementation chunks before work begins, and the 60-minute run remains an end-to-end validation gate rather than the only acceptance measure for the state machine. The deterministic cast/wait/reel harness is required before approving runtime behavior under real game conditions.

### Story 4.1: Agent Base Loop — Capture-to-Policy Single-Window Pipeline

> Implementation note: Split this story into smaller execution units before implementation: (a) capture queue + backpressure/eviction semantics, (b) inference client + latency logging, (c) state-machine tick orchestration, and (d) HSL + OS output handoff. Each chunk must have an explicit test harness and no hidden cross-stage timing assumptions.

As Ion,
I want the full single-window pipeline wired end-to-end: capture thread → Inference Client → PolicyQueue → FSM base → HSL → OS input,
So that a running Agent process completes one perception-decision-action tick per frame and I can plug in real FSM states on top of the working loop (FR-5 base).

**Acceptance Criteria:**

**Given** a single Agent process is started with a valid profile
**When** the main loop runs
**Then** each tick: one frame is captured, sent to GPU Server, `PerceptionResult` returned, FSM state handler invoked, resulting `Action` passed through HSL, dispatched to OS input; the full tick latency is logged and the tick ID is emitted so queue eviction and latency backpressure can be traced deterministically

**Given** the FSM is in a stub IDLE state that produces a no-op action
**When** the loop runs for 60 seconds
**Then** the Agent completes ≥500 ticks (≥~8/s); no tick causes an unhandled exception; all ticks are logged to `sessions.db`; the loop remains stable when one frame is delayed by up to 2x the normal inference budget

**Given** a downstream stage (e.g., GPU Server) is slow for one tick
**When** the capture thread continues running
**Then** oldest frames are evicted from FrameQueue; the capture thread is never blocked; no backlog causes latency to cascade across subsequent ticks; the dropped-frame count is logged with the queue state

**Given** the base loop is under test in a deterministic harness
**When** cast, wait, and reel transitions are simulated
**Then** each state transition is replayable from a seeded input sequence and the same state machine outcome is produced across runs without dependence on wall-clock timing

---

### Story 4.2: Character Identification on Startup

As Ion,
I want the Agent to scan the bound game window at startup and determine the active character class via skill bar layout fingerprinting before starting the control loop,
So that the correct agent profile is assigned automatically and I am only prompted on ambiguous cases (FR-15).

**Acceptance Criteria:**

**Given** a Warlord game window is the bound window
**When** the Agent starts without `--class` flag
**Then** YOLO detects skill bar icons and identifies the window as `warlord`; `warlord.yaml` is loaded; identification result is logged; the accepted confidence threshold for automatic assignment is defined as `>= 0.75` for `warlord` detection

**Given** identification confidence is below the configured threshold (`< 0.75`)
**When** the Agent starts
**Then** the control loop is halted; Ion is prompted in the terminal to manually confirm the class assignment before the loop begins; the detection result, confidence value, and fallback path are logged

**Given** `--class warlord` flag is passed explicitly
**When** the Agent starts
**Then** identification scan is skipped and the specified profile is loaded directly; the override is logged as an explicit operator decision

**Given** the startup identification result is ambiguous or fails the threshold but the user chooses a profile manually
**When** the loop launches
**Then** the chosen profile remains active for the session and the ambiguity is recorded in `sessions.db` for later tuning

---

### Story 4.3: Fishing FSM — Cast and Wait States

As Ion,
I want the Fishing Mode FSM to implement IDLE → CASTING → WAITING states where the bot casts the fishing rod and waits for a bite event,
So that the first half of the fishing loop runs autonomously and timeouts return cleanly to IDLE (FR-25 partial).

**Acceptance Criteria:**

**Given** the Agent is in IDLE state with Fishing Mode profile loaded
**When** the FSM tick runs
**Then** the Agent transitions to CASTING; the rod cast key sequence is executed via HSL; the FSM transitions to WAITING

**Given** the FSM is in WAITING state
**When** no bite event is detected within the configured timeout
**Then** the FSM transitions back to IDLE cleanly; the timeout event is logged; the next tick begins a new cast cycle

**Given** the FSM is in CASTING or WAITING
**When** a session halt signal is received
**Then** the current state is abandoned safely; the Agent transitions to a stopped state and produces no further input

---

### Story 4.4: Fishing FSM — Tension Detection and Reel (Phase 1 Gate Complete)

As Ion,
I want the Fishing FSM to detect a fish tension event via YOLO and execute the reel input, completing the full cast-to-reel loop so the bot sustains 1 hour of uninterrupted autonomous fishing,
So that the Phase 1 gate is met and the full end-to-end pipeline is validated on a real use case (FR-25 completion).

**Acceptance Criteria:**

**Given** the FSM is in WAITING state and a tension visual indicator is present in the game frame
**When** the YOLO detection returns a tension class detection above the configured confidence threshold (`>= 0.80`)
**Then** the FSM transitions to REELING; the reel input key sequence is executed via HSL; the FSM returns to IDLE; the confidence score and tension window are logged

**Given** the bot runs the fishing loop for 60 uninterrupted minutes
**When** the session ends
**Then** zero unhandled exceptions have occurred; the session log shows a continuous sequence of cast/wait/reel cycles; no human input was required; this is treated as the end-to-end validation gate for Epic 4 and not as the sole acceptance criterion for the state machine

**Given** a bite event is missed (YOLO confidence below threshold during the bite window)
**When** the timeout expires in WAITING state
**Then** the FSM returns to IDLE and begins the next cast; no error state is entered; the missed-tension event and timeout are logged for operational review

**Given** the cast/wait/reel logic is under test in a deterministic harness
**When** a seeded sequence of frame results is replayed
**Then** the resulting state transitions and actions are identical across repeated runs, allowing approval of the runtime implementation before live use

---

## Epic 5: Party Orchestration

WL Agent and PP Agent exchange state over the Party Bus. PP buff Safety Check works correctly. The Orchestrator monitors heartbeats and halts both agents on missed heartbeats.

### Epic 5 Shared Contracts

- **PartyState payload:** Each state message uses the existing JSON envelope `{agent_id, type: "party_state", payload}`. `payload` is the complete serialized `PartyState` object and contains exactly `fsm_state` (string), `hp_percent` (0-100 number), `mp_percent` (0-100 number), `position` (`[x, y]` integer frame-pixel coordinates, origin top-left), `buff_presence` (map of buff name to boolean), and `heartbeat_timestamp` (Unix timestamp). Agents publish one complete snapshot on every policy tick; snapshots are replaced atomically and are never merged.
- **Peer-state freshness:** A subscriber retains the last valid snapshot as a read-only value and records its local `received_at` separately. After `HEARTBEAT_INTERVAL * HEARTBEAT_MISSED_COUNT` (default 3 seconds) without a valid message from that peer, the snapshot is marked stale and a `party_bus_disconnected` warning is logged. Stale data is not treated as current input; the Orchestrator's halt protocol remains authoritative for stopping both agents.
- **Heartbeat payload:** Heartbeats use the same Agent PUB endpoint and JSON envelope `{agent_id, type: "heartbeat", payload: {heartbeat_timestamp}}`; the Orchestrator records the observation time on receipt and does not consume `GameState` or `PartyState`.
- **Session event contract:** Required event types are `party_bus_disconnected`, `buff_cast_deferred`, `heartbeat_missed`, `session_halt`, `session_resume`, and `party_bus_reconnected`. Every payload includes `agent_id` or `agent_ids` as applicable, `session_id`, and `reason`; state-related events additionally include `fsm_state` or `prior_fsm_state` where applicable. Events are appended to `data/sessions.db` using the existing `source`, `type`, and `payload_json` columns.
- **Halt control:** The Orchestrator publishes `{type: "session_halt", payload: {session_id, reason: "heartbeat_missed", missed_agent_id, missed_count}}` on its control PUB/SUB endpoint. Both agents latch `PAUSED`, capture their pre-halt FSM state once, cancel or abandon pending actions, and produce no OS input. A heartbeat resuming does not auto-resume a halted session; an explicit operator resume after both agents are healthy publishes `{type: "session_resume", payload: {session_id, reason: "operator_resume", agent_ids}}`, after which each agent restores its captured pre-halt FSM state and logs the transition. The Orchestrator signals processes; it does not restart them.

### Story 5.1: Party Bus — PartyState PUB/SUB Exchange

As Ion,
I want each Agent to publish its own `PartyState` (FSM state, HP%, MP%, position, buff presence) each tick and subscribe to the peer agent's `PartyState`,
So that each Agent has real-time visibility into the other's state without shared memory and per the ZeroMQ PUB/SUB pattern (FR-6, AD-1, AD-4, AD-11).

**Acceptance Criteria:**

**Given** WL Agent and PP Agent are both running with PUB sockets bound
**When** WL Agent publishes a `PartyState` with `fsm_state: PULLING`
**Then** PP Agent's SUB socket receives the complete `party_state` envelope within one policy tick; PP Agent's policy loop can read `peer_party_state.fsm_state == PULLING`; the serialized payload conforms to the Epic 5 PartyState contract

**Given** the Party Bus message is published
**When** the PP Agent reads the peer state
**Then** PP Agent's own `GameState` is not modified; only the read-only `peer_party_state` field is updated (AD-4)

**Given** multiple peer messages arrive while the policy loop is processing
**When** the next message is accepted
**Then** the complete latest snapshot replaces the previous snapshot atomically; no fields are merged across messages and no partially updated snapshot is observable

**Given** the Party Bus connection is lost (WL Agent process killed)
**When** PP Agent attempts to read peer state
**Then** the last valid `PartyState` is retained as read-only, marked stale after the configured missed-heartbeat window, PP Agent does not crash, and a `party_bus_disconnected` warning and session event are logged; the Orchestrator halt protocol is used for the coordinated pause

---

### Story 5.2: PP Buff Safety Check

As Ion,
I want the PP Agent to evaluate a Safety Check before every timed buff cast, passing only when no mobs are within the configured aggro-risk radius (in pixel coordinates) and WL is not in PULLING state,
So that PP never draws mob aggro by casting at the wrong moment — and if the check fails, the cast is deferred and retried, never silently skipped (FR-6).

**Acceptance Criteria:**

**Given** PP buff timer has expired
**When** no mobs are within the pixel-coordinate aggro-risk radius (per AD-10b) and WL `PartyState.fsm_state` is not PULLING
**Then** Safety Check passes; the buff cast is executed immediately

**Given** a current-frame `PerceptionResult` contains mob detections and PP has a current-frame character position
**When** the Safety Check evaluates proximity
**Then** it uses each mob detection's `bbox_xyxy` center and PP's `GameState.character_position`, both in captured-frame pixels with origin top-left; a mob is within the risk radius when Euclidean distance is less than or equal to the configured radius; no game-world coordinates are used

**Given** PP buff timer has expired
**When** WL `PartyState.fsm_state` is `PULLING`
**Then** Safety Check fails even when no mob is currently inside the radius; `FIGHTING` and other non-`PULLING` WL states do not fail the state-only condition

**Given** PP buff timer has expired
**When** a mob is detected within the aggro-risk radius in the current frame
**Then** Safety Check fails; the retry timer starts at the time of the failed check; the buff cast is deferred by the configured retry interval; a `buff_cast_deferred` event records the failed condition and next eligible timestamp; PP continues normal non-cast policy-loop work while waiting

**Given** Safety Check has failed repeatedly
**When** the retry interval elapses
**Then** the check is re-evaluated; the cast executes as soon as the check passes; the cast is never permanently skipped

---

### Story 5.3: Orchestrator Heartbeat Monitor & Session Halt

As Ion,
I want the Party Orchestrator to monitor heartbeat messages from both agents and trigger a session halt on both when either agent misses N consecutive heartbeats,
So that a stuck or crashed agent never leaves the other agent running unmonitored against the live game (FR-13, FR-14).

**Acceptance Criteria:**

**Given** both agents are running and publishing heartbeats piggybacked on their Party Bus PUB messages
**When** the Orchestrator's SUB sockets receive heartbeats
**Then** the Orchestrator records the last-seen timestamp per agent from receipt time and no halt is triggered while each heartbeat arrives before `HEARTBEAT_INTERVAL * HEARTBEAT_MISSED_COUNT`

**Given** one agent stops publishing (process killed or hung)
**When** N consecutive heartbeat intervals (configurable, default 3) pass without a message
**Then** the Orchestrator emits one `session_halt` control message with `reason: heartbeat_missed`, `missed_agent_id`, and `missed_count`; logs `heartbeat_missed` and `session_halt` events to `sessions.db`; both agents capture their current FSM state, enter latched `PAUSED`, cancel pending actions, and produce no further OS input

**Given** a halted session is recovered (agent restarted and heartbeats resume)
**When** the Orchestrator detects resumed heartbeats
**Then** the Orchestrator logs `party_bus_reconnected` with both agents' health status, but does not automatically resume input; only after both agents are healthy and an explicit `session_resume` control message with `{session_id, reason: "operator_resume", agent_ids}` is received do agents restore the FSM state captured at halt, log `session_resume`, and continue

**Given** the Orchestrator has emitted a halt for a missed heartbeat
**When** a single agent process is still running
**Then** the Orchestrator signals both agents and does not restart either process; process restart, if needed, remains an explicit Tray/UI operation before the resume protocol

---

## Epic 6: Combat Mode & Session Lifecycle

Ion can start a full WL+PP combat farming session. The bot handles the complete lifecycle: combat loop, death recovery, inventory-full town return, and clean session cap shutdown — running for 4+ hours without intervention.

### Story 6.1: Warlord Combat FSM — Pull, Fight, Loot

As Ion,
I want the Warlord Agent to implement IDLE → PULLING → FIGHTING → LOOTING FSM states driven by PerceptionResult detections,
So that the WL autonomously executes the pull-AoE-loot combat cycle and the BC Policy module selects within-state action sequences (FR-5 WL Combat).

**Acceptance Criteria:**

**Given** the WL Agent is in IDLE and a mob detection appears in the mob_area ROI
**When** the FSM evaluates the transition condition
**Then** WL transitions to PULLING; the BC Policy module for PULLING selects and executes the pull skill sequence via HSL

**Given** WL is in PULLING and the mob reaches melee range (detection position shifts to center frame)
**When** the transition condition is met
**Then** WL transitions to FIGHTING; the AoE skill rotation BC Policy executes

**Given** WL is in FIGHTING and all mob detections are gone (mob_area ROI clear)
**When** the transition condition is met
**Then** WL transitions to LOOTING; loot key sequence executes; WL returns to IDLE after loot window closes or timeout
**And** each FSM transition is written to `sessions.db` events table within one decision cycle

---

### Story 6.2: Prophet Buff Cycle FSM — Timer-Driven Buffing

As Ion,
I want the PP Agent to manage buff timers independently and enter BUFFING state to cast each buff on timer expiry, with all casts gated by Safety Check,
So that WL maintains full buffs throughout the session without Ion's involvement (FR-5 PP Combat, FR-6 buff cycle).

**Acceptance Criteria:**

**Given** PP buff timers are initialized from `prophet.yaml` on session start
**When** a buff timer expires
**Then** PP transitions from IDLE to BUFFING; the Safety Check is evaluated; if it passes, the buff cast executes via HSL; PP returns to IDLE after casting

**Given** PP is mid-BUFFING and WL's `PartyState.fsm_state` changes to PULLING
**When** Safety Check is re-evaluated
**Then** the remaining buff casts are deferred until WL exits PULLING; no partial buff sequence is abandoned without retry

**Given** a full buff cycle (all timed buffs) has been cast
**When** the session log is inspected
**Then** each buff cast appears as a structured event with timestamp, buff name, and Safety Check pass/fail result

---

### Story 6.3: Death Detection & Full Party Recovery

As Ion,
I want both agents to detect the death state, execute the respawn and rebuff sequence, and resume their prior FSM states — completing the full party recovery within 60 seconds,
So that the session continues automatically after a party wipe without Ion's intervention (FR-16).

**Acceptance Criteria:**

**Given** WL Agent detects the death state (death screen detection via YOLO in PerceptionResult)
**When** the FSM evaluates the GameState
**Then** WL transitions to DEAD; the respawn key sequence executes; WL navigates to the buff restoration position

**Given** WL has respawned and reached the buff spot
**When** PP Agent detects WL's `PartyState` has transitioned from DEAD to a recoverable state
**Then** PP casts the full buff cycle on WL; upon completion, both agents resume their pre-death FSM states

**Given** the death event was detected
**When** full party recovery completes
**Then** elapsed time from death detection to both agents active is ≤60 seconds; the death event and recovery sequence are logged to `sessions.db` with timestamps

---

### Story 6.4: Inventory-Full Detection & Town Return

As Ion,
I want the system to detect a full inventory condition and suspend the combat loop, execute a safe return to town, handle loot per configured rules, and resume the farming loop automatically,
So that the session never silently discards loot or requires Ion to manage inventory (FR-17).

**Acceptance Criteria:**

**Given** the inventory-full visual indicator is detected in the game frame (YOLO or OCR)
**When** the condition is detected during a combat loop
**Then** the combat loop is suspended; WL transitions to a RETURNING state; the town return movement sequence executes

**Given** WL is in town after inventory-full return
**When** loot rules from the profile are evaluated
**Then** items are deposited or dropped per the configured rules; no item is silently discarded without a profile rule authorizing it

**Given** loot handling is complete
**When** the return sequence finishes
**Then** both agents resume the farming loop from IDLE; the inventory return event is logged to `sessions.db`

---

### Story 6.5: Session Cap & Clean Shutdown

As Ion,
I want each session to enforce a configurable maximum duration and execute a clean shutdown sequence — returning both characters to a safe position, completing PP's final buff cycle, and stopping all OS input,
So that sessions end predictably and safely even if Ion walks away and forgets about them (FR-18).

**Acceptance Criteria:**

**Given** a session reaches the configured cap (default 4–6 hours)
**When** the cap timer fires — even mid-combat-cycle
**Then** the current combat action is abandoned; WL moves to a safe position before stopping; no further combat actions are taken

**Given** the session cap has been reached and WL is in a safe position
**When** PP executes the shutdown buff cycle
**Then** PP casts a final round of buffs; both characters enter an idle standing state; the bot produces no further keyboard or mouse input

**Given** shutdown completes
**When** `sessions.db` is inspected
**Then** the session record has a `ended_at` timestamp; a `session_cap_shutdown` event is present with the final FSM states of both agents

---

## Epic 7: Training Pipeline

Ion can record a gameplay session, run auto-prelabeling, correct labels in Label Studio, retrain a YOLO model, and have it atomically deployed. YouTube footage can be ingested into the label queue.

### Story 7.1: Recording Mode — Dual-Write Frame Capture & Input Log

As Ion,
I want Recording Mode activated by a `--record` flag that switches the Agent capture thread to dual-write (pipeline + disk archive) and activates a pynput listener logging all keyboard and mouse inputs,
So that I can capture my own gameplay as labeled training data without interfering with manual play (FR-19, AD-13).

**Acceptance Criteria:**

**Given** an Agent is started with `--record` flag
**When** the capture thread runs
**Then** frames are written to `recordings/<session_id>/frames/` AND pushed to the pipeline simultaneously; the game client does not drop below 30 FPS

**Given** Recording Mode is active
**When** Ion presses keys or moves the mouse
**Then** each input event is logged to `recordings/<session_id>/inputs.jsonl` with a timestamp synchronized to the frame sequence

**Given** the hotkey to stop Recording Mode is pressed
**When** recording ends
**Then** the frame archive and input log are finalized and closed cleanly; the directory is ready for prelabeling

---

### Story 7.2: Auto-Prelabeling Pipeline

As Ion,
I want `python -m lagent.train prelabel --recording <path>` to apply the current YOLO models to all captured frames and produce a Label Studio–importable annotation file,
So that I only need to correct the labels that YOLO got wrong — not annotate everything from scratch (FR-20).

**Acceptance Criteria:**

**Given** a recording directory containing captured frames
**When** `python -m lagent.train prelabel --recording recordings/<session_id>` is run
**Then** the current `common/current.pt` and class-specific `current.pt` are applied to all frames; a `prelabeled.json` annotation file is written to the recording directory in Label Studio import format

**Given** a 30-minute recording (≈18,000 frames at 10 FPS)
**When** prelabeling runs on the GTX 1070 Ti
**Then** prelabeling completes in ≤15 minutes

**Given** the `prelabeled.json` file exists
**When** it is imported into a local Label Studio project
**Then** all frames load with bounding box annotations; no format conversion is required

---

### Story 7.3: Model Training & Atomic Deployment

As Ion,
I want `python -m lagent.train train --recording <path>` to fine-tune the YOLO model from corrected labels, log the run to local MLflow, and atomically replace `current.pt` only after the new model passes validation,
So that I never lose a working model and training history is fully tracked locally (FR-21, AD-7).

**Acceptance Criteria:**

**Given** a recording directory with corrected Label Studio annotations
**When** `python -m lagent.train train --recording recordings/<session_id>` is run
**Then** YOLOv8-nano is fine-tuned; the run is logged to local MLflow with model version, dataset snapshot, and key metrics (mAP, loss)

**Given** training completes and the new model passes the configured validation threshold
**When** deployment runs
**Then** the new model is written to a temp path and then moved to `models/<class>/current.pt` via `os.replace()` atomically; the prior version is archived (not deleted)

**Given** training completes on the GTX 1070 Ti from a 30-minute labeled recording
**When** the run finishes
**Then** wall-clock time is ≤2 hours; the new model produces detections when loaded in the GPU Inference Server

---

### Story 7.4: YouTube Frame Ingestion

As Ion,
I want `python -m lagent.train ingest --url <youtube-url> --fps <n>` to download the video via yt-dlp, extract frames via OpenCV, and feed them into the prelabeling pipeline,
So that I can supplement my own recordings with publicly available gameplay footage without any external API credentials (FR-22).

**Acceptance Criteria:**

**Given** a YouTube URL pointing to a public Asterios x55 gameplay video
**When** `python -m lagent.train ingest --url <url> --fps 5` is run
**Then** yt-dlp downloads the video to a temp directory; OpenCV extracts frames at 5 FPS; frames are written to a recording directory in the same format as captured recordings

**Given** a 10-minute video is ingested
**When** the process completes
**Then** total time (download + extraction + prelabeling) is ≤5 minutes on the GTX 1070 Ti

**Given** extracted frames are in the recording directory
**When** they appear in the Label Studio label queue
**Then** they are indistinguishable in format from frames captured by Recording Mode; no special handling is required

---

## Epic 8: Tray UI & Status Overlay

Ion can control sessions entirely from the system tray: start/stop sessions with profile selection, toggle Recording Mode, and monitor per-agent FSM state, HP/MP, and session timer in a minimal always-on-top overlay.

### Story 8.1: System Tray Icon & Session Control Menu

As Ion,
I want a Windows system tray icon that provides a right-click context menu for starting and stopping sessions with profile selection,
So that I can launch and stop the bot without opening a terminal window (UX-1, UX-2, AD-5).

**Acceptance Criteria:**

**Given** `python -m lagent.ui` is running
**When** Ion right-clicks the tray icon
**Then** a context menu appears with: "Start Session ▶" (submenu: Fishing / Combat / Shadow), "Stop Session", "Recording Mode" (toggle), "Status Overlay", "Exit"

**Given** Ion selects "Start Session → Combat"
**When** the menu item is activated
**Then** the Tray/UI process spawns GPU Server, WL Agent (Combat profile), PP Agent (Combat profile), and Orchestrator as subprocesses; a session record is created in `sessions.db`; "Stop Session" becomes enabled

**Given** Ion selects "Stop Session"
**When** the menu item is activated
**Then** all spawned child processes receive SIGTERM; the Tray/UI waits for clean shutdown; the session record is updated with `ended_at`

---

### Story 8.2: Status Overlay Window

As Ion,
I want a borderless semi-transparent always-on-top PyQt6 window that shows per-agent status (FSM state, HP%, MP%, session timer) updated in real-time,
So that I can monitor session health at a glance without disrupting the game client (UX-3, UX-4, UX-5).

**Acceptance Criteria:**

**Given** a session is running and the Status Overlay is toggled on
**When** the overlay renders
**Then** it shows two rows (WL and PP) each with: agent name, current FSM state label, HP% bar, MP% bar, elapsed session timer; updates reflect `sessions.db` events within 2 seconds

**Given** the overlay is displayed
**When** the game client is in focus
**Then** the overlay remains visible and always-on-top; it does not steal focus or intercept mouse input from the game client

**Given** no session is running
**When** the overlay is displayed
**Then** both agent rows show "Stopped" state; no errors or blank fields

---

### Story 8.3: Session State Wiring & Tray Feedback

As Ion,
I want the tray icon and menu state to reflect the current session status in real-time,
So that I always know at a glance whether the bot is running, recording, or idle without opening any window (UX-6).

**Acceptance Criteria:**

**Given** a session is running
**When** Ion hovers over the tray icon
**Then** a tooltip shows: session mode, active profile, elapsed time (e.g., "Combat · warlord+prophet · 01:24:37")

**Given** Recording Mode is toggled on from the tray menu
**When** the toggle activates
**Then** the tray icon visual changes to indicate recording state; the Agent process is restarted with `--record` flag; the menu item shows a checkmark

**Given** a session halts unexpectedly (Orchestrator triggers halt)
**When** the halt occurs
**Then** the tray icon updates to an error/halted state; a Windows system notification is shown with "Session halted — check status overlay"; the tray menu enables "Start Session" again
