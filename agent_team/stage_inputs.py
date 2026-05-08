from __future__ import annotations

from pathlib import Path
from typing import Mapping


STAGE_DOCUMENT_ARTIFACT_KEYS = {
    "Route": frozenset(),
    "ProductDefinition": frozenset({"route", "route-packet", "route-packet.json"}),
    "ProjectRuntime": frozenset({"route", "product_definition"}),
    "TechnicalDesign": frozenset({"route", "product_definition", "project_runtime"}),
    "Implementation": frozenset({"route", "product_definition", "project_runtime", "technical_design"}),
    "Verification": frozenset(
        {"route", "product_definition", "project_runtime", "technical_design", "implementation"}
    ),
    "GovernanceReview": frozenset(
        {
            "route",
            "product_definition",
            "project_runtime",
            "technical_design",
            "implementation",
            "verification",
        }
    ),
    "Acceptance": frozenset(
        {
            "route",
            "product_definition",
            "project_runtime",
            "technical_design",
            "implementation",
            "verification",
            "governance_review",
        }
    ),
    "SessionHandoff": frozenset(
        {
            "route",
            "product_definition",
            "project_runtime",
            "technical_design",
            "implementation",
            "verification",
            "governance_review",
            "acceptance",
        }
    ),
}


def stage_input_artifact_paths(
    *,
    artifact_paths: Mapping[str, str],
    stage: str,
) -> dict[str, str]:
    allowed = STAGE_DOCUMENT_ARTIFACT_KEYS.get(stage, frozenset())
    return _filter_existing_artifact_paths(artifact_paths=artifact_paths, allowed_keys=allowed)


def stage_context_artifact_paths(
    *,
    artifact_paths: Mapping[str, str],
    stage: str,
) -> dict[str, Path]:
    allowed = STAGE_DOCUMENT_ARTIFACT_KEYS.get(stage, frozenset())
    return {
        name: Path(value)
        for name, value in _filter_existing_artifact_paths(
            artifact_paths=artifact_paths,
            allowed_keys=allowed,
        ).items()
    }


def stage_allows_technical_design_context(stage: str) -> bool:
    return stage in {"Implementation", "Verification", "GovernanceReview", "Acceptance", "SessionHandoff"}


def _filter_existing_artifact_paths(
    *,
    artifact_paths: Mapping[str, str],
    allowed_keys: frozenset[str],
) -> dict[str, str]:
    scoped: dict[str, str] = {}
    seen_paths: set[Path] = set()
    for key, value in artifact_paths.items():
        if key not in allowed_keys:
            continue
        if not value:
            continue
        path = Path(value)
        if not path.exists() or path in seen_paths:
            continue
        seen_paths.add(path)
        scoped[str(key)] = str(value)
    return scoped
