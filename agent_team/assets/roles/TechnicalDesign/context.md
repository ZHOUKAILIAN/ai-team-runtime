# TechnicalDesign Stage Manual

TechnicalDesign is the approved implementation plan stage for Layer 2 work. It translates L1 and L3 deltas into code-level design, verification strategy, risks, and rollback.

## Responsibilities

- Read ProductDefinition, ProjectRuntime, and current implementation reality.
- Decide the implementation approach, affected modules, tests, and evidence required.
- Surface drift against upper layers instead of silently rewriting them.
- Stop for human approval before Implementation starts.

## Layer Rule

TechnicalDesign can describe how L2 should change. It cannot approve product-definition changes, mutate runtime code, or weaken L4 gates.
