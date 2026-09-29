## Deferred from: code review of 4-3-fishing-fsm-cast-wait (2026-08-26)

- **Timeout Action Ambiguity** — Return value `Action(wait, 0.0)` when timeout expires is semantically ambiguous to caller. Is this a busy-wait, immediate re-invocation, or no-op? Design issue in loop/FSM interface, defer to architecture review.
- **Floating Point Precision on Micro-Timeouts** — System clock resolution (~1-10ms) can cause spurious timeouts for `wait_timeout < 0.01s`. Unlikely in real deployments; defer to performance tuning phase.
- **Unused Profile Parameter** — Constructor accepts `profile` parameter but never references it. Hardcoded values used instead. Deferred as planned enhancement for future configuration via profile.

## Deferred from: code review of 3-4-micro-drift-error-injection (2026-08-26)

- Dict profile Bezier range is ignored in `lagent/hsl/mouse.py:390`; pre-existing behavior, not introduced by Story 3.4.

- source_spec: `_bmad-output/implementation-artifacts/spec-lineage2-fishing-pump-reel-controller.md`
	summary: Advance FSM deadlines when inference results stop arriving.
	evidence: `AgentLoop.tick()` bypasses the state handler when frame/result queues are empty or mismatched, so both the pre-existing bite timeout and the new fight timeout cannot fire during an inference outage.
- source_spec: `_bmad-output/implementation-artifacts/spec-lineage2-fishing-pump-reel-controller.md`
	summary: Synchronize heartbeat pause snapshots with the loop's transitioned FSM state.
	evidence: `AgentLoop` owns the post-action state transition while `FishingFSM.pause_for_session_halt()` snapshots its last invoked state, so a pause between those operations can resume one state behind.