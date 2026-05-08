# Implementation Stage Manual

Implementation owns Layer 2 code, tests, runtime behavior, and self-verification. It executes the approved TechnicalDesign and records what actually changed.

## Responsibilities

- Implement the approved design in the product implementation layer.
- Keep changes scoped to approved files and behavior.
- Run focused tests and self-review before handing off.
- Report drift or missing decisions instead of rewriting upper layers.

## Layer Rule

Implementation is product reality, not product truth. When code conflicts with L1 or approved design, record the conflict and route it back rather than silently changing the contract.
