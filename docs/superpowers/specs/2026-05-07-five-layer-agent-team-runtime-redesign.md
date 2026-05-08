# Five-Layer Agent Team Runtime Redesign

## Background

The current Agent Team runtime is centered on a fixed product delivery chain:

```text
Product -> Dev technical plan -> Dev implementation -> QA -> Acceptance
```

That model separates product, development, QA, and acceptance work, but it still treats a task PRD as the main upstream artifact. Under the five-layer architecture, a task proposal is not automatically Layer 1 product truth. The runtime must first classify which parts of the request belong to product definition, implementation reality, project landing, governance, local session control, or research.

## Design Decision

Replace the role-first workflow with a layer-routed workflow. The runtime's first executable stage is `Route`, and every later stage has explicit layer metadata:

```text
Route
  -> ProductDefinition
  -> ProjectRuntime
  -> TechnicalDesign
  -> Implementation
  -> Verification
  -> GovernanceReview
  -> Acceptance
  -> SessionHandoff
  -> Done
```

The initial implementation may run all stages in order. A later optimization can let `Route` skip non-applicable stages. Even before conditional skip is added, every stage must produce an artifact that says whether the layer has a real delta, no-op, or unresolved human decision.

## Layer Model

| Layer | Runtime meaning | Canonical owner |
| --- | --- | --- |
| L1 Product Definition | Stable product semantics, core objects, business/API meaning, long-term rules | Repository product definition docs |
| L2 Product Implementation | Code, tests, migrations, runtime behavior, implementation reports | Product repository implementation |
| L3 Project Landing | How this project runs, starts, packages, deploys, configures, and lays out the product | Repository project landing docs |
| L4 Repository Governance | Runtime process, gates, review discipline, writeback and merge policy | Repository governance docs |
| L5 Local Control | Task/session workspace, handoff, temporary evidence, unresolved context | `.agent-team` runtime/session artifacts |
| Research | Comparisons, background research, arguments, writing drafts | Research archive only |

## Stage Responsibilities

| Stage | Primary layer | Artifact | Responsibility |
| --- | --- | --- | --- |
| `Route` | L4 | `route-packet.json` | Classify request, affected layers, red lines, required stages, and baseline sources |
| `ProductDefinition` | L1 | `product-definition-delta.md` | Extract stable product-definition candidates from the task proposal and mark non-L1 content |
| `ProjectRuntime` | L3 | `project-landing-delta.md` | Capture startup/deploy/config/layout/runtime-default impacts |
| `TechnicalDesign` | L2 | `technical-design.md` | Plan implementation against approved L1/L3 deltas and current implementation reality |
| `Implementation` | L2 | `implementation.md` | Apply code/test/runtime changes and provide self-verification |
| `Verification` | L2 | `verification-report.md` | Independently verify implementation against L1, L2, L3, and task scope |
| `GovernanceReview` | L4 | `governance-review.md` | Check layer violations, red-line promotions, evidence quality, writeback obligations, and merge readiness |
| `Acceptance` | L1 + L4 | `acceptance-report.md` | Recommend final Go/No-Go from product result and governance evidence |
| `SessionHandoff` | L5 | `session-handoff.md` | Preserve current session state, next steps, unresolved decisions, and non-promoted local material |

## Artifact Semantics

`product-definition-delta.md` is not the canonical product definition. It is the current task's proposed Layer 1 patch. After human approval and governance review, it may be written back to canonical product definition docs.

Repository-level stable entries:

```text
docs/product-definition/     # L1 canonical entries
docs/project-landing/        # L3 canonical entries
docs/governance/             # L4 canonical entries
.agent-team/_runtime/...     # L5 session state and machine traces
```

Session-level artifacts:

```text
route-packet.json
change-proposal.md
product-definition-delta.md
non-l1-classification.md
project-landing-delta.md
technical-design.md
implementation.md
verification-report.md
governance-review.md
acceptance-report.md
session-handoff.md
```

## Gates

The first hard gate is L1 classification. `ProductDefinition` must distinguish:

- L1 candidates: stable product semantics, core objects, long-term rules, business/API meaning.
- Non-L1 task content: delivery scope, implementation hints, project landing impacts, governance impacts, local handoff, research, and open questions.

No implementation stage should treat a task PRD or change proposal as canonical L1 by default.

`GovernanceReview` must block or flag:

- Handoff, task notes, or local logs promoted to formal truth.
- Implementation reality silently promoted to product semantics.
- Research material promoted to governance or product definition without adoption.
- Physical repo split or public/private decisions made before classification and formal-entry boundaries.
- Missing writeback targets for accepted L1/L3/L4 deltas.

## Compatibility

This is an intentional breaking change. The old stages `Product`, `Dev`, `QA`, and `Acceptance` are replaced as runtime-control stages. `Acceptance` remains as a final recommendation stage, but it now validates product result plus governance evidence rather than only PRD alignment.

CLI names may stay stable (`agent-team run`) while the underlying stages and artifacts change.

## Initial Implementation Scope

1. Add init-time five-layer classification: `agent-team init` creates `agent-team/project/five-layer/` and can invoke `codex exec` with the GitHub-hosted `five-layer-classifier` skill source to produce `classification.md`.
2. Add layer metadata to stage policies and stage contracts.
3. Replace default stages and role slugs with the five-layer stages.
4. Update the stage machine for the new linear workflow and approval gates.
5. Update stage input selection and dry-run artifacts.
6. Replace packaged role assets with five-layer role assets.
7. Update README and focused tests for the new stage model.

Conditional stage skipping from `route-packet.json` is intentionally deferred until the fixed five-layer pipeline is stable.

The init-time classification is a split-preparation pass only. It must not move, delete, publish, or physically split files. Its job is to identify L1/L3/L4 formal entries, L5 local-retention material, research/archive material, and high-risk misclassifications before runtime work starts. The runtime should prefer the remote skill source URL over a local installed copy, while allowing the local copy only as a cache or fallback.
