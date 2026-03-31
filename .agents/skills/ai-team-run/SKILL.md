---
name: ai-team-run
description: Use when the user wants to run a requirement through the AI_Team single-session workflow in this repository.
---

# AI_Team Run

Use this skill to bootstrap and execute the AI_Team workflow in the current repository.

Best practice: invoke this skill only when Codex is opened at the target project's root directory.

## Bootstrap

Keep the user's original message intact and run:

```bash
./scripts/company-run.sh "<the user's original message>"
```

This bootstraps a session and prints:
- `session_id`
- `artifact_dir`
- `summary_path`

## Workflow

1. Read the generated `workflow_summary.md` and the session artifact directory.
2. If subagents are available, use the project-scoped agents from `.codex/agents/` for Product, Dev, QA, and Acceptance.
3. Product writes `prd.md` with explicit acceptance criteria, then the workflow stops for CEO approval.
4. After approval, Dev and QA iterate until QA produces independent evidence or blocks with concrete findings.
5. Acceptance writes `acceptance_report.md` with an AI recommendation only.
6. Stop and wait for the human Go/No-Go decision.

## Rules

- Use session-scoped artifacts under `.ai_company_state/artifacts/<session_id>/`.
- Never collapse QA into Dev's TDD.
- If QA or Acceptance lacks real evidence, mark the workflow as `blocked`.
- If subagents are unavailable, follow the same stages sequentially in the current session.

## Required Artifacts

- `prd.md`
- `implementation.md`
- `qa_report.md`
- `acceptance_report.md`
- `workflow_summary.md`
