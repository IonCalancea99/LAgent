---
title: "LAgent — Technical Addendum"
status: draft
created: 2026-08-04
updated: 2026-08-04
---

# LAgent — Technical Addendum

Supplementary technical context captured during the product brief conversation. Intended for the Architecture phase.

---

## Party Roster (Full — Not All Active Simultaneously)

| Class | Role | V1 Active? | Reason |
|-------|------|-----------|--------|
| Warlord (WL) | AoE main DD + puller | ✅ Window 1 | Primary farmer |
| Prophet (PP) | Main buffer + healer | ✅ Window 2 | Required for WL survival |
| Spoiler | Resource farmer (Sweep) | ❌ Phase 3 | Needs 3rd window (premium) |
| Blade Dancer (BD) | Dance buffer | ❌ Phase 4 | Offline dancer or premium window |
| Sword Singer (SWS) | Song buffer | ❌ Phase 4 | Offline dancer or premium window |

**Open question**: Does Asterios x55 support offline dancer/singer mode? If yes, BD+SWS can be parked at grind spot before bot session starts, providing dances/songs passively without consuming an active window slot.

---

## Hardware Profile & Constraints

- **CPU**: Intel i7 (generation unspecified)
- **GPU**: GTX 1070 Ti — 8GB VRAM
- **RAM**: Unspecified (assume ≥16GB for 2 game windows + Python runtime)
- **OS**: Windows (required for L2 client + dxcam + pynput)

**VRAM Budget (2-window scenario)**:
| Component | Estimated VRAM |
|-----------|---------------|
| 2× L2 game windows | ~1–2 GB (shared via DirectX) |
| YOLOv8-nano inference (2 streams) | ~400–600 MB |
| EasyOCR model | ~300–500 MB |
| PyTorch runtime overhead | ~300 MB |
| **Total** | **~2.5–3.5 GB** |

Comfortable headroom on 8GB. Training must still be offline (fine-tuning YOLO uses 4–6GB+).

**Capture rate strategy**: 10 FPS per window is sufficient for L2's pace (skills have cast times ≥0.5s). Actual perception→action latency target: <200ms end-to-end.

---

## Recommended Tech Stack (Rationale)

| Component | Choice | Why |
|-----------|--------|-----|
| Screen capture | **dxcam** (primary), **mss** (fallback) | dxcam uses DirectX for <10ms latency on Windows; mss is cross-platform fallback |
| Object detection | **Ultralytics YOLOv8-nano** | Best inference speed/accuracy tradeoff on 1070 Ti; fine-tuning on custom data is well-documented |
| OCR | **EasyOCR** | Better accuracy on stylized/fantasy fonts than Tesseract; GPU-accelerated |
| Input simulation | **pynput + win32api** | Low-level Windows API calls; harder to fingerprint than PyAutoGUI's SendInput |
| Bézier mouse | **Custom implementation** | Generate cubic Bézier paths between current and target position with randomized control points and speed profiles |
| Inter-process comms | **ZeroMQ (zmq)** | Sub-millisecond latency for WL↔PP coordination; no shared memory risk |
| Behavior policy | **Imitation learning (BC)** from recordings | Sufficient for deterministic L2 combat loops; RL optional in Phase 2+ |
| Training framework | **PyTorch + PyTorch Lightning** | Standard; Lightning reduces boilerplate for training loop management |
| Experiment tracking | **MLflow (local server)** | No cloud; tracks model versions, metrics, hyperparams across training runs |
| Data storage | **SQLite** | Zero-ops; stores session telemetry, action logs, buff state history |
| Config | **YAML + Pydantic v2** | Type-safe agent profiles; one YAML file per class defines ROI positions, skill keys, buff timers |
| YouTube ingestion | **yt-dlp + OpenCV frame extraction** | yt-dlp downloads video; OpenCV extracts frames at configurable FPS; frames fed into label pipeline |

---

## Anti-Detection Design Requirements

These must be implemented before any live testing, not added later:

1. **Mouse movement**: All cursor paths use cubic Bézier curves with randomized control point offsets (±15–30px). Speed profile follows a bell curve (slow start, fast mid, slow end) with ±10% random variance per path.
2. **Keystroke timing**: Inter-key delays drawn from a Gaussian distribution matching recorded human play timing per skill (mean and std captured during training recording phase).
3. **Fatigue simulation**: Action latency increases by a small multiplier every 30–60 minutes of session time (simulating human tiredness). Reset after simulated "break" (bot pauses for 5–15 minutes, no input).
4. **Micro-drift**: Random small camera rotations, occasional cursor resting on non-target locations between actions.
5. **Session length caps**: Sessions capped at 4–6 hours maximum before forced pause, to match human play patterns.
6. **Error injection**: 1–3% probability of "misclick recovery" — bot targets wrong mob, immediately corrects.

---

## Training Pipeline Architecture

```
[Recording Mode]                    [Training]                    [Deployment]
  User plays manually    →    Auto-label (YOLO prelabel)    →    Export model
  App captures frames         + Manual label correction          to inference
  + input log                 (Label Studio or CVAT)            engine
  
[YouTube Ingestion]
  User provides URL      →    yt-dlp download    →    Frame extraction    →    Label pipeline
```

**Label Studio** or **CVAT** (both locally deployable) recommended for annotation UI. Label Studio has better Python API integration.

**Phase 1 (Fishing) training data needs**:
- Fishing rod cast animation start/end frames
- Fish "tension" event (visual indicator on screen — typically a bar or icon change)
- Successful reel vs. failed reel
- Fishing menu UI elements

YouTube footage from Asterios fishing guides can supplement operator recordings for this phase.

---

## Character Identification Strategy (Startup Scan)

When the bot starts, it must identify which window contains which class. Fingerprinting strategy (in priority order):

1. **Skill bar layout**: Each class has a unique set of skills visible in the active skill bar. YOLO detection of skill icons is the most reliable signal.
2. **Character name color**: In L2, name color sometimes encodes class or level tier — server-specific.
3. **Stat panel OCR**: If skill bar is ambiguous, open Character panel, OCR class name text.
4. **Inventory items**: Class-specific equipment (polearm for WL, robe for PP) as fallback.

Identification runs once at startup and stores window→role mapping for the session duration.

---

## Phase Roadmap (Technical)

| Phase | Milestone | Windows | New Capability |
|-------|-----------|---------|----------------|
| 1 | Fishing POC | 1 (WL) | Full pipeline validation: capture → detect → decide → act |
| 2 | WL+PP combat V1 | 2 | Party coordination, buff cycle, combat loop, death recovery |
| 3 | Spoiler integration | 3 (premium) | Sweep after kills, inventory management, town recall |
| 4 | BD/SWS coordination | 2+offline or 3 | Offline dancer support or 3rd window rotation |

---

## Options Considered & Rejected

| Option | Reason Rejected |
|--------|----------------|
| Memory reading (L2Walker approach) | High ban risk; incompatible with Asterios anticheat |
| Packet sniffing | Same risk profile as memory reading; requires client-level access |
| Reinforcement learning from scratch | Impractical without a simulator; live RL on the real server is too slow and risky |
| Cloud inference | Latency unacceptable; external dependency violates local-first requirement |
| PyAutoGUI for input | Uses SendInput which is fingerprint-detectable; pynput + win32api lower-level |
| OpenAI Gym L2 wrapper | No existing implementation for Asterios; would require client modification |
