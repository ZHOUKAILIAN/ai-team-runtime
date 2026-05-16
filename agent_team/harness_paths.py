from __future__ import annotations

import os
from pathlib import Path

STATE_ROOT_NAME = ".agt"
LEGACY_STATE_ROOT_NAME = ".agent-team"


def _default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


def default_state_root(*, repo_root: Path, codex_home: Path | None = None) -> Path:
    del codex_home
    return repo_root.resolve() / STATE_ROOT_NAME


def legacy_state_root(*, repo_root: Path) -> Path:
    return repo_root.resolve() / LEGACY_STATE_ROOT_NAME


def resolve_state_root(*, repo_root: Path) -> Path:
    preferred = default_state_root(repo_root=repo_root)
    legacy = legacy_state_root(repo_root=repo_root)
    if preferred.exists() or not legacy.exists():
        return preferred
    return legacy
