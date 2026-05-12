from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SESSION_INDEX_NAME = "session-index.json"
TERMINAL_WORKFLOW_STATES = {"Done", "NoGo"}


@dataclass(frozen=True, slots=True)
class TaskWorktree:
    path: Path
    branch: str
    base_branch: str
    base_head: str


def session_index_path(project_root: Path) -> Path:
    return project_root.resolve() / ".agent-team" / SESSION_INDEX_NAME


def load_session_index(project_root: Path) -> dict[str, object]:
    path = session_index_path(project_root)
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


def slugify_run_intent(message: str, *, max_length: int = 48) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", message.strip()).strip("-").lower()
    if not slug:
        slug = "task"
    return slug[:max_length].strip("-") or "task"


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


def create_task_worktree(*, project_root: Path, message: str) -> TaskWorktree:
    project_root = project_root.resolve()
    if git(project_root, ["rev-parse", "--is-inside-work-tree"]).returncode != 0:
        raise RuntimeError("run requires a git worktree so it can create an isolated task worktree.")

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    slug = slugify_run_intent(message)
    worktrees_root = project_root / ".worktrees"
    worktrees_root.mkdir(parents=True, exist_ok=True)
    base_name = f"{stamp}-{slug}"
    worktree_path = worktrees_root / base_name
    branch = f"agent-team/{base_name}"
    suffix = 1
    while worktree_path.exists() or git(project_root, ["rev-parse", "--verify", "--quiet", branch]).returncode == 0:
        suffix += 1
        worktree_path = worktrees_root / f"{base_name}-{suffix}"
        branch = f"agent-team/{base_name}-{suffix}"

    base_branch = git_stdout(project_root, ["branch", "--show-current"])
    base_head = git_stdout(project_root, ["rev-parse", "HEAD"])
    result = git(project_root, ["worktree", "add", "-b", branch, str(worktree_path), "HEAD"])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Failed to create task worktree: {detail}")
    return TaskWorktree(
        path=worktree_path.resolve(),
        branch=branch,
        base_branch=base_branch,
        base_head=base_head,
    )
