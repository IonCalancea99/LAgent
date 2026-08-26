# Stories Index

This folder is the single place for story artifacts used during implementation planning.

## Epic 2 - Perception Pipeline

- 2.1 Screen Capture Thread - dxcam Primary, mss Fallback
- 2.2 ROI Extraction from Agent Profile
- 2.3 GPU Inference Server - YOLO Detection (Common + Class Models)
- 2.4 EasyOCR Integration - HP/MP/Buff Numeric Values
- 2.5 Inference Client, PolicyQueue and Debug Perception Display

## Epic 3 - Human Simulation Layer and Shadow Mode

- 3.1 Bezier Mouse Path Generator
- 3.2 Keystroke Timing Noise
- 3.3 Fatigue Model
- 3.4 Micro-drift and Error Injection
- 3.5 Shadow Mode - Full HSL Shaping Without OS Output

## Epic 4 - Fishing Mode

- 4.1 Agent Base Loop — Capture-to-Policy Single-Window Pipeline
- 4.2 Character Identification on Startup
- 4.3 Fishing FSM — Cast and Wait States
- 4.4 Fishing FSM — Tension Detection and Reel

## Epic 5 - Party Orchestration

- 5.1 Party Bus — PartyState PUB/SUB Exchange
- 5.2 PP Buff Safety Check
- 5.3 Orchestrator Heartbeat Monitor & Session Halt

## Epic 6 - Combat Mode & Session Lifecycle

- 6.1 Warlord Combat FSM — Pull, Fight, Loot
- 6.2 Prophet Buff Cycle FSM — Timer-Driven Buffing
- 6.3 Death Detection & Full Party Recovery
- 6.4 Inventory-Full Detection & Town Return
- 6.5 Session Cap & Clean Shutdown

## Epic 7 - Training Pipeline

- 7.1 Recording Mode — Dual-Write Frame Capture & Input Log
- 7.2 Auto-Prelabeling Pipeline
- 7.3 Model Training & Atomic Deployment
- 7.4 YouTube Frame Ingestion

## Epic 8 - Tray UI & Status Overlay

- 8.1 System Tray Icon & Session Control Menu
- 8.2 Status Overlay Window
- 8.3 Session State Wiring & Tray Feedback

## Naming Convention

Story files are named `<epic>-<story>-<slug>.md`, for example `3-1-bezier-mouse-path-generator.md`.