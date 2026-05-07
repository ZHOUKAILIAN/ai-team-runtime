from __future__ import annotations

from pathlib import Path

from .models import RoleProfile
from .packaged_assets import packaged_text
from .project_structure import resolve_role_context_paths

DEFAULT_ROLE_NAMES = ("Product", "Dev", "QA", "Acceptance")


def load_role_profiles(
    repo_root: Path,
    state_root: Path | None = None,
    role_names: tuple[str, ...] = DEFAULT_ROLE_NAMES,
) -> dict[str, RoleProfile]:
    profiles: dict[str, RoleProfile] = {}

    for role_name in role_names:
        paths = resolve_role_context_paths(repo_root, role_name)
        role_dir = paths.role_dir
        context_path = paths.context_path
        contract_path = paths.guidance_path
        learning_dir = (state_root / "memory" / role_name) if state_root else None
        if paths.source != "packaged":
            base_context_text = _read_text(context_path)
            base_contract_text = _read_text(contract_path)
        else:
            base_context_text = packaged_text("roles", role_name, "context.md")
            base_contract_text = packaged_text("roles", role_name, "contract.md")

        profiles[role_name] = RoleProfile(
            name=role_name,
            role_dir=role_dir,
            context_path=context_path,
            contract_path=contract_path,
            base_context_text=base_context_text,
            base_contract_text=base_contract_text,
            learned_context_text=_read_text(learning_dir / "context_patch.md") if learning_dir else "",
            learned_contract_text=_read_text(learning_dir / "contract_patch.md") if learning_dir else "",
        )

    return profiles


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""

    return path.read_text()
