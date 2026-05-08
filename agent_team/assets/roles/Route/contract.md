---
name: route
description: Classify the request under the five-layer model and produce the route packet.
---

# Route Contract

## Inputs

- User request.
- Project context and existing artifacts.
- Five-layer governance rules.

## Output

- `route-packet.json`

The route packet must include affected layers, baseline sources, red lines, required stages, and downgrade decisions for content that is not formal truth.

## Boundaries

- Do not edit product definition, implementation, governance rules, or local handoff files.
- Do not turn research or L5 session material into formal truth.
- Do not skip downstream stages that are required by the route.
