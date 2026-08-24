---
title: "LAgent — Autonomous L2 Asterios x55 AI Bot"
status: draft
created: 2026-08-04
updated: 2026-08-04
---

# PRD: LAgent

## 0. Document Purpose

This PRD defines the functional requirements for LAgent, a locally-operated autonomous bot for Lineage 2 on the Asterios x55 private server. The primary reader is Ion (sole operator and developer) and any downstream workflow owners (architecture, epics/stories). The document uses Glossary-anchored vocabulary throughout. All capability terms are defined in §3. Technical mechanism decisions (exact model architectures, transport protocols, VRAM budgets) live in the accompanying `addendum.md`; this PRD specifies *what* the system must do, not *how* it is implemented.

Sources informing this PRD: `brief.md` and `addendum.md` (brief-LAgent-2026-08-04).

---

## 1. Vision

LAgent is a fully local AI system that plays Lineage 2 autonomously on the Asterios x55 private server, managing a 2-character party (Warlord + Prophet) without human intervention after initial login. It perceives the game exclusively through screen capture and acts exclusively through simulated mouse and keyboard input — no memory reading, no packet injection — making its footprint indistinguishable from human play at the OS and network level.

The system ships with a first-party training pipeline: Ion records his own gameplay directly in the app, optionally supplements with processed YouTube footage, and produces class-specific vision and behavior models on local hardware. Anti-detection is a first-class design requirement implemented before any live testing, not bolted on afterward.

The immediate delivery target is the Asterios x55 server, with **Fishing automation** as the Phase 1 proof-of-concept and **WL+PP combat farming** as the V1 milestone. The training pipeline is the system's enduring strategic value; the bot is its first customer.

---

## 2. Target User

### 2.1 Jobs To Be Done

- Run extended autonomous farming sessions (4+ hours) on Asterios x55 without supervision.
- Maintain zero ban risk — no client modification, behavioral fingerprint indistinguishable from human play.
- Train new bot behaviors (e.g., fishing → combat) within a 2-hour cycle using personal gameplay recordings.
- Control all training data locally — no cloud services, no external data exposure.
- Recover gracefully from in-game events (death, full inventory) without human intervention.

### 2.2 Non-Users (v1)

- Other L2 players or other servers — the system is trained specifically on Asterios x55 UI; it is not a general-purpose L2 bot.
- Operators wanting 3-window (Spoiler) or offline dancer (BD/SWS) configurations — explicitly deferred to Phase 3/4.

### 2.3 Key User Journeys

- **UJ-1. Ion starts an autonomous farming session.** Ion logs in both characters manually, launches LAgent, and selects the WL+PP combat profile. The bot identifies both windows, assigns roles, and begins the farming loop. Ion walks away. Four hours later the session is still running.
- **UJ-2. Ion trains a new behavior from a recording.** Ion activates Recording Mode, plays fishing manually for 30 minutes, stops the recording, and kicks off the label + train pipeline. Within 2 hours a new fishing model is deployable.
- **UJ-3. Ion ingests YouTube footage for supplementary training data.** Ion pastes a YouTube URL into the ingestion UI, selects target FPS and class, and the pipeline downloads, extracts frames, and feeds them into the label queue automatically.
- **UJ-4. The bot recovers from a party death.** Both characters die during a session. The bot detects the death state, respawns, navigates to the buff spot, PP rebuffs WL, and combat resumes — without Ion's involvement.

---

## 3. Glossary

- **Agent** — A single autonomous control loop bound to one game window (WL Agent or PP Agent). Each agent runs the full perception → decision → action cycle independently.
- **Party Orchestrator** — The inter-process coordinator that synchronizes state between the WL Agent and PP Agent via the Party Bus.
- **Party Bus** — The ZeroMQ message channel over which Agents publish state events and subscribe to peer state.
- **Session** — A single continuous bot run from startup to shutdown (or crash). Sessions are capped at 4–6 hours.
- **Perception Pipeline** — The ordered chain of capture → detect → OCR that transforms a raw screen frame into structured game state.
- **Game State** — The structured representation of one Agent's world at a point in time: HP/MP values, active buffs, mob positions, loot presence, character position, UI mode.
- **Behavior Policy** — The decision function that maps Game State (+ Party State from the Orchestrator) to the next Action for an Agent. Implemented as a combined FSM + BC Policy.
- **BC Policy** (Behavioral Cloning Policy) — A learned decision function trained via imitation learning on operator recordings. Handles fine-grained within-state action selection and timing alongside the FSM.
- **Safety Check** — A precondition evaluation performed by the PP Agent before any timed buff cast, verifying that casting will not attract unwanted mob aggro to PP.
- **Common Model** — A shared YOLO model family covering class-agnostic detections applicable across all behavior profiles (e.g., fishing mechanics, loot on ground, generic UI elements).
- **Class Model** — A class-specific YOLO model family covering detections unique to a character class or behavior profile (e.g., WL mob targeting, PP buff icon states).
- **Action** — A single discrete output: mouse move, mouse click, key press, or wait. All Actions are executed with human-simulation shaping.
- **Human Simulation Layer** — The subsystem that shapes all Actions with Bézier mouse curves, keystroke timing noise, fatigue drift, and micro-drift to produce a human-like input fingerprint.
- **Recording Mode** — An operational mode in which the app captures screen frames and Ion's actual keyboard/mouse inputs simultaneously, producing labeled training data.
- **Training Pipeline** — The offline process that takes labeled frames and input logs and produces updated vision and behavior models.
- **Label Pipeline** — The stage of the Training Pipeline responsible for auto-prelabeling frames (via YOLO) and surfacing them for manual correction in a labeling tool.
- **ROI** (Region of Interest) — A defined sub-region of a game window (e.g., HP bar, buff icon strip, mob area) extracted per frame for targeted analysis.
- **Fishing Mode** — The Phase 1 behavior profile: cast → wait → tension detection → reel.
- **Combat Mode** — The V1 primary behavior profile: WL pull → AoE → loot; PP buff cycle + heal.
- **Fatigue Model** — A time-varying latency multiplier that increases action delays over a session to simulate human tiredness, with periodic "break" resets.
- **Break** — A simulated pause period (5–15 minutes, no input) triggered by the Fatigue Model to mimic human rest patterns.

---

## 4. Features

### 4.1 Screen Capture & Perception Pipeline

**Description:** Each game window is captured at ~10 FPS. Captured frames are processed through a Perception Pipeline: ROI extraction, YOLO-based detection of mobs / loot / UI elements / character state, and OCR for numeric values (HP, MP, buff counts). The output is a structured Game State consumed by the Behavior Policy. The pipeline runs independently per Agent window. Realizes UJ-1, UJ-4.

**Functional Requirements:**

#### FR-1: Per-window screen capture at target rate

The Perception Pipeline shall capture each bound game window at a configurable target rate (default: 10 FPS) and make each frame available for ROI extraction within 10 ms of capture.

**Consequences:**
- End-to-end capture-to-frame-available latency is ≤10 ms on the target hardware (GTX 1070 Ti, Windows).
- Capture continues independently per window; one window's lag does not block the other.

#### FR-2: ROI extraction

The Perception Pipeline shall extract a configurable set of named ROIs from each captured frame before passing to detection. ROI positions are defined per class in a YAML agent profile.

**Consequences:**
- ROI coordinates are loaded from the active agent profile at Session start.
- Changing ROI positions requires only a profile update, not a code change.

#### FR-3: Object and state detection

The Perception Pipeline shall apply two YOLO model families per frame: a **Common Model** for class-agnostic detections (loot on ground, fishing mechanics, generic UI elements) and a **Class Model** for class-specific detections (mob targeting for WL, buff icon states for PP). Both model outputs are merged into the Game State.

**Consequences:**
- Both model inferences together complete within 100 ms per frame per window on target hardware.
- Detections below a configurable confidence threshold (per model family) are ignored.
- The Common Model is shared across all behavior profiles; only the Class Model is replaced when switching profiles.
- Each model family is independently versioned and fine-tunable.

#### FR-4: Numeric OCR

The Perception Pipeline shall apply OCR to the HP bar, MP bar, and buff-timer ROIs to extract current numeric values. Values are included in the Game State.

**Consequences:**
- OCR runs on GPU when available; degrades gracefully to CPU.
- EasyOCR is used with default pre-trained weights; no custom fine-tuning is required for Asterios x55 fonts.

---

### 4.2 Behavior Policy & Decision Engine

**Description:** Each Agent runs a combined FSM + BC Policy. The FSM governs high-level state transitions (IDLE → PULLING → FIGHTING → LOOTING → RETURNING → DEAD → BUFFING) driven by Game State detections. Within each FSM state, the BC Policy — trained via imitation learning on Ion's recordings — selects fine-grained action sequences and timing. This combined architecture provides structured, predictable macro-behavior from the FSM with human-like micro-behavior from the BC Policy. Realizes UJ-1, UJ-4.

**Functional Requirements:**

#### FR-5: Combined FSM + BC behavior policy

Each Agent shall implement a per-class FSM for high-level state management combined with a BC Policy for within-state action selection. The FSM defines states, transition conditions (from Game State inputs and Party State), and which BC Policy module handles action selection in each state. Transitions and policy module bindings are configurable in the agent YAML profile.

**Consequences:**
- All FSM states, transitions, and BC Policy module bindings are enumerated in the agent profile, not hardcoded.
- Unrecognized Game State combinations default to IDLE and log a warning.
- The BC Policy modules are independently trainable and versioned per class and per FSM state.

#### FR-6: Party State consumption and PP buff Safety Check

Each Agent shall subscribe to the Party Bus and incorporate the peer Agent's published state into its own decision cycle. The PP Agent shall maintain its own buff-cycle timers for self-buffs and WL personal buffs, ticking independently of WL state. Before executing any timed buff cast, the PP Agent shall evaluate a Safety Check to confirm the cast will not attract unwanted mob aggro.

**Consequences:**
- PP Agent does not wait for WL to request a rebuff — it casts on timer expiry subject to Safety Check passing.
- Safety Check passes when: no mobs are within the PP's configured aggro-risk radius AND WL is not in a state (PULLING) that would redirect newly-attracted mobs to PP.
- If Safety Check fails, the buff cast is deferred by one configurable retry interval and re-evaluated; it is never skipped entirely.
- WL Agent publishes its state transitions to the Party Bus within one decision cycle of transition.
- PP Agent does not produce offensive action sequences outside of the BUFFING FSM state.

#### FR-7: Per-class YAML agent profile

Agent behavior parameters (FSM transitions, skill key bindings, buff timer durations, ROI positions, confidence thresholds, mode-specific flags) shall be defined in a YAML file per character class, validated by a schema on load.

**Consequences:**
- Loading an invalid profile raises a schema validation error at startup before any Session begins.
- Profiles are hot-reloadable between Sessions without restarting the application.

---

### 4.3 Action Execution & Human Simulation Layer

**Description:** Every Action produced by a Behavior Policy is routed through the Human Simulation Layer before being sent to the OS input API. The layer shapes mouse paths (Bézier curves), keystroke timing (Gaussian noise), macro fatigue (growing latency over session time), micro-drift (idle cursor movement, occasional camera drift), and error injection (rare deliberate misclick followed by correction). Anti-detection shaping is non-optional and cannot be disabled. Realizes UJ-1.

**Functional Requirements:**

#### FR-8: Bézier mouse paths

All mouse moves shall follow a cubic Bézier curve with randomized control point offsets. Speed profiles shall follow a bell curve (slow start, fast middle, slow end) with per-path random variance.

**Consequences:**
- Control point offsets are drawn from a configurable uniform range (default: ±15–30 px).
- Speed variance is ±10% per path, drawn independently.
- Straight-line mouse moves are never produced.

#### FR-9: Keystroke timing noise

Inter-key delays for all key sequences shall be drawn from a per-skill Gaussian distribution. Mean and standard deviation for each skill's timing are captured from Ion's recordings during the Training Pipeline.

**Consequences:**
- Default timing parameters are used at bootstrap (before training data is collected).
- Timing parameters are updated per-skill when a new training run completes.

#### FR-10: Fatigue model

Action latency shall be multiplied by a Fatigue Factor that grows monotonically over Session time. The Fatigue Factor resets after each Break.

**Consequences:**
- Fatigue Factor grows on a configurable schedule (default: small increment every 30–60 minutes).
- A Break is triggered automatically when Fatigue Factor reaches a configurable ceiling, or when Session duration reaches the configured session cap (default: 4–6 hours).
- During a Break, no mouse or keyboard input is produced for a randomized duration within the configured break-length range (default: 5–15 minutes).

#### FR-11: Micro-drift

Between Actions, the system shall produce occasional small cursor movements to non-target positions and rare minor camera rotations, drawn from a configurable frequency and magnitude distribution.

**Consequences:**
- Micro-drift frequency is configurable and off-by-default in the agent profile; enabling it is recommended before live testing.

#### FR-12: Error injection

With a configurable low probability (default: 1–3%), the system shall produce a deliberate misclick (targeting a nearby incorrect entity), detect the resulting Game State anomaly, and execute a corrective Action within one decision cycle.

**Consequences:**
- Error injection probability is per-Action-type and configurable in the agent profile.
- The corrective Action is logged as an `override` event in the memlog for session audit.

---

### 4.4 Party Orchestrator

**Description:** A lightweight coordinator that runs alongside both Agents, relaying state events between them over the Party Bus (ZeroMQ). The Orchestrator does not make gameplay decisions; it is a message relay and session monitor. Realizes UJ-1, UJ-4.

**Functional Requirements:**

#### FR-13: Party Bus relay

The Party Orchestrator shall relay Agent state events between the WL Agent and PP Agent with sub-10 ms latency.

**Consequences:**
- Loss of Party Bus connectivity triggers a PAUSED state on both Agents and a Session warning log.
- Reconnection restores both Agents to their prior FSM states.

#### FR-14: Session health monitoring

The Party Orchestrator shall monitor both Agents for heartbeat signals at a configurable interval. If either Agent misses N consecutive heartbeats (configurable, default: 3), the Orchestrator shall trigger a Session halt and log the event.

**Consequences:**
- Halted Sessions are safe — no further input is produced after halt.
- The halt event is written to the session log and surfaced to the operator on next launch.

---

### 4.5 Session Lifecycle Management

**Description:** Covers startup identification, death recovery, inventory management, and session shutdown — the full lifecycle of a single autonomous Session. Realizes UJ-1, UJ-4.

**Functional Requirements:**

#### FR-15: Character identification on startup

At Session start, the system shall scan each configured game window and determine which character class is active, assigning the correct agent profile before beginning the control loop.

**Consequences:**
- Identification succeeds on first attempt ≥95% of the time using skill bar layout fingerprinting as the primary signal.
- If identification fails, the system halts and prompts Ion to manually confirm the assignment before proceeding.

#### FR-16: Death detection and recovery

When an Agent detects the death state (via Game State), it shall enter the DEAD FSM state, execute the respawn sequence, navigate to the buff restoration position, and coordinate with PP Agent to rebuff before resuming the prior FSM state.

**Consequences:**
- Full party recovery from death (both characters respawned, rebuffed, resumed) completes within 60 seconds.
- Death events are logged with timestamp and Game State snapshot.

#### FR-17: Inventory-full detection and town return

When any Agent detects a full inventory condition, the system shall suspend the combat loop, execute a safe return to town, deposit or drop loot per configured rules, and resume the farming loop.

**Consequences:**
- No loot is silently discarded without a configured rule authorizing it.
- Town return completes without requiring Ion's intervention.

#### FR-18: Session cap and shutdown

Each Session shall enforce a configurable maximum duration (default: 4–6 hours). On cap, the system executes a clean shutdown: both Agents return to a safe location, PP casts a final buff cycle, and both characters stand idle before the bot stops producing input.

**Consequences:**
- Session cap is enforced even if a combat loop is mid-cycle; the combat loop is abandoned safely (move to safe position first).
- Shutdown sequence is logged as a session event.

---

### 4.6 Training Pipeline

**Description:** The offline system that produces vision and behavior models from labeled recordings. Includes Recording Mode (in-app capture during manual play), auto-prelabeling, manual label correction, model training, and YouTube video ingestion. The Training Pipeline is not user-facing automation; it is an operator workflow. Realizes UJ-2, UJ-3.

**Functional Requirements:**

#### FR-19: Recording Mode

The application shall provide a Recording Mode in which it simultaneously captures game window frames at the configured capture rate and logs Ion's actual mouse and keyboard inputs with timestamps, without interfering with Ion's manual play.

**Consequences:**
- Recording produces a frame archive and a synchronized input log in a configurable output directory.
- Recording overhead does not cause the game client to drop below 30 FPS.
- Recording Mode is activated and deactivated by a hotkey.

#### FR-20: Auto-prelabeling

After a recording session, the system shall apply the current YOLO models (Common + Class) to all captured frames, producing a prelabeled annotation file in Label Studio's import format.

**Consequences:**
- Prelabeling completes at ≥2× real-time speed on target hardware (i.e., 30 minutes of recording prelabeled in ≤15 minutes).
- Prelabeled annotations are importable into Label Studio without format conversion.

#### FR-21: Model training

After label correction, the system shall fine-tune the YOLO model (vision) and update the keystroke timing parameters (behavior) from the labeled recording.

**Consequences:**
- A new behavior model (e.g., Fishing Mode) is trainable to functional quality within 2 hours of labeled recording on target hardware.
- Training runs are tracked in local MLflow; each run logs model version, dataset snapshot, and key metrics.
- Trained models are versioned and the prior version is not overwritten until the new version is validated.

#### FR-22: YouTube frame ingestion

The system shall accept a YouTube URL, download the video using a local downloader, extract frames at a configurable FPS, and feed the extracted frames into the Label Pipeline.

**Consequences:**
- A 10-minute video is fully processed (downloaded + frames extracted + prelabeled) in ≤5 minutes on target hardware.
- No YouTube credentials or API keys are required.
- Extracted frames are stored alongside locally-recorded frames and are indistinguishable in the label queue.

---

### 4.7 Shadow Mode (Good to Have)

**Description:** An observe-only operational mode in which LAgent runs the full Perception Pipeline and Behavior Policy, logs what actions it *would* take, but produces zero actual mouse or keyboard input. Intended for pre-live behavioral validation: Ion can verify that the bot's decision fingerprint looks human before committing to live play. Not required for the Phase 1 gate but recommended before the first live Combat Mode session. Realizes UJ-1 (validation path).

**Functional Requirements:**

#### FR-24: Shadow Mode operation

The system shall support a Shadow Mode flag that, when enabled, routes all Actions through the Human Simulation Layer for logging but suppresses all OS input API calls.

**Consequences:**
- Shadow Mode is activated via a startup flag or UI toggle; it cannot be toggled mid-Session.
- All would-be Actions are logged with full Human Simulation Layer output (Bézier path, timing, fatigue state) to the session log.
- Shadow Mode sessions are clearly labelled in the session log to distinguish from live sessions.
- No game state is affected during Shadow Mode.

**Out of Scope:** Shadow Mode does not simulate game responses (e.g., mob health changes) — it only suppresses input.

---

### 4.8 Behavior Profiles: Fishing Mode (Phase 1 POC)

**Description:** The first complete behavior profile, used to validate the end-to-end pipeline before V1 combat behaviors. Fishing Mode automates the cast → wait → tension detection → reel cycle for a single character window. It exercises the Perception Pipeline, Behavior Policy, Human Simulation Layer, and Training Pipeline without the complexity of a 2-window party. Realizes UJ-2.

**Functional Requirements:**

#### FR-25: Fishing cast-and-reel loop

The Fishing Mode FSM shall: detect idle fishing state → cast rod → wait for bite event → detect tension event (visual indicator change) → execute reel input → return to idle. The loop repeats for the full Session duration.

**Consequences:**
- The bot sustains a 1-hour uninterrupted fishing session with no human input as the Phase 1 gate.
- Missed bite events (no tension detected within the configurable timeout) return the FSM to idle without error.
- Tension detection uses YOLO-based visual detection, not pixel-color matching.

---

## 5. Non-Goals (Explicit)

- **No memory reading or packet inspection.** Zero interaction with L2 client internals, memory space, or network traffic — ever.
- **No cloud services.** All inference, training, storage, and telemetry runs on Ion's local machine.
- **No 3-window support in V1.** Spoiler/Sweep requires a 3rd window; explicitly Phase 3.
- **No offline dancer (BD/SWS) coordination.** Asterios x55 does not support offline dancer/singer mode — BD/SWS integration is not planned for any phase.
- **No PvP response or survival behavior.** The bot does not detect or react to hostile players.
- **No raid boss participation.**
- **No zone selection strategy.** Starting zone is operator-defined per Session.
- **No cross-machine or distributed operation.**
- **No model sharing or external distribution.** This is a personal tool; no packaging for other users.

---

## 6. MVP Scope

### 6.1 In Scope (V1)

- 2-window party management: WL Agent + PP Agent
- Fishing Mode behavior profile (Phase 1 gate)
- Combat Mode behavior profile: WL pull → AoE → loot; PP buff cycle + heal
- In-app Recording Mode
- YouTube frame ingestion pipeline
- Auto-prelabeling + Label Studio integration
- YOLO Common Model + Class Model fine-tuning + versioning
- Human Simulation Layer (Bézier, timing noise, fatigue, micro-drift, error injection)
- Shadow Mode (good to have — recommend before first live Combat Mode session)
- Character identification on startup
- Death detection and recovery (full party, ≤60 seconds)
- Inventory-full detection and town return
- Session cap + clean shutdown
- Party Orchestrator (ZeroMQ Party Bus)
- YAML agent profile configuration
- Local MLflow experiment tracking
- SQLite session telemetry and action logs

### 6.2 Out of Scope for V1

- 3rd window (Spoiler): Phase 3 — deferred until 2-window bot is stable
- Offline dancer coordination (BD/SWS): not planned — Asterios x55 does not support this mode
- PvP response, zone selection, raid participation: indefinitely deferred
- Cross-server support: not planned

---

## 7. Success Metrics

**Primary**

- **SM-1**: Bot sustains a WL+PP farming session for ≥4 hours without human intervention. Validates FR-5, FR-6, FR-15, FR-16, FR-17, FR-18.
- **SM-9**: Shadow Mode session log shows action timing distributions within 1 standard deviation of Ion's recorded play. Validates FR-24 (pre-live validation gate).
- **SM-2**: Full party recovery from death completes within 60 seconds. Validates FR-16.
- **SM-3**: Zero bans in a continuous 30-day operation period. Validates FR-8, FR-9, FR-10, FR-11, FR-12 (Human Simulation Layer).

**Secondary**

- **SM-4**: Character identification succeeds on first attempt ≥95% of the time. Validates FR-15.
- **SM-5**: A new behavior model is trainable to functional quality within 2 hours of labeled recording. Validates FR-21.
- **SM-6**: YouTube frame ingestion processes a 10-minute video in ≤5 minutes. Validates FR-22.
- **SM-7**: Perception Pipeline inference latency ≤100 ms per frame per window. Validates FR-3.
- **SM-8**: Phase 1 gate: Fishing Mode sustains a 1-hour uninterrupted session with no human input. Validates FR-25.

**Counter-metrics (do not optimize)**

- **SM-C1**: Bot action timing variance must not be reduced to zero in pursuit of consistency — zero variance is more detectable than human-like noise. Counterbalances SM-1.
- **SM-C2**: Session length must not be extended beyond the configured cap in pursuit of SM-1 — longer sessions increase GM observation risk. Counterbalances SM-1.

---

## 8. Open Questions

All design questions resolved. No open items.

---

## 9. Decisions Record

All assumptions resolved and locked:

| # | Topic | Decision |
|---|-------|----------|
| 1 | Behavior policy | Combined FSM + BC Policy (FSM for state transitions, BC Policy for within-state action selection) |
| 2 | YOLO model strategy | Two model families: Common Model (class-agnostic) + Class Model (class-specific), both running per frame |
| 3 | PP buff cycle | Timer-driven; all timed casts gated by Safety Check (aggro-risk radius + WL state) |
| 4 | Annotation tool | Label Studio (Python API integration) |
| 5 | EasyOCR | Default pre-trained weights; no fine-tuning required |
| 6 | Offline dancer (BD/SWS) | Not applicable — Asterios x55 does not support offline dancer mode |
| 7 | Session persistence | Session-fresh; no cross-session zone memory |
| 8 | Shadow Mode | Good to have — included in V1 scope as FR-24 |
