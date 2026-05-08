from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import model_dataclass
from .packaged_assets import packaged_text
from .workflow import STAGE_SLUGS, STAGES


DEFAULT_DOC_MAP = {
    "product_definition": "docs/product-definition",
    "project_runtime": "docs/project-runtime",
    "technical_design": "docs/technical-design",
    "governance": "docs/governance",
}

MODERN_DOC_MAP_KEYS = frozenset(DEFAULT_DOC_MAP)
LEGACY_DOC_MAP_KEYS = frozenset({"requirements", "designs", "workflow_specs", "standards"})

DOC_CANDIDATES = {
    "product_definition": (
        "docs/product-definition",
        "docs/product-definitions",
        "docs/product",
        "product-definition",
    ),
    "project_runtime": (
        "docs/project-runtime",
        "docs/runtime",
        "docs/project",
    ),
    "technical_design": (
        "docs/technical-design",
        "docs/tech-design",
        "docs/designs",
        "docs/design",
        "docs/architecture",
    ),
    "governance": (
        "docs/governance",
        "docs/standards",
        "docs/workflow",
        "docs/workflow-specs",
    ),
}

ROLE_SLUGS = dict(STAGE_SLUGS)
DEPRECATED_ROLE_SLUGS = ("product", "dev", "qa", "techplan", "ops")


@model_dataclass
class RoleContextPaths:
    role_name: str
    role_dir: Path
    context_path: Path
    guidance_path: Path
    source: str


@model_dataclass
class ProjectStructure:
    repo_root: Path
    agent_team_root: Path
    project_root: Path
    doc_map_path: Path
    doc_map: dict[str, str]
    used_default_docs: bool

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["repo_root"] = str(self.repo_root)
        payload["agent_team_root"] = str(self.agent_team_root)
        payload["project_root"] = str(self.project_root)
        payload["doc_map_path"] = str(self.doc_map_path)
        return payload


def detect_project_structure(repo_root: Path) -> ProjectStructure:
    repo_root = repo_root.resolve()
    agent_team_root = repo_root / "agent-team"
    project_root = agent_team_root / "project"
    doc_map_path = project_root / "doc-map.json"
    existing_doc_map = _read_doc_map(doc_map_path)
    if existing_doc_map:
        doc_map, used_default_docs = _modernize_existing_doc_map(existing_doc_map)
    else:
        doc_map = detect_doc_map(repo_root)
        used_default_docs = not doc_map
        if used_default_docs:
            doc_map = dict(DEFAULT_DOC_MAP)

    return ProjectStructure(
        repo_root=repo_root,
        agent_team_root=agent_team_root,
        project_root=project_root,
        doc_map_path=doc_map_path,
        doc_map=doc_map,
        used_default_docs=used_default_docs,
    )


def detect_doc_map(repo_root: Path) -> dict[str, str]:
    repo_root = repo_root.resolve()
    detected: dict[str, str] = {}
    for key, candidates in DOC_CANDIDATES.items():
        for candidate in candidates:
            path = repo_root / candidate
            if path.exists() and path.is_dir():
                detected[key] = candidate
                break
    return detected


def ensure_project_structure(repo_root: Path) -> ProjectStructure:
    structure = detect_project_structure(repo_root)
    structure.project_root.mkdir(parents=True, exist_ok=True)

    _write_doc_map(structure.doc_map_path, structure.doc_map)
    _ensure_text(structure.project_root / "context.md", "# Project Context\n\nDescribe the project-level context here.\n")
    _ensure_text(structure.project_root / "rules.md", "# Project Rules\n\nAdd project-level Agent Team rules here.\n")
    _remove_deprecated_project_roles(structure.project_root / "roles")
    if structure.used_default_docs:
        roles_dir = structure.project_root / "roles"
        roles_dir.mkdir(parents=True, exist_ok=True)
        for role_name in STAGES:
            slug = ROLE_SLUGS[role_name]
            _ensure_text(
                roles_dir / f"{slug}.context.md",
                packaged_text("roles", role_name, "context.md"),
            )
            _ensure_text(
                roles_dir / f"{slug}.contract.md",
                packaged_text("roles", role_name, "contract.md"),
            )
    return structure


def resolve_role_context_paths(repo_root: Path, role_name: str) -> RoleContextPaths:
    repo_root = repo_root.resolve()
    slug = ROLE_SLUGS.get(role_name, role_name.lower())
    agent_team_roles_dir = repo_root / "agent-team" / "project" / "roles"
    agent_team_context_path = agent_team_roles_dir / f"{slug}.context.md"
    if agent_team_context_path.exists():
        return RoleContextPaths(
            role_name=role_name,
            role_dir=agent_team_roles_dir,
            context_path=agent_team_context_path,
            guidance_path=agent_team_roles_dir / f"{slug}.contract.md",
            source="agent-team-project",
        )

    legacy_role_dir = repo_root / role_name
    if legacy_role_dir.exists():
        return RoleContextPaths(
            role_name=role_name,
            role_dir=legacy_role_dir,
            context_path=legacy_role_dir / "context.md",
            guidance_path=legacy_role_dir / "contract.md",
            source="legacy-role-directory",
        )

    packaged_role_dir = repo_root / role_name
    return RoleContextPaths(
        role_name=role_name,
        role_dir=packaged_role_dir,
        context_path=packaged_role_dir / "context.md",
        guidance_path=packaged_role_dir / "contract.md",
        source="packaged",
    )


def _read_doc_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items() if isinstance(value, str)}


def _modernize_existing_doc_map(doc_map: dict[str, str]) -> tuple[dict[str, str], bool]:
    modern_entries = {key: value for key, value in doc_map.items() if key in MODERN_DOC_MAP_KEYS}
    if modern_entries:
        merged = dict(DEFAULT_DOC_MAP)
        merged.update(modern_entries)
        return merged, False
    if set(doc_map).intersection(LEGACY_DOC_MAP_KEYS):
        return dict(DEFAULT_DOC_MAP), True
    return doc_map, False


def _write_doc_map(path: Path, doc_map: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc_map, indent=2, sort_keys=True) + "\n")


def _ensure_text(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _remove_deprecated_project_roles(roles_dir: Path) -> None:
    if not roles_dir.exists():
        return
    for slug in DEPRECATED_ROLE_SLUGS:
        for suffix in ("context", "contract"):
            path = roles_dir / f"{slug}.{suffix}.md"
            if path.exists():
                path.unlink()
