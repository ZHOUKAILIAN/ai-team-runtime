---
name: implementation
description: Implement the approved technical design and record Layer 2 evidence.
---

# Implementation Contract

## Inputs

- `technical-design.md`
- Approved upstream deltas.
- Current code, tests, and runtime constraints.

## Output

- `implementation.md`

The implementation report must include changed files, behavior summary, self-review, commands run, failures or skipped checks, and unresolved risks.

## Boundaries

- Do not change L1, L3, or L4 documents unless the approved design explicitly routes that writeback.
- Do not claim independent verification.
- Do not hide test failures or unrun checks.
