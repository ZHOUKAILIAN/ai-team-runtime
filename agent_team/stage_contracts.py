from __future__ import annotations

import hashlib
from pathlib import Path

from .memory_layers import MemoryRetrievalResult, retrieve_role_memory
from .models import StageContract
from .roles import load_role_profiles
from .state import StateStore
from .stage_inputs import stage_input_artifact_paths
from .stage_policies import default_policy_registry, dev_technical_plan_policy

COMMON_FORBIDDEN_ACTIONS = [
    "must_not_change_stage_order",
    "must_not_skip_required_artifacts",
    "must_not_claim_workflow_done",
]


def _compose_role_context(role, retrieved_memory: MemoryRetrievalResult | None = None) -> str:
    if role is None:
        return ""

    sections: list[str] = []
    if role.effective_context_text.strip():
        sections.append("# Role Context\n\n" + role.effective_context_text.strip())
    if role.effective_contract_text.strip():
        sections.append("# Role Contract\n\n" + role.effective_contract_text.strip())
    if retrieved_memory is not None and retrieved_memory.matches:
        sections.append("# Relevant Memory (CLI Keyword Retrieval)\n\n" + retrieved_memory.to_markdown())
    return "\n\n".join(sections)


def build_stage_contract(
    *,
    repo_root: Path,
    state_store: StateStore,
    session_id: str,
    stage: str,
) -> StageContract:
    session = state_store.load_session(session_id)
    summary = state_store.load_workflow_summary(session_id)
    roles = load_role_profiles(repo_root=repo_root, state_root=state_store.root)
    role = roles.get(stage)
    registry = default_policy_registry()
    policy = _policy_for_stage_summary(stage=stage, summary=summary, registry=registry)
    retrieved_memory = retrieve_role_memory(
        state_root=state_store.root,
        role_name=stage,
        query=session.request,
        max_results=8,
    )

    input_artifacts = stage_input_artifact_paths(
        artifact_paths=summary.artifact_paths,
        stage=stage,
    )
    required_outputs = list(policy.required_outputs)

    contract_id = _build_contract_id(
        session_id=session_id,
        stage=stage,
        summary=summary,
        required_outputs=required_outputs,
        evidence_requirements=policy.evidence_requirements,
    )

    return StageContract(
        session_id=session_id,
        stage=stage,
        contract_id=contract_id,
        goal=policy.goal,
        input_artifacts=input_artifacts,
        required_outputs=list(policy.required_outputs),
        forbidden_actions=list(COMMON_FORBIDDEN_ACTIONS),
        evidence_requirements=policy.evidence_requirements,
        evidence_specs=list(policy.evidence_specs),
        role_context=_compose_role_context(role, retrieved_memory),
    )


def _policy_for_stage_summary(stage: str, summary, registry):
    if stage == "Dev" and _dev_should_write_technical_plan(summary):
        return dev_technical_plan_policy()
    return registry.get(stage)


def _dev_should_write_technical_plan(summary) -> bool:
    if summary.current_state != "Dev":
        return False
    if summary.dev_status in {"planning", "pending"}:
        return True
    return not bool(summary.artifact_paths.get("technical_plan"))


def _build_contract_id(
    *,
    session_id: str,
    stage: str,
    summary,
    required_outputs: list[str],
    evidence_requirements: list[str],
) -> str:
    payload = "|".join(
        [
            session_id,
            stage,
            summary.current_state,
            summary.current_stage,
            summary.prd_status,
            summary.dev_status,
            summary.qa_status,
            summary.acceptance_status,
            summary.human_decision,
            str(summary.qa_round),
            ",".join(required_outputs),
            ",".join(evidence_requirements),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
