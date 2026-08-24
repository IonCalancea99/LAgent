---
title: "LAgent — Autonomous L2 Asterios x55 AI Bot"
status: draft
created: 2026-08-04
updated: 2026-08-04
---

# Product Brief: LAgent

## Executive Summary

LAgent is a fully local AI system that autonomously plays Lineage 2 on the Asterios x55 private server, managing a 2-character party (Warlord + Prophet) without human intervention after the initial login. It perceives the game exclusively through screen capture and acts exclusively through simulated mouse and keyboard input — no memory reading, no packet injection — making its footprint indistinguishable from human play at the OS and network level.

The system ships with a full training pipeline: the operator records their own gameplay directly in the app, supplements with processed YouTube footage, and produces class-specific vision and behavior models on local hardware. Anti-detection is a first-class design requirement: every action is shaped by randomized timing distributions, Bézier mouse curves, and fatigue simulation to resist both automated and human GM scrutiny.

The immediate target is the Asterios x55 server, with Fishing automation as the Phase 1 proof-of-concept and WL+PP combat farming as the V1 milestone.

---

## The Problem

Playing Lineage 2 efficiently demands sustained, repetitive precision across sessions lasting many hours: maintaining buff cycles on multiple characters, pulling and AoE-clearing mob packs, looting, managing inventory, recovering from deaths, and reacting to events — all simultaneously across two windows. Manual play at this cadence is unsustainable for a solo operator.

Existing automation approaches fail in one of three ways:
- **Client-modification bots** (L2Walker, Adrenaline-era tools) read memory or inject packets — high ban risk and incompatible with current Asterios anticheat.
- **Cloud-dependent bots** introduce latency, external services, and privacy exposure.
- **Generic automation scripts** (AutoHotkey, pixel bots) are brittle to any UI change and entirely lack adaptive behavior.

No solution combines local-first infrastructure, vision-only interaction, server-specific training, and human-behavior simulation in a single coherent system.

---

## The Solution

LAgent is built around a closed perception–decision–action loop running independently per character window, coordinated by a party orchestrator:

1. **Capture** — Each game window is screen-captured at ~10 FPS using a low-latency capture library. Regions of interest (HP/MP bars, buff icons, chat, minimap, mob area) are extracted per frame.
2. **Perceive** — A YOLOv8-nano model (trained on Asterios x55 screenshots) detects mobs, loot, UI elements, and character states. EasyOCR handles numeric values (HP, MP, counts).
3. **Decide** — A behavior policy (trained via imitation learning on operator-recorded gameplay) selects the next action for each character, informed by party state from the orchestrator.
4. **Act** — Actions are executed as human-like simulated input: Bézier mouse curves, randomized inter-keystroke delays drawn from statistical distributions, micro-pauses and drift.
5. **Coordinate** — A lightweight party bus (ZeroMQ) synchronizes PP's buff decisions with WL's combat state — PP knows when WL is pulling, WL knows when PP is casting.

The training pipeline runs offline: record a session → auto-label frames → fine-tune models → deploy. YouTube video URLs can be provided for supplementary training data (e.g., fishing mechanics from community footage).

---

## What Makes This Different

| Axis | LAgent | Existing Alternatives |
|------|--------|-----------------------|
| Detection surface | Vision-only, simulated input | Memory read / packet inject |
| Infrastructure | Fully local, zero cloud | Cloud-dependent or server-side |
| Training data | Operator's own recordings + YouTube | Hardcoded scripts / fixed pixel coords |
| Server specificity | Trained on Asterios x55 actual UI | Generic L2 client assumptions |
| Anti-detection | First-class: Bézier, noise, fatigue | Afterthought or absent |
| Adaptability | Retrainable when game patches UI | Breaks on any UI change |

The moat is execution quality and local sovereignty — not a technical patent. The system is as hard to detect as it is to detect a human, because it only does what a human does: look at the screen and move the mouse.

---

## Who This Serves

**Primary user: Ion (solo operator)**
A single L2 player running a 2-character party on Asterios x55. Wants extended autonomous farming sessions without supervision, zero ban risk tolerance, and full control over training data and local infrastructure. Not interested in sharing the system or monetizing it — this is a personal productivity tool for a specific server.

---

## Success Criteria

**Operational**
- Bot sustains a WL+PP farming session for 4+ hours without human intervention
- Full party recovery from death within 60 seconds (respawn, rebuff, resume)
- Inventory-full detection triggers safe return to town automatically
- Character identification from window scan succeeds on first attempt ≥95% of the time

**Anti-Detection**
- Zero bans in a continuous 30-day operation period
- Mouse movement paths pass visual inspection as human-like
- Action timing distributions match recorded human play within 1 standard deviation

**Training Pipeline**
- A new behavior model (e.g., fishing) is trainable to functional quality within 2 hours of labeled recording
- YouTube frame ingestion pipeline processes a 10-minute video in under 5 minutes on local hardware
- Model inference latency ≤100ms per frame on GTX 1070 Ti at 10 FPS capture rate

**Phase 1 Gate (Fishing)**
- Bot autonomously casts, waits, detects fish tension events, and reels in — for a 1-hour session with no human input

---

## Scope

### V1 — In (2-window WL+PP, Free Tier)

| Feature | Notes |
|---------|-------|
| 2-window party management | WL + PP only |
| In-app screen recording mode | Operator plays, app captures frames + inputs for labeling |
| YouTube frame ingestion | yt-dlp download → frame extraction → label pipeline |
| YOLOv8-nano mob/UI detection | Trained on Asterios x55 screenshots |
| PP buff cycle automation | Tracks buff timers, auto-rebuffs, heals WL |
| WL combat loop | Pull → AoE → loot cycle |
| Human-like input simulation | Bézier curves, timing noise, fatigue model |
| Character identification on startup | Scan window → assign role → begin loop |
| Death recovery | Detect death → respawn → rebuff → resume |
| Basic inventory management | Detect full inventory → town return |
| **Fishing automation (Phase 1 POC)** | Cast → wait → tension detection → reel; validates full pipeline |
| Local MLflow experiment tracking | Training runs logged locally |
| YAML-based agent profile config | Per-class behavior parameters |

### V1 — Out (Explicitly Deferred)

- 3-window premium support (deferred until free-tier bot is stable)
- Spoiler / sweep (requires 3rd window)
- BD / SWS offline dancer coordination
- PvP response or survival behavior
- Raid boss participation
- Zone selection strategy (starting zone is operator-defined)
- Multi-machine or distributed operation

---

## Key Risks & Open Questions

| Risk | Severity | Mitigation |
|------|----------|------------|
| GTX 1070 Ti sustains 2 game windows + inference at 10 FPS | Medium | Benchmark early; YOLOv8-nano chosen for this hardware profile |
| Asterios x55 patches UI between training and deployment | Medium | Retrain pipeline must be fast (target: <2hr); modular ROI config |
| GM human-observation detection | High | Fatigue model, session length caps, behavioral noise — must be validated empirically |
| EasyOCR accuracy on L2's custom fonts | Low-Medium | Fine-tune on server-specific font samples; fallback to template matching |
| PP/WL window identification ambiguity | Low | Fingerprint on skill bar layout, not portrait alone |

---

## Technical Constraints (Summary)

- **Hardware**: i7 CPU, GTX 1070 Ti (8GB VRAM) — inference must run at ≤8GB VRAM; training is offline-only
- **OS**: Windows (L2 client runs on Windows; dxcam/pynput are Windows-native)
- **Stack**: Python 3.11+, PyTorch, Ultralytics YOLOv8, EasyOCR, dxcam/mss, pynput, ZeroMQ, MLflow, SQLite
- **No external services**: All inference, training, and storage runs on local machine
- **No client modification**: Zero interaction with L2 client internals, memory, or network packets

---

## Vision

LAgent becomes a modular, self-improving L2 automation platform. Phase 2 adds a 3rd window (Spoiler) for resource farming. Phase 3 integrates BD/SWS offline dancer coordination. Long-term: a configurable class-role framework that any L2 player can train against their own server's UI and characters — a local-first, detection-resistant alternative to the entire category of memory-reading bots. The training pipeline is the product's enduring value; the bot is its first customer.
