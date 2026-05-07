from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import WorkflowSummary
from .state import StateStore
from .status import build_status_overview


def build_panel_snapshot(
    store: StateStore,
    session_id: str,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    session = store.load_session(session_id)
    summary = store.load_workflow_summary(session_id)
    events = store.read_session_events(session_id)
    contract = _read_json_artifact(summary.artifact_paths.get("acceptance_contract", ""))
    review_completion = _read_json_artifact(summary.artifact_paths.get("review_completion", ""))

    required_evidence = list(contract.get("required_evidence", []))
    evidence_provided = list(review_completion.get("evidence_provided", []))
    pending_evidence = [item for item in required_evidence if item not in evidence_provided]

    session_payload = _read_json(session.session_dir / "session.json")
    stage_records = list(session_payload.get("stage_records", []))

    return {
        "overview": build_status_overview(summary=summary, state_root=store.root, repo_root=repo_root),
        "session": {
            "session_id": session.session_id,
            "request": session.request,
            "raw_message": session.raw_message or "",
            "created_at": session.created_at,
            "session_dir": str(session.session_dir),
            "artifact_dir": str(session.artifact_dir),
            "state_root": str(store.root),
        },
        "state": summary.to_dict(),
        "operator": {
            "current_action": _current_action(summary),
            "next_action": _next_action(summary),
            "blocked_reason": summary.blocked_reason,
            "latest_event": events[-1] if events else None,
        },
        "evidence": {
            "required": required_evidence,
            "provided": evidence_provided,
            "pending": pending_evidence,
            "acceptance_criteria": list(contract.get("acceptance_criteria", [])),
            "unresolved_items": list(review_completion.get("unresolved_items", [])),
        },
        "artifacts": _artifact_rows(summary),
        "stages": stage_records,
        "events": events,
    }


def list_panel_sessions(store: StateStore) -> dict[str, list[dict[str, Any]]]:
    if not store.root.exists():
        return {"active": [], "archived": []}

    active_sessions: list[dict[str, Any]] = []
    archived_sessions: list[dict[str, Any]] = []
    for session_id in sorted(store.session_ids(), reverse=True):
        try:
            session = store.load_session(session_id)
        except FileNotFoundError:
            continue
        session_payload = _read_json(session.session_dir / "session.json")
        if not session_payload:
            continue
        try:
            summary = store.load_workflow_summary(session_id)
        except FileNotFoundError:
            summary = WorkflowSummary(
                session_id=session_id,
                runtime_mode="unknown",
                current_state="unknown",
                current_stage="unknown",
            )
        session_row = {
            "session_id": session_id,
            "request": session_payload.get("request", ""),
            "created_at": session_payload.get("created_at", ""),
            "current_state": summary.current_state,
            "current_stage": summary.current_stage,
            "acceptance_status": summary.acceptance_status,
            "blocked_reason": summary.blocked_reason,
            "archived": summary.current_state == "Done",
        }
        if session_row["archived"]:
            archived_sessions.append(session_row)
        else:
            active_sessions.append(session_row)
    return {"active": active_sessions, "archived": archived_sessions}


def _current_action(summary: WorkflowSummary) -> str:
    if summary.blocked_reason:
        return f"{summary.current_stage} is blocked and needs evidence or rework before progress can continue."
    return {
        "Intake": "Intake captured the request. Product should draft the PRD and acceptance criteria next.",
        "ProductDraft": "Product is drafting or has drafted the PRD for CEO approval.",
        "WaitForCEOApproval": "Waiting for CEO approval before Dev starts implementation.",
        "Dev": "Dev should implement the approved PRD and submit the implementation bundle.",
        "QA": "QA should independently verify Dev output and submit evidence-backed findings.",
        "Acceptance": "Acceptance should validate the product outcome against the PRD and evidence contract.",
        "WaitForHumanDecision": "Waiting for the human Go/No-Go decision.",
    }.get(summary.current_state, f"{summary.current_stage} is active.")


def _next_action(summary: WorkflowSummary) -> str:
    if summary.blocked_reason:
        return f"Resolve blocker: {summary.blocked_reason}"
    if summary.current_state in {"Intake", "ProductDraft"}:
        return "Run Product with the current stage contract, then submit Product result."
    if summary.current_state == "WaitForCEOApproval":
        return "Review PRD, then record human decision: go, no-go, or rework."
    if summary.current_state == "Dev":
        return "Run Dev against the approved PRD and submit implementation evidence."
    if summary.current_state == "QA":
        return "Run QA independently and submit QA result with rerun evidence."
    if summary.current_state == "Acceptance":
        return "Run Acceptance and submit recommendation plus required review artifacts."
    if summary.current_state == "WaitForHumanDecision":
        return "Record the final human Go/No-Go decision."
    return "Inspect the latest event and workflow summary before continuing."


def _artifact_rows(summary: WorkflowSummary) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in sorted(summary.artifact_paths):
        path = summary.artifact_paths[name]
        rows.append({"name": name, "path": path, "exists": Path(path).exists()})
    return rows


def _read_json_artifact(path_value: str) -> dict[str, Any]:
    if not path_value:
        return {}
    return _read_json(Path(path_value))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
