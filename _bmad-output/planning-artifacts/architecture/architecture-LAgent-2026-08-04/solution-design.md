# LAgent — Solution Design

**Project:** LAgent — Autonomous L2 Asterios x55 AI Bot  
**Date:** 2026-08-04  
**Author:** Winston (System Architect, BMad)  
**Audience:** Ion (sole developer and operator)  
**Companion:** [ARCHITECTURE-SPINE.md](./ARCHITECTURE-SPINE.md)

---

## 1. System Overview

LAgent is a fully local, screen-vision-only autonomous bot for Lineage 2 on the Asterios x55 private server. It manages a 2-character party (Warlord + Prophet) by reading the screen and simulating human mouse and keyboard input — with zero client modification, memory reading, or packet injection.

The system has two operational modes:

| Mode | What runs | Purpose |
|---|---|---|
| **Live Session** | 5 OS processes | Autonomous farming / fishing |
| **Training Pipeline** | CLI tool (offline) | Produce new vision + behavior models |

These modes are **mutually exclusive** — training requires 4–6 GB VRAM and must not run during a live session.

---

## 2. C4 Diagrams

### 2.1 Level 1 — System Context

Who and what interacts with LAgent.

```mermaid
C4Context
    title LAgent — System Context

    Person(ion, "Ion", "Sole operator and developer. Starts sessions, records gameplay, trains models.")

    System(lagent, "LAgent", "Autonomous bot: perceives game via screen capture, acts via simulated input. Trains new behaviors from operator recordings.")

    System_Ext(l2client, "Lineage 2 Client (×2)", "Asterios x55 game client. Two windows: Warlord and Prophet.")
    System_Ext(labelstudio, "Label Studio (local)", "Annotation UI for correcting auto-prelabeled training frames.")
    System_Ext(mlflow, "MLflow (local)", "Experiment tracking for training runs. Not on runtime critical path.")
    System_Ext(youtube, "YouTube", "Supplementary training footage. Accessed via yt-dlp during training only.")

    Rel(ion, lagent, "Operates: starts/stops sessions, activates recording mode, triggers training pipeline")
    Rel(lagent, l2client, "Reads via screen capture (dxcam). Writes via simulated mouse + keyboard (win32api / pynput).")
    Rel(lagent, labelstudio, "Exports prelabeled annotation files; imports corrected labels")
    Rel(lagent, mlflow, "Logs training runs, model versions, metrics")
    Rel(lagent, youtube, "Downloads footage via yt-dlp during training ingestion")
```

---

### 2.2 Level 2 — Container Diagram

The 5 runtime OS processes and the offline Training Pipeline.

```mermaid
C4Container
    title LAgent — Container Diagram (Runtime + Training)

    Person(ion, "Ion")

    Container(ui, "Tray / UI", "Python: pystray + PyQt6", "System tray app. Launches/terminates all runtime processes. Displays status overlay: FSM state, HP/MP, session timer per agent.")
    Container(orc, "Party Orchestrator", "Python: pyzmq", "Monitors agent heartbeats. Triggers session halt if either agent misses N consecutive heartbeats. Relays no gameplay data — pure health monitor.")
    Container(gpu, "GPU Inference Server", "Python: Ultralytics YOLOv8-nano + EasyOCR + PyTorch", "Single process owning all GPU calls. Accepts frame + ROI map from each agent. Returns PerceptionResult (detections + OCR values). ZeroMQ DEALER/ROUTER.")
    Container(wl, "WL Agent", "Python: FSM + BC Policy + HSL", "Warlord control loop. Capture thread → inference request → policy → HSL → OS input. Publishes PartyState over ZeroMQ PUB.")
    Container(pp, "PP Agent", "Python: FSM + BC Policy + HSL", "Prophet control loop. Manages buff timers + Safety Check. Subscribes to WL PartyState. Publishes own PartyState.")

    ContainerDb(db, "sessions.db", "SQLite (WAL mode)", "Session records + timestamped events from all processes. Multi-writer safe.")
    ContainerDb(models, "models/", "Filesystem", "current.pt files per class. Replaced atomically by Training Pipeline.")
    ContainerDb(profiles, "profiles/", "YAML files", "Per-class agent profiles: ROIs, FSM bindings, skill keys, buff timers.")

    Container(train, "Training Pipeline CLI", "Python: PyTorch Lightning + MLflow + yt-dlp", "Offline only. Subcommands: prelabel, train, ingest. Never runs during a live session.")

    Rel(ion, ui, "Controls via tray menu + hotkeys")
    Rel(ui, wl, "Spawns / terminates (subprocess)")
    Rel(ui, pp, "Spawns / terminates (subprocess)")
    Rel(ui, gpu, "Spawns / terminates (subprocess)")
    Rel(ui, orc, "Spawns / terminates (subprocess)")
    Rel(ui, db, "Reads session telemetry for status display")

    Rel(wl, gpu, "ZeroMQ DEALER: {agent_id, frame_bytes, roi_map}", "async")
    Rel(pp, gpu, "ZeroMQ DEALER: {agent_id, frame_bytes, roi_map}", "async")
    Rel(gpu, wl, "ZeroMQ: PerceptionResult")
    Rel(gpu, pp, "ZeroMQ: PerceptionResult")
    Rel(gpu, models, "Loads current.pt at startup")

    Rel(wl, pp, "ZeroMQ PUB: PartyState")
    Rel(pp, wl, "ZeroMQ PUB: PartyState")
    Rel(wl, orc, "ZeroMQ PUB: heartbeat (piggybacked on PartyState PUB)")
    Rel(pp, orc, "ZeroMQ PUB: heartbeat")

    Rel(wl, db, "Writes: session events, FSM transitions, action log")
    Rel(pp, db, "Writes: session events, FSM transitions, action log")
    Rel(orc, db, "Writes: heartbeat events, session halt events")

    Rel(wl, profiles, "Loads warlord.yaml at startup")
    Rel(pp, profiles, "Loads prophet.yaml at startup")

    Rel(ion, train, "Invokes CLI: python -m lagent.train prelabel|train|ingest")
    Rel(train, models, "Writes current.pt atomically (temp + os.replace)")
    Rel(train, db, "Reads recording metadata")
```

---

### 2.3 Level 3 — Agent Component Diagram

The internal structure of a single Agent process (WL or PP — identical base, different FSM/policy).

```mermaid
C4Component
    title Agent Process — Internal Components

    Container_Boundary(agent, "Agent Process (WL or PP)") {
        Component(capture, "Capture Thread", "dxcam / mss", "Grabs game window frame at ~10 FPS. Pushes to FrameQueue. In Recording Mode: also writes frame to disk + logs input via pynput listener.")
        Component(frameq, "FrameQueue", "threading.Queue (maxsize=2)", "Oldest-frame eviction. Never blocks capture thread.")
        Component(infclient, "Inference Client", "pyzmq DEALER", "Pops frame from FrameQueue. Sends {agent_id, frame_bytes, roi_map} to GPU server. Receives PerceptionResult. Pushes to PolicyQueue.")
        Component(policyq, "PolicyQueue", "threading.Queue (maxsize=2)", "Oldest-frame eviction. Decouples inference from policy tick.")
        Component(fsm, "FSM + BC Policy", "Pure Python + loaded .pt", "Pops PerceptionResult + PartyState. Runs FSM transition logic. Calls BC Policy module for within-state action selection. Produces Action.")
        Component(partybus, "Party Bus Client", "pyzmq PUB + SUB", "PUBs own PartyState each policy tick. SUBs to peer agent's PartyState. Heartbeat piggybacked on PUB message.")
        Component(hsl, "HSL Instance", "lagent.hsl", "Shapes every Action: Bézier path, timing noise, fatigue multiplier, micro-drift, error injection. In Shadow Mode: logs shaped action, suppresses OS call.")
        Component(inputapi, "Input API", "pynput + win32api", "Executes shaped mouse moves and key events via Windows low-level API.")
    }

    Rel(capture, frameq, "push frame")
    Rel(frameq, infclient, "pop frame (drop-oldest if full)")
    Rel(infclient, fsm, "push PerceptionResult via PolicyQueue")
    Rel(partybus, fsm, "inject peer PartyState each tick")
    Rel(fsm, hsl, "Action")
    Rel(hsl, inputapi, "shaped Action (or suppressed in Shadow Mode)")
```

---

### 2.4 Level 3 — GPU Inference Server Component Diagram

```mermaid
C4Component
    title GPU Inference Server — Internal Components

    Container_Boundary(gpuserver, "GPU Inference Server") {
        Component(router, "ZeroMQ ROUTER", "pyzmq", "Receives inference requests from Agent DEALER sockets. Correlation by agent_id. Non-blocking async dispatch.")
        Component(batcher, "Frame Batcher", "Python", "Collects frames from both agents per tick window. Dispatches to YOLO inference. Can run sequentially or batched depending on throughput profile.")
        Component(yolo, "YOLO Inference", "Ultralytics YOLOv8-nano + CUDA", "Runs Common Model + Class Model per frame. Returns Detection list with bounding boxes + class + confidence.")
        Component(ocr, "OCR Inference", "EasyOCR + CUDA", "Runs on ROI crops (HP bar, MP bar, buff timers). Returns ocr_values dict.")
        Component(merger, "Result Merger", "Python", "Combines YOLO detections + OCR values into PerceptionResult. Routes back to originating agent via ROUTER.")
    }

    Rel(router, batcher, "frames")
    Rel(batcher, yolo, "frame batches")
    Rel(batcher, ocr, "ROI crops")
    Rel(yolo, merger, "Detection list")
    Rel(ocr, merger, "ocr_values")
    Rel(merger, router, "PerceptionResult → agent")
```

---

## 3. Key Data Flows

### 3.1 Normal Per-Tick Perception-Decision-Action Loop

```mermaid
sequenceDiagram
    participant CAP as Capture Thread
    participant FQ as FrameQueue
    participant IC as Inference Client
    participant GPU as GPU Inference Server
    participant FSM as FSM + BC Policy
    participant BUS as Party Bus
    participant HSL as HSL Instance
    participant OS as OS Input API

    CAP->>FQ: push frame (drop oldest if full)
    IC->>FQ: pop frame
    IC->>GPU: DEALER send {agent_id, frame, roi_map}
    GPU-->>IC: PerceptionResult {detections, ocr_values}
    IC->>FSM: push PerceptionResult
    BUS-->>FSM: latest peer PartyState
    FSM->>FSM: evaluate FSM transition
    FSM->>FSM: BC Policy → Action
    FSM->>BUS: publish own PartyState + heartbeat
    FSM->>HSL: Action
    HSL->>HSL: shape (Bézier + timing + fatigue)
    HSL->>OS: shaped mouse/key event
```

---

### 3.2 PP Buff Safety Check Flow

```mermaid
sequenceDiagram
    participant PP as PP FSM
    participant BUS as Party Bus (SUB)
    participant HSL as HSL Instance

    PP->>PP: buff timer expires
    PP->>BUS: read latest WL PartyState
    alt Safety Check passes\n(no mobs in aggro radius AND WL not PULLING)
        PP->>HSL: cast buff Action
        HSL->>HSL: shape + execute
    else Safety Check fails
        PP->>PP: defer by retry_interval; re-evaluate next tick
    end
    note over PP: cast is never skipped — only deferred
```

---

### 3.3 Death Recovery Flow

```mermaid
sequenceDiagram
    participant WL as WL Agent FSM
    participant PP as PP Agent FSM
    participant BUS as Party Bus

    WL->>WL: detect DEAD state (PerceptionResult)
    WL->>BUS: publish PartyState{fsm=DEAD}
    PP->>BUS: read WL PartyState{fsm=DEAD}
    WL->>WL: execute respawn sequence
    PP->>PP: hold combat; await WL BUFFING state
    WL->>WL: navigate to buff position
    WL->>BUS: publish PartyState{fsm=BUFFING}
    PP->>PP: Safety Check → execute full buff cycle on WL
    PP->>BUS: publish PartyState{fsm=IDLE}
    WL->>WL: transition IDLE → PULLING
    note over WL,PP: full recovery target ≤60s (FR-16)
```

---

### 3.4 Training Pipeline Flow (Offline)

```mermaid
flowchart LR
    REC["Recording Mode\n(Agent process, --record flag)\nCaptures frames + Ion's inputs"]
    ARCH["recordings/\nFrame archive + input log"]
    PRE["lagent.train prelabel\nYOLO auto-annotation → Label Studio format"]
    LS["Label Studio (local)\nManual label correction"]
    TR["lagent.train train\nFine-tune YOLO + update timing params\nPyTorch Lightning + MLflow"]
    MDL["models/{class}/current.pt\nAtomic replace via os.replace()"]
    GPU["GPU Inference Server\nLoads new current.pt on next startup"]

    REC --> ARCH
    ARCH --> PRE
    PRE --> LS
    LS --> TR
    TR --> MDL
    MDL --> GPU

    YT["YouTube URL\nlagent.train ingest\nyt-dlp + OpenCV frame extraction"]
    YT --> LS
```

---

## 4. Process Topology & Port Map

All ZeroMQ binds are localhost-only. Suggested port assignments:

| Process | Socket type | Port | Direction |
|---|---|---|---|
| GPU Inference Server | ROUTER (bind) | 5555 | receives from both agents |
| WL Agent | DEALER (connect) | 5555 | sends frames to GPU server |
| PP Agent | DEALER (connect) | 5555 | sends frames to GPU server |
| WL Agent | PUB (bind) | 5556 | publishes PartyState + heartbeat |
| PP Agent | PUB (bind) | 5557 | publishes PartyState + heartbeat |
| PP Agent | SUB (connect) | 5556 | subscribes to WL PartyState |
| WL Agent | SUB (connect) | 5557 | subscribes to PP PartyState |
| Orchestrator | SUB (connect) | 5556, 5557 | monitors both PUB streams |

All ports are configurable in `profiles/` or a top-level `config.yaml`.

---

## 5. Deployment View

Single Windows machine. No network egress during runtime.

```mermaid
graph TD
    subgraph Machine["Ion's Machine — Windows, GTX 1070 Ti (8GB VRAM)"]
        subgraph Proc["Runtime Processes (live Session)"]
            UI[lagent.ui\nTray + status overlay]
            ORC[lagent.orchestrator]
            GPU[lagent.gpu_server\n~2.5-3.5 GB VRAM]
            WL[lagent.agent --class warlord]
            PP[lagent.agent --class prophet]
        end
        subgraph WinOS["Windows"]
            L2A[L2 Client Window: WL]
            L2B[L2 Client Window: PP]
        end
        subgraph Storage["Local Storage"]
            DB[(sessions.db)]
            MDLS[(models/ — .pt files)]
            PROF[(profiles/ — .yaml)]
        end
        subgraph Train["Training (offline, not concurrent)"]
            CLI[lagent.train CLI\n4-6 GB VRAM during training]
            LS[Label Studio local server]
            ML[MLflow local server]
        end
    end

    WL -- dxcam capture --> L2A
    PP -- dxcam capture --> L2B
    WL -- win32api input --> L2A
    PP -- win32api input --> L2B
    GPU --> MDLS
    WL --> DB
    PP --> DB
    ORC --> DB
    UI --> DB
    CLI --> MDLS
    CLI --> LS
    CLI --> ML
```

**VRAM budget (runtime, steady state):**

| Component | Estimated VRAM |
|---|---|
| 2× L2 game windows (DirectX) | ~1–2 GB (shared) |
| YOLOv8-nano ×2 models (Common + Class) | ~400–600 MB |
| EasyOCR | ~300–500 MB |
| PyTorch runtime overhead | ~300 MB |
| **Total** | **~2.5–3.5 GB** — comfortable on 8 GB |

Training is offline and uses a separate 4–6 GB budget.

---

## 6. Architectural Decision Summary

| AD | Decision | Key constraint it prevents |
|---|---|---|
| AD-1 | ZeroMQ-only cross-process comms | Shared mutable state; GIL contention |
| AD-2 | Dedicated GPU Inference Server | GPU starvation / CUDA stream contention between agents |
| AD-3 | Oldest-frame eviction queues | Cascading pipeline stall from slow inference tick |
| AD-4 | Per-agent exclusive GameState | Shared state contention; cross-agent mutation |
| AD-5 | Tray + overlay; UI is sole launcher | Heavyweight GUI in session process; rogue process spawning |
| AD-6 | Training as separate CLI | VRAM co-use; training deps in runtime |
| AD-7 | Convention-based atomic model swap | Runtime MLflow dependency; mid-session model replacement |
| AD-8 | HSL per-agent instance; non-bypassable | Shared fatigue state; HSL bypass creating detectable straight-line input |
| AD-9 | Single WAL-mode SQLite DB | Per-process DB files requiring post-session merge |
| AD-10 | OCR in GPU server | Split perception responsibility; CPU OCR latency in agent cycle |
| AD-11 | Fixed ZeroMQ socket patterns per channel | Blocking REQ/REP on inference path; ambiguous routing |
| AD-12 | `lagent.common` only shared import | Circular imports; training deps loading into runtime |
| AD-13 | Recording Mode inside Agent; launch-time exclusive | Separate recorder process IPC complexity; record+session co-run |

---

## 7. Open Questions & Deferred Decisions

| Item | Deferred to |
|---|---|
| Per-class FSM state enumeration and transition conditions | Epic-level spines |
| BC Policy model architecture (LSTM / MLP / transformer) | Epic-level spines |
| GPU Inference Server batching strategy (batched vs. sequential YOLO calls) | Implementation |
| ZeroMQ message schema versioning strategy (post-V1) | Post-V1 |
| Phase 3+ topology (3rd Agent window for Spoiler) | Phase 3 |
| Keystroke timing parameter bootstrap defaults | HSL implementation |
| Operational monitoring beyond session log | Not in V1 |
