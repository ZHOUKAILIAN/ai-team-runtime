from __future__ import annotations

from pathlib import Path
from typing import Mapping


PRODUCT_ARTIFACT_KEYS = frozenset(
    {
        "product",
        "product_requirements",
        "product-requirements",
        "product-requirements.md",
        "prd",
    }
)
ACCEPTANCE_PLAN_ARTIFACT_KEYS = frozenset({"acceptance_plan", "acceptance_plan.md"})
TECHNICAL_PLAN_ARTIFACT_KEYS = frozenset({"technical_plan", "techplan", "technical_plan.md"})
DEV_ARTIFACT_KEYS = frozenset({"dev", "implementation", "implementation.md"})
STAGE_DOCUMENT_ARTIFACT_KEYS = {
    "Product": PRODUCT_ARTIFACT_KEYS | ACCEPTANCE_PLAN_ARTIFACT_KEYS,
    "Dev": (
        PRODUCT_ARTIFACT_KEYS
        | ACCEPTANCE_PLAN_ARTIFACT_KEYS
        | TECHNICAL_PLAN_ARTIFACT_KEYS
        | DEV_ARTIFACT_KEYS
    ),
    "QA": (
        PRODUCT_ARTIFACT_KEYS
        | ACCEPTANCE_PLAN_ARTIFACT_KEYS
        | TECHNICAL_PLAN_ARTIFACT_KEYS
        | DEV_ARTIFACT_KEYS
    ),
    "Acceptance": PRODUCT_ARTIFACT_KEYS | ACCEPTANCE_PLAN_ARTIFACT_KEYS,
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


def stage_allows_technical_plan_context(stage: str) -> bool:
    return stage in {"Dev", "QA"}


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
