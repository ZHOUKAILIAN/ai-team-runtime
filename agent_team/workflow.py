from __future__ import annotations


STAGES = (
    "Route",
    "ProductDefinition",
    "ProjectRuntime",
    "TechnicalDesign",
    "Implementation",
    "Verification",
    "GovernanceReview",
    "Acceptance",
    "SessionHandoff",
)

EXECUTABLE_STATES = frozenset(STAGES)

STAGE_SLUGS = {
    "Route": "route",
    "ProductDefinition": "product-definition",
    "ProjectRuntime": "project-runtime",
    "TechnicalDesign": "technical-design",
    "Implementation": "implementation",
    "Verification": "verification",
    "GovernanceReview": "governance-review",
    "Acceptance": "acceptance",
    "SessionHandoff": "session-handoff",
}

STAGE_ARTIFACTS = {
    "Route": "route-packet.json",
    "ProductDefinition": "product-definition-delta.md",
    "ProjectRuntime": "project-landing-delta.md",
    "TechnicalDesign": "technical-design.md",
    "Implementation": "implementation.md",
    "Verification": "verification-report.md",
    "GovernanceReview": "governance-review.md",
    "Acceptance": "acceptance-report.md",
    "SessionHandoff": "session-handoff.md",
}

STAGE_ARTIFACT_KEYS = {
    "Route": "route",
    "ProductDefinition": "product_definition",
    "ProjectRuntime": "project_runtime",
    "TechnicalDesign": "technical_design",
    "Implementation": "implementation",
    "Verification": "verification",
    "GovernanceReview": "governance_review",
    "Acceptance": "acceptance",
    "SessionHandoff": "session_handoff",
}

WAIT_STATES = frozenset(
    {
        "WaitForProductDefinitionApproval",
        "WaitForTechnicalDesignApproval",
        "WaitForHumanDecision",
    }
)

HUMAN_REWORK_TARGETS = frozenset(
    {
        "Route",
        "ProductDefinition",
        "ProjectRuntime",
        "TechnicalDesign",
        "Implementation",
        "Verification",
        "GovernanceReview",
    }
)


def normalize_stage(stage: str) -> str:
    lowered = stage.lower()
    for known in STAGES:
        if known.lower() == lowered:
            return known
    raise ValueError(f"Unknown stage: {stage}")


def stage_slug(stage: str) -> str:
    return STAGE_SLUGS.get(stage, stage.lower())


def artifact_name_for(stage: str) -> str:
    return STAGE_ARTIFACTS.get(stage, f"{stage.lower()}.md")


def artifact_key_for(stage: str) -> str:
    return STAGE_ARTIFACT_KEYS.get(stage, stage.lower())
