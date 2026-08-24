# Story 1.4: ZeroMQ Channel Wiring & All Processes Running

Status: ready-for-dev

## Story

As Ion,
I want all runtime processes to start, establish their ZeroMQ connections per fixed socket pattern rules, and exchange a startup handshake,
so that inter-process wiring is verified before real logic is added.

## Acceptance Criteria

1. Given GPU Server starts first with ROUTER and both agents start with DEALER, when each agent sends a test inference payload, then GPU Server receives both with agent_id correlation and returns stub PerceptionResult to each origin within 50 ms.
2. Given WL and PP publish stub PartyState messages over PUB and subscribe with SUB, when each publishes, then peer agent and Orchestrator receive the message (including heartbeat-tagged events).
3. Given Orchestrator subscribes to both agent PUB channels, when an agent stops publishing, then Orchestrator logs heartbeat-missed warning after configured interval.

## Tasks / Subtasks

- [ ] Implement minimal ZeroMQ endpoint config and startup wiring
- [ ] Define fixed ports and message envelope for DEALER/ROUTER and PUB/SUB
- [ ] Build GPU server stub request-reply path
- [ ] Parse request envelope {agent_id, frame_bytes, roi_map}
- [ ] Return stub PerceptionResult routed to originating dealer identity
- [ ] Implement Party Bus stubs in WL and PP
- [ ] Publish PartyState and heartbeat message types on agent PUB
- [ ] Subscribe each agent to peer PUB stream
- [ ] Implement Orchestrator heartbeat monitor
- [ ] Subscribe orchestrator to both agent PUB endpoints
- [ ] Detect missed heartbeat count and emit warning log
- [ ] Add startup and handshake tests
- [ ] Multi-process integration test for startup ordering and connectivity
- [ ] Latency assertion for stub inference response target

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

### File List

- _bmad-output/implementation-artifacts/1-4-zeromq-channel-wiring-process-startup-handshake.md
