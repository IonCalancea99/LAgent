---
title: 'Transport Test Diagnostics and Interference Coverage'
type: 'bugfix'
created: '2026-09-01'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'd01b49eeff509b33bbbaabb296714d4d776d2063'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** ZeroMQ integration tests guarantee cleanup with `try/finally`, but aggregate assertions and uncaptured background-thread exceptions can hide which agent or receive path failed. The Story 1.4 routing test also sends requests sequentially, so it does not exercise cross-agent interference despite requiring origin correlation.

**Approach:** Keep deterministic cleanup, add operation-specific exception context where failures can otherwise be lost, issue both agent requests concurrently, and assert results per named agent. Apply the same diagnostics to the later GPU routing test that repeats this pattern.

## Boundaries & Constraints

**Always:** Preserve DEALER/ROUTER and PUB/SUB contracts; retain cleanup on every exit; preserve original exceptions as causes; identify the affected agent, receiver, or expected message in failures; verify worker and server threads terminate.

**Ask First:** Any production transport behavior change, dependency version change, or conversion of broader test suites to shared fixtures.

**Never:** Swallow exceptions; add a broad outer `except` that degrades pytest tracebacks; weaken latency, routing, payload, heartbeat, or stale-state assertions; skip tests merely because declared dependencies are missing.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Concurrent routing | Warlord and prophet request together | Each DEALER receives a response carrying its own agent ID | Name the agent for timeout, exception, missing result, or mismatched response |
| Worker failure | A request raises inside a background thread | Main test fails with the agent and original exception visible | Capture the exception, assert the named error map is empty, and preserve diagnostic representation |
| Receive timeout | Party-state or heartbeat message does not arrive | Test identifies receiver and expected message | Convert timeout to a contextual pytest failure chained from the timeout |
| Cleanup timeout | Request or server thread remains alive | Test fails instead of silently leaking a daemon thread | Assert thread termination after bounded join |

</frozen-after-approval>

## Code Map

- `tests/test_story_1_4_transport.py` -- Story 1.4 inference routing, PartyBus delivery, heartbeat, and cleanup integration tests.
- `tests/test_story_2_3_gpu_inference.py` -- Concurrent per-agent inference routing test with currently uncaptured worker exceptions.
- `lagent/common/transport.py` -- DEALER request timeout and response decoding contract; no production change expected.
- `lagent/gpu_server/server.py` -- ROUTER identity-based response path; no production change expected.

## Tasks & Acceptance

**Execution:**
- [x] `tests/test_story_1_4_transport.py` -- run both inference requests concurrently, surface named worker/receive failures, replace aggregate checks with per-agent assertions, and assert server shutdown -- prove correlation and make failures actionable.
- [x] `tests/test_story_2_3_gpu_inference.py` -- capture named request-thread exceptions and verify all worker/server threads stop -- prevent silent thread failures in the analogous routing test.

**Acceptance Criteria:**
- Given both agents request inference concurrently, when the GPU server responds, then each named result has the originating agent ID and expected payload without cross-agent contamination.
- Given a background request raises, when the test joins its workers, then pytest reports the responsible agent and original exception instead of only a missing aggregate result.
- Given a PartyBus receive times out, when the test fails, then the receiver and expected message are present in the failure.
- Given cleanup cannot stop a thread within the bound, when teardown completes, then the test reports the leaked thread.
- Given the focused test files run with project dependencies installed, when pytest completes, then all tests in both files pass.

## Spec Change Log

## Design Notes

Pytest already renders synchronous exceptions raised inside a `try` block before executing `finally`; an outer catch is therefore not needed. Exceptions raised inside `threading.Thread` do not propagate to the test thread, so worker targets must catch and record them for an explicit main-thread assertion. Contextual receive helpers should catch only the expected timeout class and use exception chaining.

## Verification

**Commands:**
- `.venv/bin/python -m pytest tests/test_story_1_4_transport.py tests/test_story_2_3_gpu_inference.py -vv` -- expected: both focused files pass with no unhandled-thread warnings.
- `.venv/bin/python -m pytest tests/test_story_1_4_transport.py::test_gpu_routes_stub_result_to_originating_agent -vv` -- expected: concurrent per-agent routing passes and server thread terminates.

## Suggested Review Order

**Concurrent Correlation**

- Synchronizes named requests so cross-agent routing is exercised under overlap.
	[test_story_1_4_transport.py:58](../../tests/test_story_1_4_transport.py#L58)

- Repeats deterministic correlation checks against class-specific inference output.
	[test_story_2_3_gpu_inference.py:81](../../tests/test_story_2_3_gpu_inference.py#L81)

**Failure Diagnostics**

- Groups every named worker failure while preserving original exceptions.
	[test_story_1_4_transport.py:107](../../tests/test_story_1_4_transport.py#L107)

- Qualifies malformed detection payloads with the responsible agent.
	[test_story_2_3_gpu_inference.py:140](../../tests/test_story_2_3_gpu_inference.py#L140)

- Adds receiver and expected-message context to PartyBus timeouts.
	[test_story_1_4_transport.py:19](../../tests/test_story_1_4_transport.py#L19)

**Cleanup Integrity**

- Attempts every cleanup action without masking the primary test failure.
	[test_story_1_4_transport.py:28](../../tests/test_story_1_4_transport.py#L28)

- Captures server-thread crashes and verifies bounded shutdown in the analogous test.
	[test_story_2_3_gpu_inference.py:9](../../tests/test_story_2_3_gpu_inference.py#L9)