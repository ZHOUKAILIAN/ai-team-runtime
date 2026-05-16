from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_REF_CANDIDATES = ("origin/test", "origin/main", "test", "main")
DEFAULT_BRANCH_PREFIX = "feature/"
DEFAULT_WORKTREE_ROOT = ".worktrees"
DEFAULT_DATE_FORMAT = "%Y%m%d"
DEFAULT_SLUG_MAX_LENGTH = 40
DEFAULT_NAMING_MODE = "request_summary_with_fallback"

REQUEST_TERM_MAP = (
    ("新增", "add"),
    ("添加", "add"),
    ("修复", "fix"),
    ("更新", "update"),
    ("删除", "remove"),
    ("登录", "login"),
    ("按钮", "button"),
    ("接口", "api"),
    ("订单", "order"),
    ("页面", "page"),
    ("列表", "list"),
    ("验证", "verify"),
)


@dataclass(frozen=True, slots=True)
class WorktreePolicy:
    base_ref_candidates: tuple[str, ...] = DEFAULT_BASE_REF_CANDIDATES
    branch_prefix: str = DEFAULT_BRANCH_PREFIX
    worktree_root: str = DEFAULT_WORKTREE_ROOT
    date_format: str = DEFAULT_DATE_FORMAT
    slug_max_length: int = DEFAULT_SLUG_MAX_LENGTH
    naming_mode: str = DEFAULT_NAMING_MODE
    source: str = "builtin_default"


def worktree_policy_path(state_root: Path) -> Path:
    return state_root.resolve() / "local" / "worktree-policy.json"


def load_worktree_policy(state_root: Path) -> WorktreePolicy:
    path = worktree_policy_path(state_root)
    if not path.exists():
        return WorktreePolicy()

    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid worktree policy JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Worktree policy must be a JSON object: {path}")

    return WorktreePolicy(
        base_ref_candidates=tuple(_string_list(payload.get("base_ref_candidates"), field="base_ref_candidates")),
        branch_prefix=_normalized_branch_prefix(payload.get("branch_prefix")),
        worktree_root=_string_value(
            payload.get("worktree_root"),
            field="worktree_root",
            default=DEFAULT_WORKTREE_ROOT,
        ),
        date_format=_string_value(
            payload.get("date_format"),
            field="date_format",
            default=DEFAULT_DATE_FORMAT,
        ),
        slug_max_length=_int_value(
            payload.get("slug_max_length"),
            field="slug_max_length",
            default=DEFAULT_SLUG_MAX_LENGTH,
        ),
        naming_mode=_string_value(
            payload.get("naming_mode"),
            field="naming_mode",
            default=DEFAULT_NAMING_MODE,
        ),
        source="local_file",
    )


def summarize_request_slug(message: str, *, max_length: int) -> tuple[str, str]:
    parts: list[str] = []
    for source, target in REQUEST_TERM_MAP:
        if source in message and target not in parts:
            parts.append(target)
        if len(parts) >= 4:
            break

    for token in re.findall(r"[A-Za-z0-9]+", message.lower()):
        if token not in parts:
            parts.append(token)
        if len(parts) >= 4:
            break

    if not parts:
        return "task", "fallback_task"

    slug = re.sub(r"[^a-z0-9]+", "-", "-".join(parts)).strip("-")
    trimmed = slug[:max_length].strip("-")
    if not trimmed:
        return "task", "fallback_task"
    return trimmed, "request_summary"


def render_worktree_policy_snapshot(policy: WorktreePolicy) -> str:
    payload = {
        "base_ref_candidates": list(policy.base_ref_candidates),
        "branch_prefix": policy.branch_prefix,
        "worktree_root": policy.worktree_root,
        "date_format": policy.date_format,
        "slug_max_length": policy.slug_max_length,
        "naming_mode": policy.naming_mode,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _string_list(value: object, *, field: str) -> list[str]:
    if value is None:
        return list(DEFAULT_BASE_REF_CANDIDATES)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"worktree policy field `{field}` must be a non-empty list of strings")
    return [item.strip() for item in value]


def _string_value(value: object, *, field: str, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"worktree policy field `{field}` must be a non-empty string")
    return value.strip()


def _int_value(value: object, *, field: str, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"worktree policy field `{field}` must be a positive integer")
    return value


def _normalized_branch_prefix(value: object) -> str:
    prefix = _string_value(value, field="branch_prefix", default=DEFAULT_BRANCH_PREFIX)
    return prefix if prefix.endswith("/") else prefix + "/"
