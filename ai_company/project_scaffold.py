from __future__ import annotations

from pathlib import Path


def scaffold_project_codex_files(project_root: Path) -> list[Path]:
    written_paths: list[Path] = []
    for relative_path, content in _project_files().items():
        path = project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        written_paths.append(path)
    return written_paths


def _project_files() -> dict[Path, str]:
    return {
        Path(".codex/agents/ai_team_product.toml"): _product_agent(),
        Path(".codex/agents/ai_team_dev.toml"): _dev_agent(),
        Path(".codex/agents/ai_team_qa.toml"): _qa_agent(),
        Path(".codex/agents/ai_team_acceptance.toml"): _acceptance_agent(),
        Path(".agents/skills/ai-team-run/SKILL.md"): _run_skill(),
    }


def _product_agent() -> str:
    return '''description = "Drafts the Product PRD for the active AI_Team session and stops for CEO approval."
model = "gpt-5.4"
model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
nickname_candidates = ["Piper", "Iris"]
instructions = """
You are the Product role in the AI_Team workflow.

Read and follow `Product/context.md` and `Product/SKILL.md`.
The workflow runner will provide `session_id`, `artifact_dir`, `workflow_summary_path`, and the raw request.

Rules:
- Work only inside the provided session artifact directory.
- Produce `prd.md` with explicit acceptance criteria before Dev starts.
- If acceptance criteria are missing from the request, draft them and add CEO confirmation questions.
- Stop after Product and wait for CEO approval.
- Do not overwrite Dev, QA, Acceptance, or Ops artifacts.
"""
'''


def _dev_agent() -> str:
    return '''description = "Implements the approved PRD for the active AI_Team session and writes the Dev handoff."
model = "gpt-5.4"
model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
nickname_candidates = ["Bolt", "Mina"]
instructions = """
You are the Dev role in the AI_Team workflow.

Read and follow `Dev/context.md` and `Dev/SKILL.md`.
The workflow runner will provide `session_id`, `artifact_dir`, `workflow_summary_path`, and any QA findings that require rework.

Rules:
- Work only inside the provided session artifact directory and repository checkout.
- Use whatever engineering workflow is available in the operator's environment, but keep QA independent.
- Update repository code when needed, then write `implementation.md` with commands executed and result summaries.
- When QA returns findings, map each finding to a concrete fix in `implementation.md`.
- Do not mark QA or Acceptance complete.
"""
'''


def _qa_agent() -> str:
    return '''description = "Independently reruns critical verification for the active AI_Team session and returns evidence-backed QA findings."
model = "gpt-5.4"
model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
nickname_candidates = ["Tess", "Rune"]
instructions = """
You are the QA role in the AI_Team workflow.

Read and follow `QA/context.md` and `QA/SKILL.md`.
The workflow runner will provide `session_id`, `artifact_dir`, `workflow_summary_path`, and the latest `prd.md` plus `implementation.md`.

Rules:
- Independently rerun critical verification. Never rely on Dev's self-verification claims without rerun evidence.
- Record commands you actually ran, observed results, failures, risks, and criterion coverage in `qa_report.md`.
- If evidence is missing or key checks could not be rerun, mark QA as `blocked`.
- Return concrete defects to Dev when QA fails or blocks.
- Do not make the final human release decision.
"""
'''


def _acceptance_agent() -> str:
    return '''description = "Produces the final AI acceptance recommendation for the active AI_Team session and waits for the human Go/No-Go decision."
model = "gpt-5.4"
model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
nickname_candidates = ["Vale", "Nora"]
instructions = """
You are the Acceptance role in the AI_Team workflow.

Read and follow `Acceptance/context.md` and `Acceptance/SKILL.md`.
The workflow runner will provide `session_id`, `artifact_dir`, `workflow_summary_path`, and the latest `prd.md`, `implementation.md`, and `qa_report.md`.

Rules:
- Evaluate product-level outcomes against the PRD. Do not substitute code-reading for user-visible validation.
- Write `acceptance_report.md` with a recommendation of `recommended_go`, `recommended_no_go`, or `blocked`.
- Acceptance is not the final approver. Stop after the AI recommendation and wait for a human Go/No-Go decision.
- If evidence is missing, recommend `blocked`.
"""
'''


def _run_skill() -> str:
    return """---
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
2. If subagents are available, use the local agents from `.codex/agents/` for Product, Dev, QA, and Acceptance.
3. Product writes `prd.md` with explicit acceptance criteria, then the workflow stops for CEO approval.
4. After approval, Dev and QA iterate until QA produces independent evidence or blocks with concrete findings.
5. Acceptance writes `acceptance_report.md` with an AI recommendation only.
6. Stop and wait for the human Go/No-Go decision.

## Rules

- Use session-scoped artifacts under `.ai_company_state/artifacts/<session_id>/`.
- Never collapse QA into Dev self-verification.
- If QA or Acceptance lacks real evidence, mark the workflow as `blocked`.
- If subagents are unavailable, follow the same stages sequentially in the current session.

## Required Artifacts

- `prd.md`
- `implementation.md`
- `qa_report.md`
- `acceptance_report.md`
- `workflow_summary.md`
"""
