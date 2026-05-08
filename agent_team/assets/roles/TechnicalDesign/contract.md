---
name: technical-design
description: Produce the approved Layer 2 technical design before implementation.
---

# TechnicalDesign Contract

## Inputs

- `route-packet.json`
- `product-definition-delta.md`
- `project-landing-delta.md`
- Existing code, tests, and implementation constraints.

## Output

- `technical-design.md`

The design must include scope, affected files or modules, data/control flow, test strategy, drift risks, rollback or recovery notes, and explicit non-goals.

## Boundaries

- Do not edit implementation files.
- Do not redefine L1 or L3 truth.
- Do not advance to implementation without human approval.
