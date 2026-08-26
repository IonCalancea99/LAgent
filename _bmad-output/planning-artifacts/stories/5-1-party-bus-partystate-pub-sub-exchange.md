---
storyId: 5.1
epic: "Epic 5: Party Orchestration"
title: "Party Bus — PartyState PUB/SUB Exchange"
status: backlog
---

# Story 5.1: Party Bus — PartyState PUB/SUB Exchange

## User Story

As Ion,
I want each Agent to publish its own `PartyState` (FSM state, HP%, MP%, position, buff presence) each tick and subscribe to the peer agent's `PartyState`,
So that each Agent has real-time visibility into the other's state without shared memory and per the ZeroMQ PUB/SUB pattern (FR-6, AD-1, AD-4, AD-11).

## Acceptance Criteria

### Criterion 1: Peer PartyState is received on each tick

**Given** WL Agent and PP Agent are both running with PUB sockets bound
**When** WL Agent publishes a `PartyState` with `fsm_state: PULLING`
**Then** PP Agent's SUB socket receives the complete `party_state` envelope within one policy tick; PP Agent's policy loop can read `peer_party_state.fsm_state == PULLING`; the serialized payload conforms to the Epic 5 PartyState contract

### Criterion 2: Peer state is read-only and does not mutate local GameState

**Given** the Party Bus message is published
**When** the PP Agent reads the peer state
**Then** PP Agent's own `GameState` is not modified; only the read-only `peer_party_state` field is updated (AD-4)

### Criterion 3: Latest snapshot replaces previous snapshot atomically

**Given** multiple peer messages arrive while the policy loop is processing
**When** the next message is accepted
**Then** the complete latest snapshot replaces the previous snapshot atomically; no fields are merged across messages and no partially updated snapshot is observable

### Criterion 4: Connectivity loss is degraded safely and logged

**Given** the Party Bus connection is lost (WL Agent process killed)
**When** PP Agent attempts to read peer state
**Then** the last valid `PartyState` is retained as read-only, marked stale after the configured missed-heartbeat window, PP Agent does not crash, and a `party_bus_disconnected` warning and session event are logged; the Orchestrator halt protocol is used for the coordinated pause

## Dependencies

- ZeroMQ PUB/SUB Party Bus socket wiring for WL and PP agents
- `PartyState` serialization and snapshot contract
- Read-only `peer_party_state` field on each Agent runtime state
- Session database event logging for disconnect and reconnect warnings
- Orchestrator heartbeat monitor and safe-session-halt protocol

## Notes

This story is the baseline contract for cross-agent coordination. It intentionally limits the runtime contract to one-way publishing and read-only peer state consumption so that state ownership remains local to each Agent and the Orchestrator remains an observer/guardrail instead of a shared-state owner.

## Tasks / Subtasks

- [ ] Implement Party Bus PUB/SUB bootstrap for WL and PP Agent startup.
- [ ] Publish a full `PartyState` snapshot on every policy tick without merging partial updates.
- [ ] Retain the last valid snapshot as read-only while stale and warn on disconnect.
- [ ] Log `party_bus_disconnected` and related session events through the existing DB contract.
- [ ] Validate with deterministic message-flood and disconnect tests.

## Dev Agent Record

### Implementation Plan

- Use the agent-local runtime state as the ownership boundary and publish only the required `PartyState` subset over PUB.
- Keep peer state as a read-only snapshot value with a separate `received_at` timestamp for freshness tracking.
- Treat stale snapshots as non-authoritative; only the Orchestrator can trigger a halt on persistent missed heartbeats.

### Completion Notes

- This story remains in backlog until the Party Bus contract and peer-state handling are implemented and validated against the Epic 5 acceptance criteria.

## Change Log

- 2026-08-26: Updated story to align with the final Epic 5 PartyState contract, stale-snapshot semantics, and disconnect behavior.
