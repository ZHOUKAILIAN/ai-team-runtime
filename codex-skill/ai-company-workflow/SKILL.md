---
name: ai-company-workflow
description: "Use when the user wants a requirement executed through the AI Company single-session state machine, especially with triggers like /company-run, 执行这个需求：..., or Run this requirement through the AI Company workflow: ..."
---

# AI Company Workflow

Use this skill when either of these is true:
- the current workspace contains the AI Company runtime
- the runtime was globally installed under `~/.codex/vendor/ai-team`

If the current workspace is this repository itself, prefer the repo-scoped setup first:

```bash
./scripts/company-init.sh
./scripts/company-run.sh "<the user's original message>"
```

## Trigger Phrases

Treat these as direct workflow execution requests:
- `/company-run <requirement>`
- `执行这个需求：<需求内容>`
- `按 AI Company 流程跑这个需求：<需求内容>`
- `按 AI Company 流程执行：<需求内容>`
- `Run this requirement through the AI Company workflow: <requirement>`
- `Execute this requirement: <requirement>`

## Execution

1. Keep the user's original message intact.
2. Prefer the installed helper script:

```bash
~/.codex/skills/ai-company-workflow/scripts/company-run.sh "<the user's original message>"
```

The helper script only bootstraps a session. It does not complete QA or Acceptance by itself.

3. Direct bootstrap command:

```bash
python3 -m ai_company start-session --message "<the user's original message>"
```

After bootstrap, continue the state machine in the current Codex session to produce the full artifact contract.

4. deterministic runtime output is workflow metadata only, not real QA/Acceptance evidence.
5. Follow the single-session state machine:
`Intake` -> `ProductDraft` -> `WaitForCEOApproval` -> `Dev` -> `QA` -> `Acceptance` -> `WaitForHumanDecision`
6. Enforce artifact contract in `.ai_company_state/artifacts/`:
- `prd.md`
- `implementation.md`
- `qa_report.md`
- `acceptance_report.md`
- `workflow_summary.md`
7. QA must independently rerun verification, missing evidence forces blocked.
8. Acceptance recommends while the human decides.

Continue after session bootstrap:
- inspect and implement in the real repository
- execute real verification against the runnable path when feasible
- collect concrete evidence for QA and Acceptance decisions
- if evidence is missing, report blocked instead of accepted

## If The Runtime Is Missing

Do not pretend the workflow ran. State that neither the current workspace nor `~/.codex/vendor/ai-team` contains the AI Company runtime, and point the user to run:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/ZHOUKAILIAN/AI_Team/main/scripts/install-codex-ai-team.sh)
```
