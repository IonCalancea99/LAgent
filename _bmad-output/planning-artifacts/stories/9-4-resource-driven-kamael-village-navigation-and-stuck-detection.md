---
storyId: 9.4
epic: "Epic 9: Quest Mode"
title: "Resource-Driven Kamael Village Navigation & Stuck Detection"
status: ready-for-dev
---

# Story 9.4: Resource-Driven Kamael Village Navigation & Stuck Detection

## User Story

As Ion,
I want the quest route to be driven by the selected resource, with explicit stuck detection,
so that the agent can navigate to Marcela and the required quest area without wandering or continuing on a stale route.

## Acceptance Criteria

### Criterion 1: Route discovery is resource-driven

**Given** the quest contract specifies a route to the starting NPC or objective area
**When** the Agent loads it
**Then** it executes the route as a bounded sequence of positions, waypoints, and actions rather than a hardcoded single-purpose script

**Given** the route is absent or incomplete
**When** the quest begins
**Then** the system fails closed and records a safe-stop reason instead of assuming a default movement pattern

### Criterion 2: Navigation failure is explicit

**Given** the target waypoint is not reached within the configured timeout or retry budget
**When** the navigation step is evaluated
**Then** the agent recognizes a `navigation_timeout`, `npc_not_found`, or `route_stuck` condition and transitions to a safe stop or operator-visible error state

**Given** the map/object detection is ambiguous or the route is inconsistent with the frame evidence
**When** the objective is checked
**Then** the system does not continue to the next objective without a resolved route state

### Criterion 3: Recovery remains bounded

**Given** the quest route has a reroute or retry path defined in the resource
**When** the navigation fails once
**Then** the agent may retry only within the configured limit and logs the failure reason with objective context

**Given** the retry count is exhausted
**When** the route is evaluated
**Then** the quest enters a safe terminal state and the operator is notified through the existing session event channel

## Dependencies

- Story 9.1 quest contract definition and route metadata.
- Story 9.2 NPC and objective perception fixtures.
- Epic 6 lifecycle and recovery semantics.

## Developer Context

The first quest is bounded to Kamael village and a specific NPC path, but the route itself should still be represented as structured metadata instead of a hardcoded script. This allows the quest to be validated, routed, and logged without overfitting the planner to one single movement routine.

Navigation must be evidence-driven. The agent should move only to the expected route points and verify it reached the right area before trying to interact. Stuck detection must be explicit and terminate the quest early when the objective cannot be proved.

## Technical Requirements

- Add resource-defined route waypoints and timeout/retry rules for the quest path.
- Implement safe-stop reasons for route failure, NPC not found, and timeout.
- Attach structured objective and route failure logs to the session telemetry stream.
- Keep the route resolution logic bounded to the selected quest and not a generic world-graph planner.

## Testing Requirements

- Test route success for the known path to Marcela.
- Test stuck detection after waypoint timeout.
- Test invalid or missing route metadata triggers fail-closed behavior.
- Test route failure logs the correct reason and objective index.

## Architecture Compliance

- AD-4: navigation state remains in the agent-local quest logic.
- AD-11: external navigation actions stay within approved HSL dispatch and safety boundaries.
- AD-12: the quest route contract remains centrally defined and versioned.

## File Structure

Expected implementation surfaces: `lagent/agent/quest/navigation.py`, quest route definitions in profile resources, and tests under `tests/test_story_9_4_quest_navigation.py`.

## Completion Status

Ready for development.

## Change Log

- 2026-08-26: Story created from Epic 9 requirement and sprint proposal.
