# Story 1.2: YAML Agent Profile Loader & Validation

Status: ready-for-dev

## Story

As Ion,
I want stub warlord.yaml and prophet.yaml profiles loaded and validated by a Pydantic v2 schema at process startup,
so that invalid profile configurations fail fast with a clear error before any session begins.

## Acceptance Criteria

1. Given profiles/warlord.yaml contains required fields, when `python -m lagent.agent --class warlord` is run, then the profile loads, passes schema validation, and logs `Profile loaded: warlord`.
2. Given profiles/warlord.yaml is missing a required field (for example roi_positions), when startup runs, then a ProfileValidationError is raised and process exits non-zero before any session begins.
3. Given a valid profile exists, when profile values are edited and the process is restarted between sessions, then updated values are applied with no code changes.

## Tasks / Subtasks

- [ ] Define AgentProfile schema and nested schema models
- [ ] Add schema sections for ROI positions, FSM bindings, skill key bindings, buff timer durations, confidence thresholds
- [ ] Implement profile loader in lagent.agent startup path
- [ ] Resolve class to YAML file path under profiles/
- [ ] Validate YAML against schema before initializing runtime loops
- [ ] Implement fail-fast error surface
- [ ] Raise ProfileValidationError with clear field-level context
- [ ] Exit before capture/inference/party bus startup on invalid profiles
- [ ] Create stub profile files
- [ ] Add profiles/warlord.yaml and profiles/prophet.yaml with required baseline keys
- [ ] Add tests
- [ ] Positive validation test for each class profile
- [ ] Negative test for missing required field
- [ ] Restart-based test to verify changed values are consumed next startup

## Dev Notes

- Keep profile loading deterministic and explicit; no fallback defaults when schema validation fails.
- Error messages should be operator-readable and pinpoint failing key path.
- Avoid coupling profile parsing with transport setup; validate first, then initialize runtime components.

### Technical Requirements

- Schema validation must use Pydantic v2.
- YAML profiles live under profiles/ with one file per class.
- Config load order: file read -> schema validate -> startup continues.

### Architecture Compliance

- AD-12: Agent imports only lagent.common shared contracts.
- Consistency convention: fail-fast profile validation at process start.
- FR-7 and NFR-10 require no silent fallback behavior.

### File Structure Requirements

- profiles/warlord.yaml
- profiles/prophet.yaml
- lagent/agent startup module(s)
- lagent/common schema definitions (if shared)

### Testing Requirements

- Unit tests for schema valid/invalid inputs.
- CLI startup test asserting non-zero exit on invalid profile.
- Startup test asserting expected success log line for valid profile.

### References

- [Epic breakdown](../planning-artifacts/epics.md)
- [Architecture spine](../planning-artifacts/architecture/architecture-LAgent-2026-08-04/ARCHITECTURE-SPINE.md)
- [PRD](../planning-artifacts/prds/prd-LAgent-2026-08-04/prd.md)

## Dev Agent Record

### Agent Model Used

GPT-5.3-Codex

### Debug Log References

- PM context activation and Epic 1 extraction

### Completion Notes List

- Story file created from Epic 1.2 with schema-first startup sequencing.

### File List

- _bmad-output/implementation-artifacts/1-2-yaml-agent-profile-loader-validation.md
