---
name: verification
description: Independently verify implementation and produce a verification report.
---

# Verification Contract

## Inputs

- `technical-design.md`
- `implementation.md`
- Upstream L1/L3 deltas and current repository checks.

## Output

- `verification-report.md`

The report must include commands run, observed results, evidence paths or summaries, findings, target stages, and residual risk.

## Boundaries

- Do not edit implementation files.
- Do not accept Implementation self-verification as independent evidence.
- Do not mark unresolved findings as passed.
