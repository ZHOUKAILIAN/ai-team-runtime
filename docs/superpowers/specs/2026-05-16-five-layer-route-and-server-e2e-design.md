# Five-Layer Route And Server E2E Runtime Design

## Background

The current five-layer runtime still executes as a fixed nine-stage pipeline. `Route` produces a classification artifact, but downstream execution does not consume the routing result. In practice this means nearly every task is forced through `ProductDefinition`, even when the change is only Layer 2 implementation or Layer 3 project landing work.

The runtime also states that server-side changes should be verified end to end, but this is only a prompt-level requirement. There is no stable project-level protocol for how to start services, connect to a test environment, run API flows, or collect independent verification evidence.

## Problems

1. `Route` is descriptive only. It does not actually drive stage selection.
2. `ProductDefinition` has only one useful path: produce a delta and stop for approval. This makes `L1` feel mandatory on every task.
3. The layer model is missing a clear formal rule for where server-side end-to-end verification configuration belongs.
4. Verification policy, project runtime wiring, and local secrets are not separated cleanly across `L3`, `L4`, and `L5`.

## Goals

- Make `Route` the real workflow router.
- Enter `L1` approval only when the request changes stable product semantics.
- Keep lower layers from silently rewriting upper-layer truth.
- Add a stable server-side E2E verification protocol driven by repository-owned `L3` runtime definitions.
- Make test-environment access project-local and private, not versioned shared truth.

## Non-Goals

- Do not introduce automatic writeback/promotion into canonical `L1/L3/L4` documents in this change.
- Do not build a general-purpose external test framework.
- Do not store private test-environment connection details in repository-tracked files.
- Do not redefine five layers as a new taxonomy.

## Core Decisions

### Layer Responsibility

- `L1 ProductDefinition`
  - Owns stable product semantics, core objects, API/business meaning, and long-term acceptance semantics.
  - Example: whether an API success means an order is created and moves to a particular business state.
  - Does not own service startup, test-environment wiring, or verification secrets.

- `L2 ProductImplementation`
  - Owns code, tests, runtime behavior, implementation reports, and implementation drift reporting.
  - Can implement or report drift.
  - Cannot promote implementation reality into `L1`.

- `L3 ProjectRuntime`
  - Owns long-lived project runtime defaults, including server-side end-to-end verification runtime recipes.
  - This is the correct layer for service startup commands, healthchecks, default API verification flows, dependency services, and required local secret names.

- `L4 Governance`
  - Owns verification policy and workflow gates.
  - This is the correct layer for deciding when E2E is mandatory, what evidence is required, and when a stage must return `blocked`.

- `L5 LocalControl`
  - Owns project-local private runtime configuration and session-local execution traces.
  - Real test-environment URLs, tokens, cookies, private headers, and local overrides belong here and must not be committed.

### ProductDefinition Three-State Outcome

`ProductDefinition` must no longer act like a universal approval gate. It should produce one of three explicit outcomes:

- `no_l1_delta`
  - The request does not change stable product semantics.
  - No `L1` approval wait state is entered.

- `l1_delta_pending_approval`
  - The request proposes a real `L1` semantic change.
  - Enter the existing human approval gate.

- `blocked_missing_decision`
  - The implementation cannot proceed because a required product decision is missing.
  - The workflow blocks with focused questions instead of guessing.

### Route As Execution Router

`Route` remains mandatory, but it becomes an execution controller rather than an intake-only note writer.

`route-packet.json` must become the workflow source for:

- `affected_layers`
- `required_stages`
- `stage_decisions`
- `baseline_sources`
- `red_lines`
- `verification_mode`
- `unresolved_questions`

`Route` decides whether a stage is:

- `required`
- `skipped`
- `blocked`

The stage machine must advance to the next `required` stage rather than following a fixed linear chain.

### Server E2E Verification Ownership

Server-side end-to-end verification is repository-declared and runtime-executed:

- Repository declares the runtime recipe in `L3`.
- Runtime loads the recipe and executes it.
- Governance checks whether the right recipe and evidence were used.
- Local private connection details come from `L5`.

This prevents ad hoc verification logic from being reinvented on every task and avoids putting secret environment details into shared docs.

## Workflow Changes

### Current Workflow Problem

Today the flow behaves as if every task is:

`Route -> ProductDefinition -> wait -> ProjectRuntime -> TechnicalDesign -> wait -> Implementation -> Verification -> GovernanceReview -> Acceptance -> SessionHandoff`

That is valid only for tasks with genuine `L1` change. It is too heavy for ordinary `L2/L3` work.

### New Workflow Semantics

`Route` always runs first.

After `Route`, the state machine chooses the next stage from `required_stages`.

Examples:

- Pure `L2` bug fix:
  - `Route -> TechnicalDesign -> Implementation -> Verification -> GovernanceReview -> Acceptance -> SessionHandoff`

- `L3` runtime/deploy/config adjustment:
  - `Route -> ProjectRuntime -> TechnicalDesign -> Implementation -> Verification -> GovernanceReview -> Acceptance -> SessionHandoff`

- Real `L1` product semantic change:
  - `Route -> ProductDefinition(wait for approval) -> ProjectRuntime if needed -> TechnicalDesign -> Implementation -> Verification -> GovernanceReview -> Acceptance -> SessionHandoff`

### Route Packet Requirements

`route-packet.json` must minimally support:

```json
{
  "affected_layers": ["L2", "L3", "L4", "L5"],
  "required_stages": ["ProjectRuntime", "TechnicalDesign", "Implementation", "Verification", "GovernanceReview", "Acceptance", "SessionHandoff"],
  "stage_decisions": {
    "ProductDefinition": {
      "decision": "skipped",
      "reason": "no_l1_delta"
    },
    "ProjectRuntime": {
      "decision": "required",
      "reason": "server_e2e_recipe_changed"
    }
  },
  "verification_mode": "server_e2e_required",
  "baseline_sources": [
    "docs/project-runtime/verification.md",
    "docs/governance/verification-policy.md"
  ],
  "red_lines": [
    "lower_layers_must_not_rewrite_upper_layer_truth",
    "do_not_promote_l5_or_research_to_formal_truth"
  ],
  "unresolved_questions": []
}
```

Field names can vary if needed for implementation compatibility, but the semantics above are required.

## Server E2E Verification Design

### L3 Formal Artifacts

Add formal `L3` verification runtime artifacts:

- `docs/project-runtime/verification.md`
  - Human-readable explanation of how server-side E2E verification works in this project.
  - Describes services, dependencies, expected flows, data policy, and coverage intent.

- `docs/project-runtime/verification.yaml`
  - Machine-readable verification runtime recipe used by the runtime.

Recommended top-level sections:

- `service_profiles`
- `environment_requirements`
- `data_policy`
- `flows`
- `evidence`

Example shape:

```yaml
service_profiles:
  api:
    workdir: apps/api
    start_command: npm run dev:test
    healthcheck:
      url: http://127.0.0.1:38080/health
      expect_status: 200
      timeout_seconds: 90
    dependencies:
      - redis
      - mysql

environment_requirements:
  profile: integration-test
  required_private_keys:
    - TEST_BASE_URL
    - TEST_AUTH_TOKEN
    - TEST_DB_READONLY_DSN

data_policy:
  db_readonly: true
  mutation_via_api_only: true

flows:
  - id: create_order
    description: create an order through public API and confirm the resulting state
    steps:
      - kind: request
        request:
          method: POST
          path: /api/orders
          body_template: order_create_basic
      - kind: assert_response
        expect_status: 200
        expect_json_path:
          - path: $.code
            equals: 0
      - kind: request
        request:
          method: GET
          path: /api/orders/${response.body.data.id}
      - kind: assert_response
        expect_status: 200
      - kind: readonly_db_check
        query_id: order_status_by_id

evidence:
  save_request_response: true
  save_healthcheck_output: true
  save_readonly_db_results: true
```

### L4 Governance Artifact

Add a formal governance artifact:

- `docs/governance/verification-policy.md`

This policy must define:

- Which change categories require `server_e2e_required`
- Which evidence is mandatory for pass
- Which conditions force `blocked`
- When static or unit-only verification is acceptable

Required governance rules:

- Server-side behavioral changes that affect API behavior, persistence behavior, orchestration behavior, or request/response contracts must run server E2E unless the route packet explicitly justifies a narrower mode.
- `Verification` evidence must be independent from `Implementation` self-verification.
- Read-only database verification is allowed.
- Database writes are forbidden during verification.
- If data setup or cleanup is required, it must happen through declared APIs or flows, not direct database mutation.

### L5 Local Private Configuration

Add a non-versioned project-local private configuration file:

- `.agent-team/local/verification-private.json`

This file is project-level, long-lived, and local only.

It may contain:

- Real base URLs
- Tokens
- Cookies
- Private headers
- Local override ports
- Read-only database DSNs

It must not contain session summaries, governance policy, or shared product truth.

Recommended shape:

```json
{
  "profiles": {
    "integration-test": {
      "TEST_BASE_URL": "https://test-api.example.internal",
      "TEST_AUTH_TOKEN": "redacted-local-secret",
      "TEST_DB_READONLY_DSN": "mysql://readonly@host/db"
    }
  }
}
```

Session-local execution traces remain under the existing `.agent-team/<session>/...` artifact tree.

### Verification Execution Order

For `verification_mode: server_e2e_required`, `Verification` should execute in this order:

1. Read `L4` verification policy.
2. Load `L3` verification recipe.
3. Resolve required local private keys from `L5`.
4. Start the declared service profile.
5. Run healthcheck.
6. Execute declared API flows.
7. Collect declared evidence.
8. Produce `verification-report.md` and structured evidence files.

### Required Evidence For Pass

At minimum:

- Service startup command and exit or process status
- Healthcheck result
- Request and response evidence for each flow step
- Any declared read-only verification output
- Final pass/fail/blocked conclusion

### Required Block Conditions

`Verification` must return `blocked` when:

- Required private connection info is missing from `L5`
- `L3` recipe is missing, malformed, or incomplete for a required flow
- The service profile cannot start or pass healthcheck
- Verification requires data mutation but no API flow exists to perform it
- Independent evidence cannot be collected

## Runtime And State Changes

### Route / Stage Machine

- Consume `required_stages` from `route-packet.json`
- Add stage statuses such as `skipped` or `not_applicable`
- Move from fixed stage transitions to next-required-stage lookup
- Preserve wait states only for stages that are actually required

### ProductDefinition Result Contract

Add an explicit stage result field for `product_definition_outcome`, with values:

- `no_l1_delta`
- `l1_delta_pending_approval`
- `blocked_missing_decision`

Behavior:

- `no_l1_delta` skips the `WaitForProductDefinitionApproval` state
- `l1_delta_pending_approval` enters the approval state
- `blocked_missing_decision` enters blocked state with focused questions

### Verification Result Contract

Add explicit verification metadata for runtime-driven server E2E:

- `verification_mode`
- `service_profile`
- `flow_ids`
- `evidence_paths`
- `blocked_reason` when applicable

## File And Surface Changes

Expected repository changes:

- Runtime logic
  - `agent_team/stage_machine.py`
  - `agent_team/runtime_driver.py`
  - `agent_team/stage_inputs.py`
  - `agent_team/execution_context.py`
  - `agent_team/stage_policies.py`
  - `agent_team/models.py`
  - `agent_team/state.py`
  - `agent_team/cli.py`

- Role contracts and guidance
  - `agent_team/assets/roles/Route/contract.md`
  - `agent_team/assets/roles/Route/context.md`
  - `agent_team/assets/roles/ProductDefinition/contract.md`
  - `agent_team/assets/roles/ProductDefinition/context.md`
  - `agent_team/assets/roles/ProjectRuntime/contract.md`
  - `agent_team/assets/roles/ProjectRuntime/context.md`
  - `agent_team/assets/roles/Verification/contract.md`
  - `agent_team/assets/roles/Verification/context.md`
  - `agent_team/assets/roles/GovernanceReview/contract.md`

- New project formal artifacts
  - `docs/project-runtime/verification.md`
  - `docs/project-runtime/verification.yaml`
  - `docs/governance/verification-policy.md`

- Local non-versioned support
  - `.agent-team/local/verification-private.json` template or generated local file
  - `.gitignore` updates if required

- Tests
  - `tests/test_stage_machine.py`
  - `tests/test_runtime_driver.py`
  - `tests/test_execution_context.py`
  - `tests/test_stage_policies.py`
  - `tests/test_cli.py`
  - new focused tests for route-driven skipping and verification recipe loading if needed

## Acceptance Criteria

- A task with no `L1` semantic change does not stop at `ProductDefinition` approval.
- `Route` stage output actually determines the next executable stage.
- `ProductDefinition` can return `no_l1_delta`, `l1_delta_pending_approval`, or `blocked_missing_decision`.
- Server-side verification can be declared in `L3` and executed by runtime without placing private secrets into repository-tracked files.
- Governance can enforce when E2E is mandatory and what evidence is required.
- Verification uses read-only database validation only and relies on APIs for mutation/setup flows.

## Risks

- Route classification becomes more powerful, so route mistakes can skip necessary review if governance backstops are weak.
- Verification recipe design can become too complex if it tries to model every testing edge case up front.
- Projects with weak local environment discipline may still fail verification due to stale or missing `L5` private configuration.

## Mitigations

- Keep `GovernanceReview` responsible for checking skipped-stage correctness.
- Start with a narrow server E2E recipe schema focused on startup, healthcheck, API flow, and evidence.
- Make blocked conditions explicit and fail closed instead of guessing.

## Open Follow-Up

- Canonical writeback and formal promotion from session delta into repository `L1/L3/L4` truth should be designed in a later change.
- Route heuristics for deciding `verification_mode` may later need stronger file-pattern or diff-aware classification.
