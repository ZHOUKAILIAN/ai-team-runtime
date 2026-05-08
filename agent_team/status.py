from __future__ import annotations

from pathlib import Path

from .models import WorkflowSummary


def build_status_overview(
    *,
    summary: WorkflowSummary,
    state_root: Path,
    repo_root: Path | None = None,
) -> dict[str, str]:
    project = _project_name(state_root=state_root, repo_root=repo_root)
    role = summary.current_stage or summary.current_state or "Unknown"
    status = _status(summary)
    detail = _status_detail(summary)
    return {
        "project": project,
        "role": role,
        "status": status,
        "detail": detail,
        "text": f"{project} / {role} / {status}: {detail}",
    }


def _project_name(*, state_root: Path, repo_root: Path | None) -> str:
    if repo_root is not None:
        return repo_root.resolve().name
    if state_root.name == ".agent-team":
        return state_root.parent.name
    return state_root.name


def _status(summary: WorkflowSummary) -> str:
    if (
        summary.blocked_reason
        or summary.acceptance_status == "blocked"
        or any(status == "blocked" for status in summary.stage_statuses.values())
    ):
        return "blocked"
    if summary.current_state in {
        "WaitForProductDefinitionApproval",
        "WaitForTechnicalDesignApproval",
        "WaitForHumanDecision",
    }:
        return "waiting"
    if summary.current_state == "Done":
        return "done"
    if summary.acceptance_status in {"recommended_go", "recommended_no_go"}:
        return summary.acceptance_status
    return "in_progress"


def _status_detail(summary: WorkflowSummary) -> str:
    if summary.blocked_reason:
        return summary.blocked_reason
    if summary.current_state == "WaitForProductDefinitionApproval":
        return "Waiting for product-definition approval."
    if summary.current_state == "WaitForTechnicalDesignApproval":
        return "Waiting for technical-design approval."
    if summary.current_state == "WaitForHumanDecision":
        return "Waiting for human Go/No-Go decision."
    if summary.acceptance_status in {"recommended_go", "recommended_no_go"}:
        return f"Acceptance reported {summary.acceptance_status}."
    return f"{summary.current_stage} is active in {summary.current_state}."
