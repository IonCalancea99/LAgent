# Story 1.3: Session Database - WAL-mode SQLite Setup

Status: ready-for-dev

## Story

As Ion,
I want data/sessions.db auto-created on first write with the WAL-mode SQLite schema,
so that all runtime processes can append session telemetry and events independently without exclusive locks.

## Acceptance Criteria

1. Given data/sessions.db does not exist, when any process writes first event/session record, then sessions.db is created with WAL journal mode and required tables:
- sessions(session_id, started_at, profile, mode)
- events(id, session_id, ts, source, type, payload_json)
2. Given WL Agent and PP Agent each hold separate SQLite connections, when both write concurrently, then no `database is locked` error occurs and both events persist.
3. Given session start is logged, when querying sessions table, then row contains correct session_id, started_at, profile, mode.

## Tasks / Subtasks

- [ ] Implement shared DB bootstrap utility
- [ ] Create/open data/sessions.db on first access
- [ ] Enable PRAGMA journal_mode=WAL and appropriate write-safe pragmas
- [ ] Create schema idempotently for sessions and events tables
- [ ] Integrate per-process writer usage
- [ ] Ensure each process uses its own SQLite connection
- [ ] Add helper methods for session start and event append
- [ ] Standardize payload_json serialization format
- [ ] Add runtime telemetry hooks
- [ ] Log startup/session lifecycle events from agent/orchestrator paths
- [ ] Add concurrency and schema tests
- [ ] Parallel write test across two connections
- [ ] Cold-start test for DB creation and schema migration idempotency

## Dev Notes

- Keep DB writes append-only for this story; no update-heavy logic.
- Session and event writes should remain lightweight and resilient under high event cadence.
- Maintain strict schema naming to avoid breakage with future overlay/status readers.

### Technical Requirements

- SQLite from Python stdlib.
- WAL mode enabled at DB init time.
- JSON event payload persisted as text in payload_json.

### Architecture Compliance

- AD-9 mandates single shared data/sessions.db with one connection per process.
- Logging convention requires JSON-structured events in DB and stdout.
- UI may read DB later; schema stability matters.

### File Structure Requirements

- data/sessions.db (runtime-created)
- Shared DB utility module under lagent/common or dedicated infra module
- Writer integration points in lagent.agent and lagent.orchestrator

### Testing Requirements

- Integration test for first-write DB creation and schema existence.
- Concurrency test with independent connections (simulated WL + PP).
- Verification test for sessions table row content on session start.

### References

- [Epic breakdown](../planning-artifacts/epics.md)
- [Architecture spine](../planning-artifacts/architecture/architecture-LAgent-2026-08-04/ARCHITECTURE-SPINE.md)
- [Solution design](../planning-artifacts/architecture/architecture-LAgent-2026-08-04/solution-design.md)

## Dev Agent Record

### Agent Model Used

GPT-5.3-Codex

### Debug Log References

- Epic 1 story conversion and architecture mapping

### Completion Notes List

- Story file created from Epic 1.3 with DB bootstrap and concurrency testing focus.

### File List

- _bmad-output/implementation-artifacts/1-3-session-database-wal-sqlite-setup.md
