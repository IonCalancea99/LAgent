# Story 1.4: ZeroMQ Channel Wiring & All Processes Running

Status: done

## Story

As Ion,
I want all runtime processes to start, establish their ZeroMQ connections per fixed socket pattern rules, and exchange a startup handshake,
so that inter-process wiring is verified before real logic is added.

## Acceptance Criteria

1. Given GPU Server starts first with ROUTER and both agents start with DEALER, when each agent sends a test inference payload, then GPU Server receives both with agent_id correlation and returns stub PerceptionResult to each origin within 50 ms.
2. Given WL and PP publish stub PartyState messages over PUB and subscribe with SUB, when each publishes, then peer agent and Orchestrator receive the message (including heartbeat-tagged events).
3. Given Orchestrator subscribes to both agent PUB channels, when an agent stops publishing, then Orchestrator logs heartbeat-missed warning after configured interval.

## Tasks / Subtasks

- [x] Implement minimal ZeroMQ endpoint config and startup wiring
- [x] Define fixed ports and message envelope for DEALER/ROUTER and PUB/SUB
- [x] Build GPU server stub request-reply path
- [x] Parse request envelope {agent_id, frame_bytes, roi_map}
- [x] Return stub PerceptionResult routed to originating dealer identity
- [x] Implement Party Bus stubs in WL and PP
- [x] Publish PartyState and heartbeat message types on agent PUB
- [x] Subscribe each agent to peer PUB stream
- [x] Implement Orchestrator heartbeat monitor
- [x] Subscribe orchestrator to both agent PUB endpoints
- [x] Detect missed heartbeat count and emit warning log
- [x] Add startup and handshake tests
- [x] Multi-process integration test for startup ordering and connectivity
- [x] Latency assertion for stub inference response target

## Dev Notes

- Keep socket pattern contracts strict; do not introduce REQ/REP paths.
- Preserve message contracts in lagent.common types to avoid format drift between processes.
- This story is infrastructure only; policy and inference behavior remain stubs.

### Technical Requirements

- pyzmq for all inter-process messaging.
- Patterns:
- Agent -> GPU: DEALER/ROUTER
- Agent -> Agent Party Bus: PUB/SUB
- Agent -> Orchestrator heartbeat: same PUB stream with heartbeat message type
- Correlate inference results by agent_id and dealer identity.

### Architecture Compliance

- AD-1: all cross-process communication through ZeroMQ only.
- AD-11: fixed socket patterns, no REQ/REP anywhere in runtime.
- AD-3: queue behavior remains non-blocking at agent boundaries.

### File Structure Requirements

- lagent/gpu_server/server.py (or equivalent)
- lagent/agent base communication modules
- lagent/orchestrator heartbeat subscriber modules
- Shared message types in lagent/common

### Testing Requirements

- Process-level integration tests with 4 runtime processes.
- Heartbeat-loss simulation test for orchestrator warning behavior.
- Connectivity test ensuring no cross-agent PerceptionResult contamination.

### References

- [Epic breakdown](../planning-artifacts/epics.md)
- [Architecture spine](../planning-artifacts/architecture/architecture-LAgent-2026-08-04/ARCHITECTURE-SPINE.md)
- [Solution design](../planning-artifacts/architecture/architecture-LAgent-2026-08-04/solution-design.md)

## Dev Agent Record

### Agent Model Used

GPT-5.3-Codex

### Debug Log References

- Epic 1 transport mapping and handshake extraction

### Completion Notes List

- Story file created from Epic 1.4 with fixed socket pattern constraints and integration test gates.
- Added shared JSON ZeroMQ contracts, ROUTER GPU stub, agent Party Bus, and heartbeat monitor.
- Focused transport tests cover agent correlation, peer/orchestrator delivery, heartbeat loss, and latency.
- Code review 2026-08-24: BLOCKED locally (pyzmq absent from venv; SSL cert prevents pip install). Code structure correct. Fixed bugs: (1) `_owns_context` guard added to `GpuInferenceServer`, `AgentTransport`, `PartyBus`. (2) Missing `import zmq` inside `serve()` and `start_publisher()` where zmq constants were used but not in scope.
- Resolved 2026-08-24 via Docker (`Dockerfile` added): `pyzmq` installs cleanly in Linux container. All 39 tests pass (`docker run --rm lagent-test`). Status advanced to done.

### File List

- _bmad-output/implementation-artifacts/1-4-zeromq-channel-wiring-process-startup-handshake.md
- lagent/common/transport.py
- lagent/gpu_server/server.py
- lagent/agent/party_bus.py
- lagent/orchestrator/heartbeat.py
- tests/test_story_1_4_transport.py
