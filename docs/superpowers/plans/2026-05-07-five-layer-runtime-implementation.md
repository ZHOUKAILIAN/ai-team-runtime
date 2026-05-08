# Five-Layer Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old Product / Dev / QA / Acceptance runtime flow with the five-layer Agent Team runtime.

**Architecture:** Introduce a fixed nine-stage workflow: Route, ProductDefinition, ProjectRuntime, TechnicalDesign, Implementation, Verification, GovernanceReview, Acceptance, SessionHandoff. Keep `agent-team run` as the CLI entry while changing stages, artifacts, role assets, gates, and dry-run behavior underneath.

**Tech Stack:** Python 3.13, pytest, existing `StageMachine`, `StagePolicy`, `StateStore`, `RuntimeDriver`, and CLI modules.

---

### Task 1: Centralize Five-Layer Workflow Constants

**Files:**
- Create: `agent_team/workflow.py`
- Modify: `agent_team/state.py`
- Modify: `agent_team/skill_registry.py`
- Modify: `agent_team/project_structure.py`
- Test: `tests/test_state.py`
- Test: `tests/test_skill_registry.py`
- Test: `tests/test_project_structure.py`

- [ ] Define canonical stage order, slugs, artifact names, wait states, and human-gated stages.
- [ ] Replace hardcoded old role/stage lists with the new constants.
- [ ] Keep legacy slug lookup only for reading old sessions.

### Task 2: Replace Stage Policies, Inputs, And Contracts

**Files:**
- Modify: `agent_team/stage_policies.py`
- Modify: `agent_team/stage_contracts.py`
- Modify: `agent_team/stage_inputs.py`
- Modify: `agent_team/execution_context.py`
- Test: `tests/test_stage_policies.py`
- Test: `tests/test_stage_contracts.py`
- Test: `tests/test_execution_context.py`

- [ ] Add policies for all nine stages with layer-specific outputs and evidence names.
- [ ] Remove the Dev technical-plan special case and make TechnicalDesign its own stage.
- [ ] Update artifact input routing so each lower stage reads approved upstream layer artifacts.

### Task 3: Replace Runtime Flow And Dry-Run Artifacts

**Files:**
- Modify: `agent_team/stage_machine.py`
- Modify: `agent_team/runtime_driver.py`
- Modify: `agent_team/stage_payload.py`
- Modify: `agent_team/status.py`
- Test: `tests/test_stage_machine.py`
- Test: `tests/test_runtime_driver.py`
- Test: `tests/test_gatekeeper.py`

- [ ] Implement the fixed five-layer stage transitions and wait states.
- [ ] Preserve human gates for ProductDefinition approval, TechnicalDesign approval, and final Go/No-Go.
- [ ] Update dry-run content, evidence, supplemental artifacts, and prompt writing rules for new artifacts.

### Task 4: Replace CLI Labels And Interactive Routing

**Files:**
- Modify: `agent_team/cli.py`
- Modify: `README.md`
- Test: `tests/test_cli.py`
- Test: `tests/test_cli_judge_stage_result.py`

- [ ] Update progress labels, stage docs, wait-state messages, completed counts, decision menus, rework targets, and skill stage parsing.
- [ ] Keep `agent-team run`, `status`, `review`, `skill`, and `record-human-decision` commands stable.

### Task 5: Replace Packaged Role Assets

**Files:**
- Create/modify: `agent_team/assets/roles/<Stage>/context.md`
- Create/modify: `agent_team/assets/roles/<Stage>/contract.md`
- Delete old packaged role assets if no longer referenced.
- Test: `tests/test_packaged_assets.py`

- [ ] Add role context and contract files for each new stage.
- [ ] Ensure init writes project-level role files for the new stages when default docs are used.

### Task 6: Verify Locally And In test-agent-team

**Files:**
- Runtime repo tests.
- Target repo: `/Users/zhoukailian/Desktop/mySelf/test-agent-team`

- [ ] Run focused tests while changing each layer.
- [ ] Run full pytest.
- [ ] Run `agent-team init --five-layer-classification skip` in `test-agent-team`.
- [ ] Run a dry-run requirement in `test-agent-team` and inspect stage order, artifacts, and status output.
