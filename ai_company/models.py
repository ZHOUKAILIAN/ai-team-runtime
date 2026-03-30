from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Finding:
    source_stage: str
    target_stage: str
    issue: str
    severity: str = "medium"
    lesson: str = ""
    proposed_context_update: str = ""
    proposed_skill_update: str = ""
    evidence: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Finding":
        return cls(
            source_stage=payload.get("source_stage", ""),
            target_stage=payload.get("target_stage", ""),
            issue=payload.get("issue", ""),
            severity=payload.get("severity", "medium"),
            lesson=payload.get("lesson", ""),
            proposed_context_update=payload.get("proposed_context_update", ""),
            proposed_skill_update=payload.get("proposed_skill_update", ""),
            evidence=payload.get("evidence", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RoleProfile:
    name: str
    role_dir: Path
    context_path: Path
    memory_path: Path
    skill_path: Path
    base_context_text: str
    base_memory_text: str
    base_skill_text: str
    learned_context_text: str = ""
    learned_memory_text: str = ""
    learned_skill_text: str = ""

    @property
    def effective_context_text(self) -> str:
        return _join_sections(self.base_context_text, self.learned_context_text)

    @property
    def effective_memory_text(self) -> str:
        return _join_sections(self.base_memory_text, self.learned_memory_text)

    @property
    def effective_skill_text(self) -> str:
        return _join_sections(self.base_skill_text, self.learned_skill_text)


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    request: str
    created_at: str
    session_dir: Path
    artifact_dir: Path
    raw_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "session_id": self.session_id,
            "request": self.request,
            "created_at": self.created_at,
            "session_dir": str(self.session_dir),
            "artifact_dir": str(self.artifact_dir),
        }
        if self.raw_message is not None:
            payload["raw_message"] = self.raw_message
        return payload


@dataclass(slots=True)
class WorkflowSummary:
    session_id: str
    current_state: str
    current_stage: str
    prd_status: str = "pending"
    dev_status: str = "pending"
    qa_status: str = "pending"
    acceptance_status: str = "pending"
    human_decision: str = "pending"
    qa_round: int = 0
    blocked_reason: str = ""
    artifact_paths: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "current_state": self.current_state,
            "current_stage": self.current_stage,
            "prd_status": self.prd_status,
            "dev_status": self.dev_status,
            "qa_status": self.qa_status,
            "acceptance_status": self.acceptance_status,
            "human_decision": self.human_decision,
            "qa_round": self.qa_round,
            "blocked_reason": self.blocked_reason,
            "artifact_paths": dict(self.artifact_paths),
        }


@dataclass(slots=True)
class StageOutput:
    stage: str
    artifact_name: str
    artifact_content: str
    journal: str
    findings: list[Finding] = field(default_factory=list)
    acceptance_status: str | None = None


@dataclass(slots=True)
class StageRecord:
    stage: str
    artifact_name: str
    artifact_path: Path
    journal_path: Path
    findings_path: Path
    acceptance_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "artifact_name": self.artifact_name,
            "artifact_path": str(self.artifact_path),
            "journal_path": str(self.journal_path),
            "findings_path": str(self.findings_path),
            "acceptance_status": self.acceptance_status,
        }


@dataclass(slots=True)
class WorkflowResult:
    session_id: str
    acceptance_status: str
    review_path: Path
    stage_records: list[StageRecord] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def _join_sections(primary: str, secondary: str) -> str:
    parts = [segment.strip() for segment in (primary, secondary) if segment.strip()]
    return "\n\n".join(parts)
