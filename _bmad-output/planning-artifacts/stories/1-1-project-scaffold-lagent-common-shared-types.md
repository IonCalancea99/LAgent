# Story 1.1: Project Scaffold & lagent.common Shared Types

Status: ready-for-dev

## Story

As Ion (sole developer),
I want the full lagent package structure created with all Pydantic v2 shared types defined in lagent.common,
so that every downstream process has a single import source for GameState, PartyState, PerceptionResult, Detection, Action, and AgentProfile and the AD-12 module graph rule is enforced from day one.

## Acceptance Criteria

1. Given the repository is freshly cloned with pyproject.toml listing all runtime dependencies, when `python -c "from lagent.common import GameState, PartyState, PerceptionResult, Detection, Action, AgentProfile"` is run, then all types import without error; each is a Pydantic v2 model with fields matching canonical definitions.
2. Given shared types are defined, when import surfaces are reviewed, then lagent.common is the only module with exports of shared types and no other submodule re-exports them.
3. Given structural seed directories exist, when each process entry point is run (`python -m lagent.agent`, `python -m lagent.gpu_server`, `python -m lagent.orchestrator`, `python -m lagent.ui`), then each process starts and exits with code 0 using stub __main__.py implementations.

## Tasks / Subtasks

- [ ] Initialize project scaffold and packaging
- [ ] Create lagent package and subsystem directories from architecture seed
- [ ] Add __init__.py and stub __main__.py for all runtime entry points
- [ ] Verify module importability and package discovery with Python 3.12
- [ ] Implement shared types in lagent.common
- [ ] Add Pydantic v2 models for Detection, PerceptionResult, PartyState, Action, GameState, AgentProfile
- [ ] Export shared types only from lagent.common.__init__
- [ ] Enforce AD-12 dependency direction
- [ ] Ensure no cross-process imports between lagent.agent, lagent.gpu_server, lagent.orchestrator, lagent.ui, lagent.train
- [ ] Add minimal automated checks
- [ ] Add a smoke test for shared type imports
- [ ] Add process startup smoke tests for the four runtime modules

## Dev Notes

- Keep this story purely foundational: no runtime logic, no transport payload logic beyond import-safe shape definitions.
- Shared type contract must be stable because all later stories depend on these symbols and field names.
- Follow naming and path conventions exactly to avoid rework in stories 1.2-1.4.

### Technical Requirements

- Python version: 3.12.
- Pydantic v2 is mandatory for shared types and future profile schemas.
- Process entry point convention is `python -m lagent.<subsystem>`.
- Use snake_case module names and preserve canonical fields for Detection (`class_name`, `confidence`, `bbox_xyxy`).

### Architecture Compliance

- AD-12: lagent.common is the only shared import root for cross-process contracts.
- AD-5: UI is sole launcher process (actual launch behavior implemented later; structure starts here).
- Structural seed in Architecture Spine is the source of truth for package layout.

### File Structure Requirements

- Create only architecture-seed paths for this story:
- lagent/common, lagent/hsl, lagent/agent, lagent/gpu_server, lagent/orchestrator, lagent/ui, lagent/train
- models/common, models/warlord, models/prophet
- profiles, recordings, data

### Testing Requirements

- Import smoke test for all shared symbols.
- Startup smoke tests for module entry points.
- Test that forbidden shared-type re-export patterns are absent.

### References

- [Epic breakdown](../planning-artifacts/epics.md)
- [Architecture spine](../planning-artifacts/architecture/architecture-LAgent-2026-08-04/ARCHITECTURE-SPINE.md)
- [Solution design](../planning-artifacts/architecture/architecture-LAgent-2026-08-04/solution-design.md)
- [PRD](../planning-artifacts/prds/prd-LAgent-2026-08-04/prd.md)

## Dev Agent Record

### Agent Model Used

GPT-5.3-Codex

### Debug Log References

- _bmad/scripts/resolve_customization.py output for PM agent context

### Completion Notes List

- Story file created from Epic 1.1 with architecture guardrails and test gates.

### File List

- _bmad-output/implementation-artifacts/1-1-project-scaffold-lagent-common-shared-types.md
