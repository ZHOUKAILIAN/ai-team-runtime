from __future__ import annotations

import json
from dataclasses import replace

from .models import StageResultEnvelope, WorkflowSummary
from .workflow import HUMAN_REWORK_TARGETS, WAIT_STATES, next_required_stage, ordered_required_stages


INTERACTIVE_RUNTIME_MODES = {"runtime_driver_interactive"}


class StageTransitionError(ValueError):
    pass


class StageMachine:
    def advance(self, *, summary: WorkflowSummary, stage_result: StageResultEnvelope) -> WorkflowSummary:
        if summary.session_id != stage_result.session_id:
            raise StageTransitionError("Stage result session_id does not match workflow summary.")
        if summary.current_state in WAIT_STATES:
            raise StageTransitionError(
                f"Cannot advance from {summary.current_state} without an explicit human decision."
            )
        if stage_result.status == "blocked":
            return _set_stage_status(
                summary,
                stage_result.stage,
                "blocked",
                current_state="Blocked",
                current_stage=stage_result.stage,
                blocked_reason=stage_result.summary or stage_result.blocked_reason or "Stage result is blocked.",
            )

        if stage_result.stage == "Route":
            required_stages, stage_decisions, verification_mode = _parse_route_packet(stage_result)
            next_stage = next_required_stage(required_stages=required_stages, after_stage="Route")
            updated = _set_stage_status(
                summary,
                "Route",
                "completed",
                current_state=next_stage or "Done",
                current_stage=next_stage or "Route",
                route_required_stages=required_stages,
                route_stage_decisions=stage_decisions,
                verification_mode=verification_mode,
            )
            for stage_name, item in stage_decisions.items():
                if item.get("decision") == "skipped":
                    updated = _set_stage_status(updated, stage_name, "skipped")
            return updated

        if stage_result.stage == "ProductDefinition":
            outcome = stage_result.product_definition_outcome or "l1_delta_pending_approval"
            if outcome == "no_l1_delta":
                next_stage = next_required_stage(
                    required_stages=summary.route_required_stages,
                    after_stage="ProductDefinition",
                )
                return _set_stage_status(
                    summary,
                    "ProductDefinition",
                    "skipped",
                    current_state=next_stage or "Done",
                    current_stage=next_stage or "ProductDefinition",
                    product_definition_outcome=outcome,
                )
            return _set_stage_status(
                summary,
                "ProductDefinition",
                "drafted",
                current_state="WaitForProductDefinitionApproval",
                current_stage="ProductDefinition",
                human_decision="pending",
                product_definition_outcome=outcome,
            )

        if stage_result.stage == "ProjectRuntime":
            return _set_stage_status(
                summary,
                "ProjectRuntime",
                "completed",
                current_state="TechnicalDesign",
                current_stage="TechnicalDesign",
            )

        if stage_result.stage == "TechnicalDesign":
            return _set_stage_status(
                summary,
                "TechnicalDesign",
                "drafted",
                current_state="WaitForTechnicalDesignApproval",
                current_stage="TechnicalDesign",
                human_decision="pending",
            )

        if stage_result.stage == "Implementation":
            return _set_stage_status(
                summary,
                "Implementation",
                "completed",
                current_state="Verification",
                current_stage="Verification",
            )

        if stage_result.stage == "Verification":
            next_verification_round = summary.verification_round + 1
            if stage_result.status == "failed" or stage_result.findings:
                return _set_stage_status(
                    summary,
                    "Verification",
                    "failed",
                    current_state="Implementation",
                    current_stage="Implementation",
                    verification_round=next_verification_round,
                )
            return _set_stage_status(
                summary,
                "Verification",
                "passed",
                current_state="GovernanceReview",
                current_stage="GovernanceReview",
                verification_round=next_verification_round,
            )

        if stage_result.stage == "GovernanceReview":
            if stage_result.status == "failed" or stage_result.findings:
                return _set_stage_status(
                    summary,
                    "GovernanceReview",
                    "blocked",
                    current_state="Blocked",
                    current_stage="GovernanceReview",
                    blocked_reason=stage_result.summary or "Governance review found blocking issues.",
                )
            return _set_stage_status(
                summary,
                "GovernanceReview",
                "passed",
                current_state="Acceptance",
                current_stage="Acceptance",
            )

        if stage_result.stage == "Acceptance":
            acceptance_status = stage_result.acceptance_status or (
                "blocked" if stage_result.findings else "recommended_go"
            )
            if acceptance_status == "blocked":
                return _set_stage_status(
                    summary,
                    "Acceptance",
                    "blocked",
                    current_state="Blocked",
                    current_stage="Acceptance",
                    acceptance_status=acceptance_status,
                    blocked_reason=stage_result.summary or "Acceptance result is blocked.",
                )
            return _set_stage_status(
                summary,
                "Acceptance",
                acceptance_status,
                current_state="SessionHandoff",
                current_stage="SessionHandoff",
                acceptance_status=acceptance_status,
            )

        if stage_result.stage == "SessionHandoff":
            return _set_stage_status(
                summary,
                "SessionHandoff",
                "completed",
                current_state="WaitForHumanDecision",
                current_stage="SessionHandoff",
                human_decision="pending",
            )

        raise StageTransitionError(f"Unsupported stage result: {stage_result.stage}")

    def apply_human_decision(
        self,
        *,
        summary: WorkflowSummary,
        decision: str,
        target_stage: str | None = None,
    ) -> WorkflowSummary:
        normalized = decision.strip().lower()
        if normalized not in {"go", "no-go", "rework"}:
            raise StageTransitionError(f"Unsupported human decision: {decision}")

        if summary.current_state == "WaitForProductDefinitionApproval":
            if normalized == "go":
                return _set_stage_status(
                    summary,
                    "ProductDefinition",
                    "approved",
                    current_state="ProjectRuntime",
                    current_stage="ProjectRuntime",
                    human_decision=normalized,
                )
            if normalized == "rework":
                return _set_stage_status(
                    summary,
                    "ProductDefinition",
                    "rework_requested",
                    current_state="ProductDefinition",
                    current_stage="ProductDefinition",
                    human_decision=normalized,
                )
            return replace(
                summary,
                current_state="Done",
                current_stage="ProductDefinition",
                human_decision=normalized,
            )

        if summary.current_state == "WaitForTechnicalDesignApproval":
            if normalized == "go":
                return _set_stage_status(
                    summary,
                    "TechnicalDesign",
                    "approved",
                    current_state="Implementation",
                    current_stage="Implementation",
                    human_decision=normalized,
                )
            if normalized == "rework":
                return _set_stage_status(
                    summary,
                    "TechnicalDesign",
                    "rework_requested",
                    current_state="TechnicalDesign",
                    current_stage="TechnicalDesign",
                    human_decision=normalized,
                )
            return replace(
                summary,
                current_state="Done",
                current_stage="TechnicalDesign",
                human_decision=normalized,
            )

        if summary.current_state == "WaitForHumanDecision":
            if normalized in {"go", "no-go"}:
                return replace(
                    summary,
                    current_state="Done",
                    current_stage="SessionHandoff",
                    human_decision=normalized,
                )
            target = target_stage or ""
            if target not in HUMAN_REWORK_TARGETS:
                raise StageTransitionError(
                    "Rework decisions require a five-layer target stage before SessionHandoff."
                )
            return _set_stage_status(
                summary,
                target,
                "rework_requested",
                current_state=target,
                current_stage=target,
                human_decision=normalized,
            )

        raise StageTransitionError(
            f"Human decisions are only valid from wait states, not {summary.current_state}."
        )


def _is_interactive_runtime(summary: WorkflowSummary) -> bool:
    return summary.runtime_mode in INTERACTIVE_RUNTIME_MODES


def _parse_route_packet(stage_result: StageResultEnvelope) -> tuple[list[str], dict[str, dict[str, str]], str]:
    payload = json.loads(stage_result.artifact_content)
    required_stages = ordered_required_stages(list(payload.get("required_stages", [])))
    stage_decisions = {
        str(name): {str(key): str(value) for key, value in dict(item).items()}
        for name, item in dict(payload.get("stage_decisions", {})).items()
    }
    verification_mode = str(payload.get("verification_mode", ""))
    return required_stages, stage_decisions, verification_mode


def _set_stage_status(summary: WorkflowSummary, stage: str, status: str, **changes: object) -> WorkflowSummary:
    stage_statuses = dict(summary.stage_statuses)
    stage_statuses[stage] = status
    return replace(summary, stage_statuses=stage_statuses, **changes)
