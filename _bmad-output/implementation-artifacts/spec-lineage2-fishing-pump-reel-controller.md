---
title: 'Lineage II Fishing Pump/Reel Controller'
type: 'feature'
created: '2026-09-29'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'b92269b6e27b782b9a804a1fabb8f41184cca6b0'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The fishing FSM treats one `tension_indicator` detection as a bite and always reels. It neither compares consecutive fish-HP observations nor follows Lineage II's ordinary-fish rule: Pump while fish HP is steady and Reel while fish HP is regenerating.

**Approach:** Interpret the detected `tension_indicator` box as the filled fish-HP segment, retain a bounded consecutive-observation window, and choose Pump or Reel from the normalized width trend. Keep the FSM in the fish fight after each action, suppress decisions while HP is falling from the previous correct action, and return to IDLE when the gauge disappears or the fight times out.

## Boundaries & Constraints

**Always:** Require a configurable number of confident consecutive detections; use profile-driven keys, thresholds, cooldown, and timeout; clear temporal state on a new cast, timeout, completion, halt, or pause; preserve deterministic replay and existing cast/wait safety behavior; log the observed trend and selected action.

**Ask First:** Adding automatic recognition of high-grade fish deceptive skills, because the target server's visual cue and reversal behavior require verified examples.

**Never:** Train YOLO as a sequence/action policy; consume `inputs.jsonl` in the object-detection trainer; infer trend from detection confidence; treat a box around the complete static gauge frame as an HP-value signal; use pixel colors instead of YOLO detections.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Fish struggling | Consecutive fill widths rise beyond tolerance | Press Reel and remain in the fight | Log trend, reset observation window, enforce cooldown |
| Fish exhausted | Consecutive fill widths remain within tolerance | Press Pump and remain in the fight | Log trend, reset observation window, enforce cooldown |
| Skill takes effect | Fill width falls beyond tolerance | Wait and gather a fresh window | Do not misclassify falling HP as Pump |
| Noisy or incomplete evidence | Too few detections, low confidence, or mixed widths | Wait without key input | Bounded history; normal fight timeout remains active |
| Fight completes | Gauge was seen, then is absent for configured consecutive frames | Return to IDLE | Clear fight history and log completion |
| Bite never appears | No confident gauge before timeout | Return to IDLE | Preserve missed-tension and timeout events |

</frozen-after-approval>

## Code Map

- `lagent/agent/fishing_fsm.py` -- owns temporal observations, Lineage II action selection, lifecycle resets, and event logging.
- `profiles/fishing.yaml` -- supplies Pump/Reel keys and trend, window, cooldown, disappearance, and timeout parameters.
- `tests/test_story_4_4_fishing_tension.py` -- focused deterministic coverage for temporal action decisions and fight completion.
- `docs/site/label-studio.html` -- defines the fishing label boundary as the filled fish-HP segment.
- `docs/site/training.html` -- explains that YOLO learns one frame at a time while the FSM derives motion across frames.

## Tasks & Acceptance

**Execution:**
- [x] `lagent/agent/fishing_fsm.py` -- replace one-shot reel selection with a bounded trend classifier and repeated in-fight actions; retain backward-compatible constructor defaults.
- [x] `profiles/fishing.yaml` -- add `pump` binding and validated numeric policy settings under the fishing FSM bindings.
- [x] `tests/test_story_4_4_fishing_tension.py` -- cover rising, steady, falling, insufficient/low-confidence evidence, disappearance, timeout, profile defaults, and deterministic replay.
- [x] `docs/site/label-studio.html`, `docs/site/training.html` -- document the required box semantics and temporal responsibility boundary.

**Acceptance Criteria:**
- Given three confident consecutive fish-HP fill detections, when normalized width rises above tolerance, then the configured Reel key is emitted once and the fight remains active.
- Given three confident consecutive detections within steady tolerance, when the action cooldown permits, then the configured Pump key is emitted once and the fight remains active.
- Given HP width falls after an action, when the next window is evaluated, then no Pump/Reel input is emitted until a fresh stable or rising window exists.
- Given the gauge was observed and then disappears for the configured frame count, when the FSM ticks, then it logs completion, clears temporal state, and returns to IDLE.
- Given no valid gauge or only low-confidence detections, when the timeout expires, then no fishing skill is pressed and the existing missed-tension path returns to IDLE.

## Spec Change Log

## Design Notes

YOLO remains a per-frame detector. The detected fill width is converted to a relative trend using the largest width observed in the current fight, avoiding dependence on screen resolution. Rising, steady, and falling are controller states derived from multiple detections; they are not additional Label Studio classes. High-grade deceptive fish remain explicitly out of scope until their server-specific cue is captured and labeled.

## Verification

**Commands:**
- `.venv/bin/python -m pytest tests/test_story_4_3_fishing.py tests/test_story_4_4_fishing_tension.py -q` -- expected: all cast/wait and temporal Pump/Reel tests pass.
- `.venv/bin/python -m pytest tests/test_story_1_2_profiles.py tests/test_story_5_3_orchestrator_heartbeat.py -q` -- expected: profile loading and fishing lifecycle integrations remain compatible.

## Suggested Review Order

**Temporal Controller**

- Start with the cumulative width classifier implementing Lineage II's ordinary-fish rule.
	[`fishing_fsm.py:171`](../../lagent/agent/fishing_fsm.py#L171)

- Follow the WAITING flow through deadlines, actions, uncertain evidence, and completion.
	[`fishing_fsm.py:302`](../../lagent/agent/fishing_fsm.py#L302)

- Check policy validation and valid-gauge selection at controller boundaries.
	[`fishing_fsm.py:149`](../../lagent/agent/fishing_fsm.py#L149)
	[`fishing_fsm.py:194`](../../lagent/agent/fishing_fsm.py#L194)

**Training Contract**

- Confirm labels cover only the changing filled fish-HP segment.
	[`label-studio.html:155`](../../docs/site/label-studio.html#L155)

- Confirm temporal trends remain controller logic, not YOLO classes.
	[`training.html:212`](../../docs/site/training.html#L212)

- Verify the new guidance is discoverable through static documentation search.
	[`search-index.js:60`](../../docs/site/assets/search-index.js#L60)

**Configuration And Tests**

- Review server-tunable Pump/Reel keys and temporal thresholds.
	[`fishing.yaml:20`](../../profiles/fishing.yaml#L20)

- Read slow-regeneration and uncertain-evidence regressions first.
	[`test_story_4_4_fishing_tension.py:60`](../../tests/test_story_4_4_fishing_tension.py#L60)
	[`test_story_4_4_fishing_tension.py:154`](../../tests/test_story_4_4_fishing_tension.py#L154)

- Finish with deadline and positional-compatibility boundaries.
	[`test_story_4_4_fishing_tension.py:228`](../../tests/test_story_4_4_fishing_tension.py#L228)
	[`test_story_4_4_fishing_tension.py:274`](../../tests/test_story_4_4_fishing_tension.py#L274)
