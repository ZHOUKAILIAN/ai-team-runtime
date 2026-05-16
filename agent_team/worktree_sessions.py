from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .harness_paths import default_state_root, resolve_state_root
from .worktree_policy import (
    WorktreePolicy,
    load_worktree_policy,
    render_worktree_policy_snapshot,
    summarize_request_slug,
    worktree_policy_path,
)

SESSION_INDEX_NAME = "session-index.json"
TERMINAL_WORKFLOW_STATES = {"Done", "NoGo"}
AGT_SUPPORT_FILES = ("executor-env.json", "skill-preferences.yaml")
AGT_SUPPORT_DIRS = ("local", "memory")


@dataclass(frozen=True, slots=True)
class TaskWorktree:
    path: Path
    branch: str
    base_branch: str
    base_head: str
    base_ref: str
    base_commit: str
    worktree_policy_source: str
    worktree_policy_snapshot_path: Path
    naming_source: str


def session_index_path(project_root: Path) -> Path:
    return default_state_root(repo_root=project_root.resolve()) / SESSION_INDEX_NAME


def _existing_session_index_path(project_root: Path) -> Path:
    return resolve_state_root(repo_root=project_root.resolve()) / SESSION_INDEX_NAME


def load_session_index(project_root: Path) -> dict[str, object]:
    path = _existing_session_index_path(project_root)
    if not path.exists():
        return {"sessions": []}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"sessions": []}
    return payload if isinstance(payload, dict) else {"sessions": []}


def write_session_index(project_root: Path, payload: dict[str, object]) -> None:
    path = session_index_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def upsert_session_index_entry(
    *,
    project_root: Path,
    session_id: str,
    worktree_path: Path,
    state_root: Path,
    branch: str,
    base_branch: str = "",
    base_head: str = "",
    base_ref: str = "",
    base_commit: str = "",
    worktree_policy_source: str = "",
    worktree_policy_snapshot_path: str = "",
    naming_source: str = "",
    request: str = "",
    status: str = "",
    current_state: str = "",
    current_stage: str = "",
) -> None:
    payload = load_session_index(project_root)
    raw_sessions = payload.get("sessions", [])
    sessions = raw_sessions if isinstance(raw_sessions, list) else []
    now = datetime.now().isoformat(timespec="seconds")
    entry = {
        "session_id": session_id,
        "worktree_path": str(worktree_path.resolve()),
        "state_root": str(state_root.resolve()),
        "branch": branch,
        "base_branch": base_branch,
        "base_head": base_head,
        "base_ref": base_ref,
        "base_commit": base_commit,
        "worktree_policy_source": worktree_policy_source,
        "worktree_policy_snapshot_path": worktree_policy_snapshot_path,
        "naming_source": naming_source,
        "request": request,
        "status": status,
        "current_state": current_state,
        "current_stage": current_stage,
        "updated_at": now,
    }
    for index, existing in enumerate(sessions):
        if isinstance(existing, dict) and existing.get("session_id") == session_id:
            created_at = existing.get("created_at") or now
            merged = {**existing, **{key: value for key, value in entry.items() if value != ""}}
            merged["created_at"] = str(created_at)
            merged["updated_at"] = now
            sessions[index] = merged
            break
    else:
        entry["created_at"] = now
        sessions.append(entry)
    payload["sessions"] = sessions
    write_session_index(project_root, payload)


def find_session_index_entry(project_root: Path, session_id: str = "") -> dict[str, object] | None:
    payload = load_session_index(project_root)
    sessions = [item for item in payload.get("sessions", []) if isinstance(item, dict)]
    if session_id:
        for entry in sessions:
            if entry.get("session_id") == session_id:
                return entry
        return None
    for entry in reversed(sessions):
        state = str(entry.get("current_state") or "")
        status = str(entry.get("status") or "")
        if state not in TERMINAL_WORKFLOW_STATES and status not in {"done", "no_go"}:
            return entry
    return sessions[-1] if sessions else None


def git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr=str(exc))


def git_stdout(repo_root: Path, args: list[str]) -> str:
    result = git(repo_root, args)
    return result.stdout.strip() if result.returncode == 0 else ""


def resolve_base_ref(project_root: Path, candidates: tuple[str, ...]) -> tuple[str, str]:
    attempted: list[str] = []
    for candidate in candidates:
        attempted.append(candidate)
        commit = git_stdout(project_root, ["rev-parse", "--verify", f"{candidate}^{{commit}}"])
        if commit:
            return candidate, commit
    tried = ", ".join(attempted) or "<none>"
    raise RuntimeError(f"No configured clean base ref could be resolved. Tried: {tried}")


def copy_agent_team_support_state(
    *,
    source_state_root: Path,
    target_state_root: Path,
    policy: WorktreePolicy,
) -> Path:
    target_state_root.mkdir(parents=True, exist_ok=True)
    for filename in AGT_SUPPORT_FILES:
        source = source_state_root / filename
        if source.exists():
            destination = target_state_root / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source.read_text())

    for directory in AGT_SUPPORT_DIRS:
        source = source_state_root / directory
        if source.is_dir():
            shutil.copytree(source, target_state_root / directory, dirs_exist_ok=True)

    snapshot_path = worktree_policy_path(target_state_root)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(render_worktree_policy_snapshot(policy))
    return snapshot_path


def create_task_worktree(*, project_root: Path, source_state_root: Path, message: str) -> TaskWorktree:
    project_root = project_root.resolve()
    source_state_root = source_state_root.resolve()
    if git(project_root, ["rev-parse", "--is-inside-work-tree"]).returncode != 0:
        raise RuntimeError("run requires a git worktree so it can create an isolated task worktree.")

    policy = load_worktree_policy(source_state_root)
    base_ref, base_commit = resolve_base_ref(project_root, policy.base_ref_candidates)
    stamp = datetime.now().strftime(policy.date_format)
    slug, naming_source = summarize_request_slug(message, max_length=policy.slug_max_length)
    worktrees_root = _resolve_worktrees_root(project_root=project_root, worktree_root=policy.worktree_root)
    worktrees_root.mkdir(parents=True, exist_ok=True)
    base_name = f"{stamp}-{slug}"
    worktree_path = worktrees_root / base_name
    branch = f"{policy.branch_prefix}{base_name}"
    suffix = 1
    while worktree_path.exists() or git(project_root, ["rev-parse", "--verify", "--quiet", branch]).returncode == 0:
        suffix += 1
        worktree_path = worktrees_root / f"{base_name}-{suffix}"
        branch = f"{policy.branch_prefix}{base_name}-{suffix}"

    base_branch = git_stdout(project_root, ["branch", "--show-current"])
    base_head = git_stdout(project_root, ["rev-parse", "HEAD"])
    result = git(project_root, ["worktree", "add", "-b", branch, str(worktree_path), base_ref])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Failed to create task worktree: {detail}")

    target_state_root = default_state_root(repo_root=worktree_path).resolve()
    snapshot_path = copy_agent_team_support_state(
        source_state_root=source_state_root,
        target_state_root=target_state_root,
        policy=policy,
    )
    return TaskWorktree(
        path=worktree_path.resolve(),
        branch=branch,
        base_branch=base_branch,
        base_head=base_head,
        base_ref=base_ref,
        base_commit=base_commit,
        worktree_policy_source=policy.source,
        worktree_policy_snapshot_path=snapshot_path.resolve(),
        naming_source=naming_source,
    )


def _resolve_worktrees_root(*, project_root: Path, worktree_root: str) -> Path:
    candidate = Path(worktree_root)
    return candidate if candidate.is_absolute() else project_root / candidate
