# Story 1.1: Project Scaffold & lagent.common Shared Types

Status: ready-for-dev

## Story

As Ion (sole developer),
I want the full `lagent/` package structure created with all Pydantic v2 shared types defined in `lagent.common`,
so that every downstream process has a single import source for `GameState`, `PartyState`, `PerceptionResult`, `Detection`, `Action`, and `AgentProfile`, and the AD-12 module graph rule is enforced from day one.

## Acceptance Criteria

1. **Shared type import and canonical contracts**
   - Given the repository is freshly cloned with `pyproject.toml` listing the runtime dependencies, when `python -c "from lagent.common import GameState, PartyState, PerceptionResult, Detection, Action, AgentProfile"` runs, all six symbols import without error.
   - Each symbol is a Pydantic v2 model and is defined in `lagent.common.types`.
   - `Detection` has `class_name: str`, `confidence: float`, and `bbox_xyxy: tuple[int, int, int, int]`; the bounding box uses captured-frame pixel coordinates with a top-left origin.
   - `PerceptionResult` has `detections: list[Detection]` and `ocr_values: dict[str, str]`.
   - `GameState` represents agent-owned state: HP%, MP%, active buffs, mob positions, loot presence, character position, and UI mode.
   - `PartyState` contains the cross-process subset: FSM state, HP%, MP%, position, buff presence, and heartbeat timestamp.
   - `Action` represents the HSL input contract and supports the action types mouse move, mouse click, key press, and wait, with the parameters needed by those actions.
   - `AgentProfile` provides the shared profile contract for ROI positions, FSM bindings, skill key bindings, buff timer durations, confidence thresholds, and mode flags. Profile loading/validation behavior is Story 1.2.
   - `lagent.common.__init__` is the only package initializer that exports these shared types. No agent, GPU server, orchestrator, UI, HSL, or training module re-exports or locally redefines them.

2. **Structural seed and runnable stubs**
   - The following directories exist: `lagent/common`, `lagent/hsl`, `lagent/agent/warlord`, `lagent/agent/prophet`, `lagent/gpu_server`, `lagent/orchestrator`, `lagent/ui`, `lagent/train`, `models/common`, `models/warlord`, `models/prophet`, `profiles`, `recordings`, and `data`.
   - The Python package initializers and module entry points follow the architecture structural seed. At minimum, `lagent/agent/__main__.py`, `lagent/gpu_server/__main__.py`, `lagent/orchestrator/__main__.py`, and `lagent/ui/__main__.py` exist.
   - Each of `python -m lagent.agent`, `python -m lagent.gpu_server`, `python -m lagent.orchestrator`, and `python -m lagent.ui` starts and exits immediately with code 0. These are stubs only; process launching, ZeroMQ wiring, and session logic belong to later stories.

3. **Dependency and project metadata baseline**
   - `pyproject.toml` targets Python 3.12 and declares the runtime baseline needed by the scaffold and downstream runtime modules: Pydantic v2, pyzmq 26.x, structlog 24.x, dxcam 0.0.5, mss 9.0.x, pynput 1.7.x, and pywin32 306, with SQLite supplied by the standard library.
   - GPU inference, training, and UI-specific dependencies may be declared only when required by the repository’s chosen packaging approach; their implementation remains outside this story.

## Tasks / Subtasks

- [ ] Create the Python project metadata and package scaffold (AC: 2, 3)
  - [ ] Add `pyproject.toml` for Python 3.12 and the runtime dependency baseline.
  - [ ] Create the structural seed directories and package initializers using the `lagent.<subsystem>` naming convention.
  - [ ] Add no runtime behavior beyond import-safe stubs; do not implement profile loading, database access, ZeroMQ channels, capture, inference, HSL, or UI behavior.
- [ ] Define canonical shared Pydantic v2 models in `lagent/common/types.py` (AC: 1)
  - [ ] Define `Detection` and `PerceptionResult` exactly once with the architecture’s field names and shapes.
  - [ ] Define `GameState`, `PartyState`, `Action`, and `AgentProfile` with stable, serializable fields for downstream stories.
  - [ ] Use Pydantic v2 APIs and type annotations compatible with Python 3.12.
  - [ ] Export the six public types only from `lagent/common/__init__.py`.
- [ ] Add process entry-point stubs (AC: 2)
  - [ ] Implement `__main__.py` for `agent`, `gpu_server`, `orchestrator`, and `ui` so each exits cleanly with status 0.
  - [ ] Keep process modules independent; no runtime process imports another process package.
- [ ] Add focused scaffold tests (AC: 1, 2)
  - [ ] Smoke-test the six imports and assert each is a Pydantic v2 model.
  - [ ] Validate representative construction/serialization for the canonical fields, especially `Detection.bbox_xyxy` and `PerceptionResult`.
  - [ ] Run each module entry point as a subprocess and assert return code 0.
  - [ ] Add an AD-12 guard that shared types are not re-exported from other subsystem `__init__.py` files.

## Dev Notes

### Developer Context

This is the first implementation story and a greenfield foundation. Optimize for stable public contracts and import topology, not feature behavior. Downstream stories depend on the exact shared symbols and field names. Keep the implementation local-only and import-safe on macOS during development; Windows-only runtime integrations are deferred to their owning stories.

### Technical Requirements

- Python 3.12 is the architecture target. Use Pydantic v2 models, not dataclasses or ad hoc dictionaries, for the six shared contracts.
- `GameState` is owned and replaced by an Agent each perception cycle; it is not shared mutable state.
- `PartyState` is the only state subset intended to cross process boundaries. Future IPC uses ZeroMQ and JSON, but this story must not implement transport.
- `Detection` coordinates are frame pixels, origin top-left. Do not introduce game-world coordinates.
- Shared models must remain serializable for later ZeroMQ payloads and SQLite event payloads. Avoid importing subsystem modules into `lagent.common`.
- Do not add YOLO, EasyOCR, CUDA, training, database, profile-loading, capture, HSL, or GUI logic to satisfy this story.

### Architecture Compliance

- **AD-12:** `lagent.common` is the sole shared import root. Allowed consumers are `lagent.hsl`, `lagent.agent`, `lagent.gpu_server`, `lagent.train`, and `lagent.ui`; processes must not import each other.
- **AD-1 / AD-11:** No cross-process mechanism or socket is introduced here. Later runtime communication must use ZeroMQ with DEALER/ROUTER for inference and PUB/SUB for the Party Bus; never REQ/REP.
- **AD-2 / AD-10:** Agents will consume `PerceptionResult`; GPU ownership and OCR stay in the GPU server in later stories.
- **AD-4:** Agents exclusively own `GameState`; only `PartyState` crosses process boundaries.
- **AD-8:** `Action` is the policy-to-HSL contract. HSL instances and OS input are later work; this story must not bypass or implement them.
- **AD-9:** `data/sessions.db` is only a structural directory placeholder here. WAL schema and writers belong to Story 1.3.
- **AD-13:** Recording flags and capture behavior belong to later stories; do not make stubs claim to support recording.

### Library / Framework Requirements

Use the architecture stack versions as compatibility targets: Python 3.12; Pydantic 2.7.x; pyzmq 26.x; structlog 24.x; dxcam 0.0.5; mss 9.0.x; pynput 1.7.x; pywin32 306. SQLite is the Python standard-library module. Keep GPU/training/UI package behavior out of this story even if packaging metadata reserves those future scopes.

### File Structure Requirements

```text
pyproject.toml
lagent/
  common/__init__.py
  common/types.py
  hsl/__init__.py
  hsl/{bezier.py,fatigue.py,timing.py}
  agent/__init__.py
  agent/__main__.py
  agent/base.py
  agent/warlord/
  agent/prophet/
  gpu_server/__init__.py
  gpu_server/__main__.py
  gpu_server/{server.py,inference.py}
  orchestrator/__init__.py
  orchestrator/__main__.py
  ui/__init__.py
  ui/__main__.py
  train/__init__.py
  train/__main__.py
models/{common,warlord,prophet}/
profiles/
recordings/
data/
```

Use `.gitkeep` only where an otherwise-empty non-package directory must be retained. Do not create model files or YAML profile contents in this story. Tests should live in the repository’s standard test location established by the implementation, with no test convention currently present.

### Testing Requirements

The cheapest acceptance checks are the import smoke command and four subprocess invocations from the repository root. Add automated tests for model construction and export topology so later stories cannot silently duplicate shared types. Tests must run without Windows, CUDA, model weights, or a live game client.

### Dependencies and Sequencing

No prior implementation story exists. Story 1.2 owns YAML profile loading and validation; Story 1.3 owns the SQLite WAL database; Story 1.4 owns ZeroMQ wiring and startup handshakes. Do not pull those stories into this scaffold.

### Latest Technical Information

No external web research is required for this greenfield scaffold. The pinned architecture stack is the project contract; validate actual package compatibility during implementation rather than broadening scope to upgrade versions.

### Project Context Reference

No `project-context.md` file was found in the workspace. The authoritative sources are the Epic 1 breakdown, Architecture Spine, Solution Design, PRD, and Technical Addendum listed below.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 1: Runnable Foundation; Story 1.1]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-LAgent-2026-08-04/ARCHITECTURE-SPINE.md` — Invariants AD-1, AD-2, AD-4, AD-8, AD-9, AD-10, AD-10b, AD-11, AD-12, AD-13; Consistency Conventions; Stack; Structural Seed]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-LAgent-2026-08-04/solution-design.md` — System Overview; Container Diagram; Agent Component Diagram; Process Topology & Port Map]
- [Source: `_bmad-output/planning-artifacts/prds/prd-LAgent-2026-08-04/prd.md` — §4.2 Behavior Policy & Decision Engine, FR-7; §6 Technical Constraints]
- [Source: `_bmad-output/planning-artifacts/briefs/brief-LAgent-2026-08-04/brief.md` — Solution; Technical Constraints; Scope]
- [Source: `_bmad-output/planning-artifacts/briefs/brief-LAgent-2026-08-04/addendum.md` — Recommended Tech Stack; Training Pipeline Architecture]

## Dev Agent Record

### Agent Model Used

GitHub Copilot (Amelia / bmad-agent-dev)

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

- `_bmad-output/implementation-artifacts/1-1-project-scaffold-lagent-common-shared-types.md`
