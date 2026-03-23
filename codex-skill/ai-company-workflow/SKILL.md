---
name: ai-company-workflow
description: "Use when the user wants a requirement executed through the AI Company Product -> Dev -> QA -> Acceptance loop, especially with triggers like /company-run, 执行这个需求：..., or Run this requirement through the AI Company workflow: ..."
---

# AI Company Workflow

Use this skill when either of these is true:
- the current workspace contains the AI Company runtime
- the runtime was globally installed under `~/.codex/vendor/ai-team`

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
2. Prefer the installed helper script for deterministic execution:

```bash
~/.codex/skills/ai-company-workflow/scripts/company-run.sh "<the user's original message>"
```

3. Summarize:
- `session_id`
- `acceptance_status`
- `review.md` path
- downstream findings
- learned memory/context/skill updates, if any

## If The Runtime Is Missing

Do not pretend the workflow ran. State that neither the current workspace nor `~/.codex/vendor/ai-team` contains the AI Company runtime, and point the user to run:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/ZHOUKAILIAN/AI_Team/main/scripts/install-codex-ai-team.sh)
```
