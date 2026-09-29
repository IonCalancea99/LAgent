---
title: 'Fix Prelabel CLI Dispatch'
type: 'bugfix'
created: '2026-09-29'
status: 'done'
route: 'one-shot'
---

# Fix Prelabel CLI Dispatch

## Intent

**Problem:** `python -m lagent.train prelabel` parsed the subcommand successfully, then forwarded `prelabel` into a second parser that only accepts prelabel options, causing an `unrecognized arguments: prelabel` failure.

**Approach:** Parse the public command once, pass its typed namespace directly to the prelabel command, and cover the complete dispatch path with a regression test.

## Suggested Review Order

**CLI dispatch**

- Pass the parsed namespace directly without mutating global process arguments.
  [`__main__.py:163`](../../lagent/train/__main__.py#L163)

- Preserve standalone prelabel execution while accepting parent-parser arguments.
  [`prelabel.py:319`](../../lagent/train/prelabel.py#L319)

**Regression coverage**

- Exercise the documented public command shape and verify typed pipeline arguments.
  [`test_story_7_2_prelabeling.py:23`](../../tests/test_story_7_2_prelabeling.py#L23)
