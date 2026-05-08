---
name: project-runtime
description: Produce the Layer 3 project landing delta.
---

# ProjectRuntime Contract

## Inputs

- `route-packet.json`
- Approved or current `product-definition-delta.md`
- Repository structure and runtime context.

## Output

- `project-landing-delta.md`

The delta must name default entrypoints, run/package/config defaults, artifact locations, and project-specific landing rules affected by the request.

## Boundaries

- Do not change product semantics.
- Do not define shared collaboration, review, or merge gates.
- Do not include unsettled research or temporary local notes as L3 defaults.
