---
name: session-handoff
description: Preserve Layer 5 local continuity and stop for the final human decision.
---

# SessionHandoff Contract

## Inputs

- All prior stage artifacts.
- Current workflow summary, findings, and local runtime state.

## Output

- `session-handoff.md`

The handoff must include current status, final recommendation pointer, open risks, next action, local state to preserve, and material that must not be promoted.

## Boundaries

- Do not change product, implementation, or governance artifacts.
- Do not delete local control material as a cleanup shortcut.
- Do not mark the task done before the human decision.
