# ProductDefinition Stage Manual

ProductDefinition owns Layer 1 deltas. It answers what stable product semantics may change, and it explicitly rejects implementation detail, workflow policy, and local session material.

## Responsibilities

- Extract L1 candidates from the routed request.
- Define stable product goals, core objects, core operating model, responsibility boundaries, and long-term semantics.
- Separate this-task PRD details from durable product definition.
- Record product-definition conflicts or approval questions.

## Layer Rule

L1 has the highest change threshold. Lower layers can report drift against L1, but they cannot rewrite it. ProductDefinition may propose a delta; the human gate decides whether it becomes accepted product truth.
