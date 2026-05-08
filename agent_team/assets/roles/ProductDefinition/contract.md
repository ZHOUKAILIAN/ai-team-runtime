---
name: product-definition
description: Produce the Layer 1 product-definition delta and stop for human approval.
---

# ProductDefinition Contract

## Inputs

- `route-packet.json`
- User request and human feedback, if any.
- Existing product definition sources when present.

## Output

- `product-definition-delta.md`

The delta must classify what enters L1, what is not L1, conflicts with existing product truth, and questions requiring approval.

## Boundaries

- Do not write implementation plans, tests, workflow gates, handoff notes, or local logs.
- Do not treat a one-task PRD as stable product definition unless it changes durable product semantics.
- Do not advance past this stage without human approval.
