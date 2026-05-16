# Task Worktree Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each new `agent-team run` start from a clean configurable base ref in its own minimal branch/worktree, while keeping repository-owned five-layer docs untouched and copying only the AGT local support state into the new worktree.

**Architecture:** Add one small policy loader for `.agent-team/local/worktree-policy.json`, then route all worktree creation through `agent_team/worktree_sessions.py` so it can resolve clean base refs, generate ASCII branch names, and copy only the allowed `.agent-team/` support files and directories. Keep CLI changes narrow: `run` should consume the richer `TaskWorktree` metadata, persist new session-index fields, and leave `continue` unchanged.

**Tech Stack:** Python 3.13, `pytest`, existing CLI integration tests, `git worktree`, JSON-based local config under `.agent-team/local/`, and the current `StateStore` / workspace metadata helpers.

---

## Planned File Map

- `agent_team/worktree_policy.py`
  - New local-policy model and loader for `.agent-team/local/worktree-policy.json`, plus deterministic request-to-slug summarization and snapshot rendering.
- `agent_team/worktree_sessions.py`
  - Resolve clean base refs, create branches/worktrees from policy, copy AGT support state, and persist richer session-index metadata.
- `agent_team/cli.py`
  - Switch `run` workspace preparation from tuple metadata to full `TaskWorktree` metadata and keep `continue` behavior unchanged.
- `README.md`
  - Document the new task-worktree behavior, the local policy file path, what AGT state is copied, and what runtime history is intentionally excluded.
- `tests/test_worktree_policy.py`
  - New focused unit tests for builtin defaults, invalid local JSON, and deterministic slug generation.
- `tests/test_worktree_sessions.py`
  - New focused tests for clean-base fallback, worktree naming, copied AGT support state, and non-copied runtime history.
- `tests/test_cli.py`
  - Update `run` / `continue` integration coverage for `feature/` branch names, clean base selection, copied support state, and new session-index fields.
- `tests/test_docs.py`
  - Assert README documents the local worktree policy and AGT-state copy rules.

## Implementation Constraints

- Do not call `agent-team init` during task worktree creation.
- Do not generate or rewrite `agent-team/project/`, `docs/product-definition/`, `docs/project-runtime/`, or `docs/governance/` while creating a worktree.
- Do copy `.agent-team/executor-env.json`, `.agent-team/skill-preferences.yaml`, `.agent-team/local/`, and `.agent-team/memory/` into the new worktree when present.
- Do not copy `.agent-team/session-index.json`, `.agent-team/_runtime/`, `.agent-team/sessions/`, or historical session artifacts into the new worktree.
- Preserve existing `continue` semantics: it must reopen the recorded worktree, not create a new one.

### Task 1: Add Local Worktree Policy Loader And Slug Rules

**Files:**
- Create: `agent_team/worktree_policy.py`
- Test: `tests/test_worktree_policy.py`

- [ ] **Step 1: Write the failing unit tests for builtin defaults, local overrides, and slug fallback**

```python
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    preferred = Path("/tmp")
    return preferred if preferred.exists() else Path.cwd()


class WorktreePolicyTests(unittest.TestCase):
    def test_load_worktree_policy_uses_builtin_defaults_when_missing(self) -> None:
        from agent_team.worktree_policy import load_worktree_policy

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir) / ".agent-team"
            policy = load_worktree_policy(state_root)

            self.assertEqual(policy.base_ref_candidates, ("origin/test", "origin/main", "test", "main"))
            self.assertEqual(policy.branch_prefix, "feature/")
            self.assertEqual(policy.worktree_root, ".worktrees")
            self.assertEqual(policy.date_format, "%Y%m%d")
            self.assertEqual(policy.slug_max_length, 40)
            self.assertEqual(policy.naming_mode, "request_summary_with_fallback")
            self.assertEqual(policy.source, "builtin_default")

    def test_load_worktree_policy_reads_local_file(self) -> None:
        from agent_team.worktree_policy import load_worktree_policy, worktree_policy_path

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir) / ".agent-team"
            path = worktree_policy_path(state_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "base_ref_candidates": ["release", "main"],
                        "branch_prefix": "bugfix",
                        "worktree_root": ".sandbox-worktrees",
                        "date_format": "%Y%m%d",
                        "slug_max_length": 24,
                        "naming_mode": "request_summary_with_fallback",
                    }
                )
            )

            policy = load_worktree_policy(state_root)

            self.assertEqual(policy.base_ref_candidates, ("release", "main"))
            self.assertEqual(policy.branch_prefix, "bugfix/")
            self.assertEqual(policy.worktree_root, ".sandbox-worktrees")
            self.assertEqual(policy.slug_max_length, 24)
            self.assertEqual(policy.source, "local_file")

    def test_load_worktree_policy_rejects_invalid_json(self) -> None:
        from agent_team.worktree_policy import load_worktree_policy, worktree_policy_path

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir) / ".agent-team"
            path = worktree_policy_path(state_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not-json")

            with self.assertRaisesRegex(ValueError, "Invalid worktree policy JSON"):
                load_worktree_policy(state_root)

    def test_summarize_request_slug_translates_common_terms_and_falls_back(self) -> None:
        from agent_team.worktree_policy import summarize_request_slug

        slug, source = summarize_request_slug("新增 登录 按钮", max_length=40)
        self.assertEqual(slug, "add-login-button")
        self.assertEqual(source, "request_summary")

        fallback_slug, fallback_source = summarize_request_slug("！！！", max_length=40)
        self.assertEqual(fallback_slug, "task")
        self.assertEqual(fallback_source, "fallback_task")
```

- [ ] **Step 2: Run the new unit tests and confirm they fail before implementation**

Run: `pytest tests/test_worktree_policy.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_team.worktree_policy'`.

- [ ] **Step 3: Implement `agent_team/worktree_policy.py` with defaults, validation, and deterministic summarization**

```python
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
    return state_root / "local" / "worktree-policy.json"


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

    candidates = _string_list(payload.get("base_ref_candidates"), field="base_ref_candidates")
    branch_prefix = _normalized_branch_prefix(payload.get("branch_prefix"))
    worktree_root = _string_value(payload.get("worktree_root"), field="worktree_root", default=DEFAULT_WORKTREE_ROOT)
    date_format = _string_value(payload.get("date_format"), field="date_format", default=DEFAULT_DATE_FORMAT)
    naming_mode = _string_value(payload.get("naming_mode"), field="naming_mode", default=DEFAULT_NAMING_MODE)
    slug_max_length = _int_value(payload.get("slug_max_length"), field="slug_max_length", default=DEFAULT_SLUG_MAX_LENGTH)
    return WorktreePolicy(
        base_ref_candidates=tuple(candidates),
        branch_prefix=branch_prefix,
        worktree_root=worktree_root,
        date_format=date_format,
        slug_max_length=slug_max_length,
        naming_mode=naming_mode,
        source="local_file",
    )


def summarize_request_slug(message: str, *, max_length: int) -> tuple[str, str]:
    parts: list[str] = []
    for source, target in REQUEST_TERM_MAP:
        if source in message and target not in parts:
            parts.append(target)
        if len(parts) == 4:
            break
    for token in re.findall(r"[A-Za-z0-9]+", message.lower()):
        if token not in parts:
            parts.append(token)
        if len(parts) == 4:
            break
    if not parts:
        return "task", "fallback_task"
    slug = re.sub(r"[^a-z0-9]+", "-", "-".join(parts)).strip("-")
    trimmed = slug[:max_length].strip("-")
    return (trimmed or "task", "request_summary" if trimmed else "fallback_task")


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
    default = list(DEFAULT_BASE_REF_CANDIDATES) if field == "base_ref_candidates" else []
    if value is None:
        return default
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
```

- [ ] **Step 4: Re-run the policy tests and make sure they pass**

Run: `pytest tests/test_worktree_policy.py -q`

Expected: PASS with `4 passed`.

- [ ] **Step 5: Commit the policy loader slice**

```bash
git add agent_team/worktree_policy.py tests/test_worktree_policy.py
git commit -m "feat: add local task worktree policy loader"
```

### Task 2: Create Worktrees From Clean Base Refs And Copy Only AGT Support State

**Files:**
- Modify: `agent_team/worktree_sessions.py`
- Test: `tests/test_worktree_sessions.py`

- [ ] **Step 1: Write failing tests for clean-base fallback, copied support state, and excluded runtime history**

```python
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    preferred = Path("/tmp")
    return preferred if preferred.exists() else Path.cwd()


class WorktreeSessionTests(unittest.TestCase):
    def test_create_task_worktree_uses_clean_base_and_copies_support_state(self) -> None:
        from agent_team.harness_paths import default_state_root
        from agent_team.worktree_sessions import create_task_worktree

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
            (repo_root / "README.md").write_text("# main branch\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, check=True, capture_output=True, text=True)

            subprocess.run(["git", "checkout", "-b", "test"], cwd=repo_root, check=True, capture_output=True, text=True)
            (repo_root / "README.md").write_text("# clean test branch\n")
            subprocess.run(["git", "commit", "-am", "test baseline"], cwd=repo_root, check=True, capture_output=True, text=True)

            subprocess.run(["git", "checkout", "-b", "feature/current"], cwd=repo_root, check=True, capture_output=True, text=True)
            (repo_root / "README.md").write_text("# dirty current branch\n")
            subprocess.run(["git", "commit", "-am", "current work"], cwd=repo_root, check=True, capture_output=True, text=True)

            state_root = default_state_root(repo_root=repo_root)
            (state_root / "executor-env.json").parent.mkdir(parents=True, exist_ok=True)
            (state_root / "executor-env.json").write_text('{"inherit":[],"inherit_prefixes":[],"set":{"FOO":"BAR"},"unset":[]}\n')
            (state_root / "skill-preferences.yaml").write_text("initialized: true\n")
            (state_root / "local").mkdir(parents=True, exist_ok=True)
            (state_root / "local" / "verification-private.json").write_text('{"default":{"base_url":"https://example.test"}}\n')
            (state_root / "memory" / "Implementation").mkdir(parents=True, exist_ok=True)
            (state_root / "memory" / "Implementation" / "lessons.md").write_text("remember\n")
            (state_root / "_runtime" / "sessions" / "old").mkdir(parents=True, exist_ok=True)
            (state_root / "_runtime" / "sessions" / "old" / "session.json").write_text("{}\n")
            (state_root / "session-index.json").write_text(json.dumps({"sessions": [{"session_id": "old"}]}))
            (state_root / "local" / "worktree-policy.json").write_text(
                json.dumps(
                    {
                        "base_ref_candidates": ["missing", "test"],
                        "branch_prefix": "feature/",
                        "worktree_root": ".worktrees",
                        "date_format": "%Y%m%d",
                        "slug_max_length": 40,
                        "naming_mode": "request_summary_with_fallback",
                    }
                )
            )

            worktree = create_task_worktree(project_root=repo_root, source_state_root=state_root, message="新增 登录 按钮")

            self.assertEqual(worktree.base_ref, "test")
            self.assertRegex(worktree.branch, r"^feature/\\d{8}-add-login-button$")
            self.assertEqual((worktree.path / "README.md").read_text(), "# clean test branch\n")
            self.assertTrue((worktree.path / ".agent-team" / "executor-env.json").exists())
            self.assertTrue((worktree.path / ".agent-team" / "skill-preferences.yaml").exists())
            self.assertTrue((worktree.path / ".agent-team" / "local" / "verification-private.json").exists())
            self.assertTrue((worktree.path / ".agent-team" / "memory" / "Implementation" / "lessons.md").exists())
            self.assertFalse((worktree.path / ".agent-team" / "_runtime").exists())
            self.assertFalse((worktree.path / ".agent-team" / "session-index.json").exists())

    def test_create_task_worktree_adds_unique_suffix_when_names_collide(self) -> None:
        from agent_team.harness_paths import default_state_root
        from agent_team.worktree_sessions import create_task_worktree

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
        repo_root = Path(temp_dir) / "repo"
        repo_root.mkdir()
        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
        (repo_root / "README.md").write_text("# test repo\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "branch", "-m", "main"], cwd=repo_root, check=True, capture_output=True, text=True)

        state_root = default_state_root(repo_root=repo_root)
        (state_root / "local").mkdir(parents=True, exist_ok=True)
        (state_root / "local" / "worktree-policy.json").write_text(json.dumps({"base_ref_candidates": ["main"]}))

            first = create_task_worktree(project_root=repo_root, source_state_root=state_root, message="fix api")
            second = create_task_worktree(project_root=repo_root, source_state_root=state_root, message="fix api")

            self.assertNotEqual(first.branch, second.branch)
            self.assertTrue(second.branch.endswith("-2"))
            self.assertTrue(second.path.name.endswith("-2"))
```

- [ ] **Step 2: Run the worktree session tests and confirm they fail on the current implementation**

Run: `pytest tests/test_worktree_sessions.py -q`

Expected: FAIL with `TypeError` because `create_task_worktree()` does not accept `source_state_root`, plus assertions showing the current branch prefix and copied-state behavior do not match the new expectations.

- [ ] **Step 3: Extend `worktree_sessions.py` to resolve clean base refs, copy support state, and persist richer metadata**

```python
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .harness_paths import default_state_root
from .worktree_policy import (
    WorktreePolicy,
    load_worktree_policy,
    render_worktree_policy_snapshot,
    summarize_request_slug,
    worktree_policy_path,
)

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


def resolve_base_ref(project_root: Path, candidates: tuple[str, ...]) -> tuple[str, str]:
    attempted: list[str] = []
    for candidate in candidates:
        attempted.append(candidate)
        commit = git_stdout(project_root, ["rev-parse", "--verify", f"{candidate}^{{commit}}"])
        if commit:
            return candidate, commit
    tried = ", ".join(attempted) or "<none>"
    raise RuntimeError(f"No configured clean base ref could be resolved. Tried: {tried}")


def copy_agent_team_support_state(*, source_state_root: Path, target_state_root: Path, policy: WorktreePolicy) -> Path:
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
    policy = load_worktree_policy(source_state_root)
    base_ref, base_commit = resolve_base_ref(project_root, policy.base_ref_candidates)
    stamp = datetime.now().strftime(policy.date_format)
    slug, naming_source = summarize_request_slug(message, max_length=policy.slug_max_length)
    base_name = f"{stamp}-{slug}"
    worktrees_root = project_root / policy.worktree_root
    worktrees_root.mkdir(parents=True, exist_ok=True)
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
```

- [ ] **Step 4: Re-run the focused worktree tests and make sure they pass**

Run: `pytest tests/test_worktree_policy.py tests/test_worktree_sessions.py -q`

Expected: PASS with `6 passed`.

- [ ] **Step 5: Commit the worktree creation slice**

```bash
git add agent_team/worktree_sessions.py tests/test_worktree_sessions.py
git commit -m "feat: create task worktrees from configured clean bases"
```

### Task 3: Wire The New Worktree Metadata Through The CLI And Session Index

**Files:**
- Modify: `agent_team/cli.py`
- Modify: `agent_team/worktree_sessions.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Update the CLI integration test to assert clean-base metadata and copied AGT support state**

```python
def test_run_uses_clean_base_policy_and_continue_reuses_created_worktree(self) -> None:
    from agent_team.cli import main

    with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
        repo_root = Path(temp_dir) / "repo"
        repo_root.mkdir()
        subprocess.run(["git", "init"], cwd=repo_root, capture_output=True, text=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
        (repo_root / "README.md").write_text("# main\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, capture_output=True, text=True, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, capture_output=True, text=True, check=True)

        subprocess.run(["git", "checkout", "-b", "test"], cwd=repo_root, capture_output=True, text=True, check=True)
        (repo_root / "README.md").write_text("# test baseline\n")
        subprocess.run(["git", "commit", "-am", "baseline"], cwd=repo_root, capture_output=True, text=True, check=True)
        subprocess.run(["git", "checkout", "-b", "feature/current"], cwd=repo_root, capture_output=True, text=True, check=True)

        state_root = repo_root / ".agent-team"
        (state_root / "local").mkdir(parents=True, exist_ok=True)
        (state_root / "local" / "worktree-policy.json").write_text(
            json.dumps(
                {
                    "base_ref_candidates": ["test"],
                    "branch_prefix": "feature/",
                    "worktree_root": ".worktrees",
                    "date_format": "%Y%m%d",
                    "slug_max_length": 40,
                    "naming_mode": "request_summary_with_fallback",
                }
            )
        )
        (state_root / "executor-env.json").write_text('{"inherit":[],"inherit_prefixes":[],"set":{"FOO":"BAR"},"unset":[]}\n')
        (state_root / "skill-preferences.yaml").write_text("initialized: true\n")
        (state_root / "memory" / "Implementation").mkdir(parents=True, exist_ok=True)
        (state_root / "memory" / "Implementation" / "lessons.md").write_text("carry over\n")

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "run",
                    "--message",
                    "新增 登录 按钮",
                    "--executor",
                    "dry-run",
                ]
            )

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("branch: feature/", output)
        self.assertIn("add-login-button", output)
        session_id = _session_id_from_stdout(output)

        entry = json.loads((repo_root / ".agent-team" / "session-index.json").read_text())["sessions"][0]
        worktree_path = Path(entry["worktree_path"])
        self.assertEqual(entry["base_ref"], "test")
        self.assertTrue(entry["base_commit"])
        self.assertEqual(entry["worktree_policy_source"], "local_file")
        self.assertEqual(entry["naming_source"], "request_summary")
        self.assertTrue((worktree_path / ".agent-team" / "skill-preferences.yaml").exists())
        self.assertTrue((worktree_path / ".agent-team" / "memory" / "Implementation" / "lessons.md").exists())
        self.assertFalse((worktree_path / ".agent-team" / "_runtime").exists())

        continue_stdout = io.StringIO()
        with patch("sys.stdout", continue_stdout):
            continue_exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "continue",
                    "--executor",
                    "dry-run",
                ]
            )

        self.assertEqual(continue_exit_code, 0)
        self.assertIn(f"session_id: {session_id}", continue_stdout.getvalue())
        self.assertEqual(len(list((repo_root / ".worktrees").iterdir())), 1)
```

- [ ] **Step 2: Run the focused CLI test and confirm it fails before the CLI wiring changes**

Run: `pytest tests/test_cli.py -k "clean_base_policy and continue_reuses_created_worktree" -q`

Expected: FAIL because `branch: agent-team/` is still printed, `base_ref` metadata is missing, and only `executor-env.json` is currently copied into the new worktree.

- [ ] **Step 3: Change CLI workspace preparation to carry full `TaskWorktree` metadata into session-index writes**

```python
from .worktree_sessions import TaskWorktree, create_task_worktree, find_session_index_entry, git_stdout, upsert_session_index_entry


def _prepare_new_run_workspace(args: argparse.Namespace, *, message: str) -> TaskWorktree | None:
    if args.state_root_explicit or args.session_id:
        return None
    source_state_root = default_state_root(repo_root=args.project_root).resolve()
    try:
        worktree = create_task_worktree(
            project_root=args.project_root,
            source_state_root=source_state_root,
            message=message,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    args.repo_root = worktree.path
    args.state_root = default_state_root(repo_root=worktree.path).resolve()
    refresh_workspace_metadata(state_root=args.state_root, repo_root=args.repo_root)
    print(f"worktree_path: {worktree.path}")
    print(f"branch: {worktree.branch}")
    return worktree


def _record_run_index_result(*, args: argparse.Namespace, result, request: str = "", task_worktree: TaskWorktree | None = None) -> None:
    branch = git_stdout(args.repo_root, ["branch", "--show-current"])
    upsert_session_index_entry(
        project_root=args.project_root,
        session_id=result.session_id,
        worktree_path=args.repo_root,
        state_root=args.state_root,
        branch=branch,
        base_branch=task_worktree.base_branch if task_worktree else "",
        base_head=task_worktree.base_head if task_worktree else "",
        base_ref=task_worktree.base_ref if task_worktree else "",
        base_commit=task_worktree.base_commit if task_worktree else "",
        worktree_policy_source=task_worktree.worktree_policy_source if task_worktree else "",
        worktree_policy_snapshot_path=(
            str(task_worktree.worktree_policy_snapshot_path) if task_worktree else ""
        ),
        naming_source=task_worktree.naming_source if task_worktree else "",
        request=request,
        status=result.status,
        current_state=result.current_state,
        current_stage=result.current_stage,
    )
```

```python
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
```

- [ ] **Step 4: Re-run the focused CLI tests and then the full worktree-related subset**

Run: `pytest tests/test_cli.py -k "clean_base_policy or continue_accepts_session_id_positional_alias" -q`

Expected: PASS with the updated branch prefix and session-index assertions.

Run: `pytest tests/test_worktree_policy.py tests/test_worktree_sessions.py tests/test_cli.py -q`

Expected: PASS with the new focused coverage and no regressions in the old `continue` alias test.

- [ ] **Step 5: Commit the CLI wiring slice**

```bash
git add agent_team/cli.py agent_team/worktree_sessions.py tests/test_cli.py
git commit -m "feat: wire task worktree policy through cli"
```

### Task 4: Document The New Local Policy And Copy Rules

**Files:**
- Modify: `README.md`
- Modify: `tests/test_docs.py`

- [ ] **Step 1: Add a failing docs test for the new task worktree policy section**

```python
def test_readme_documents_task_worktree_policy(self) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    readme = (repo_root / "README.md").read_text()

    self.assertIn("Task worktrees", readme)
    self.assertIn(".agent-team/local/worktree-policy.json", readme)
    self.assertIn("feature/<date>-<slug>", readme)
    self.assertIn('["origin/test", "origin/main", "test", "main"]', readme)
    self.assertIn(".agent-team/executor-env.json", readme)
    self.assertIn(".agent-team/skill-preferences.yaml", readme)
    self.assertIn(".agent-team/memory/", readme)
    self.assertIn(".agent-team/session-index.json", readme)
    self.assertIn(".agent-team/_runtime/", readme)
```

- [ ] **Step 2: Run the docs tests and confirm the README is missing the new section**

Run: `pytest tests/test_docs.py -q`

Expected: FAIL in `test_readme_documents_task_worktree_policy`.

- [ ] **Step 3: Add a README section that explains the local policy path, clean base fallback, and copied AGT support state**

````markdown
## Task worktrees

`agent-team run` 默认会从一个干净基线创建新的任务 branch 和新的 `.worktrees/` 工作区，而不是直接从当前 `HEAD` 继续分叉。

本地策略文件：

```text
.agent-team/local/worktree-policy.json
```

默认 clean base ref 候选顺序：

```json
["origin/test", "origin/main", "test", "main"]
```

默认 branch 形如：

```text
feature/<date>-<slug>
```

新 worktree 会复制这些 AGT 本地支持状态：

- `.agent-team/executor-env.json`
- `.agent-team/skill-preferences.yaml`
- `.agent-team/local/`
- `.agent-team/memory/`

新 worktree 不会复制这些运行历史：

- `.agent-team/session-index.json`
- `.agent-team/_runtime/`
- 历史 session 产物
````

- [ ] **Step 4: Re-run the docs tests and make sure they pass**

Run: `pytest tests/test_docs.py -q`

Expected: PASS with the new README assertions.

- [ ] **Step 5: Commit the docs slice**

```bash
git add README.md tests/test_docs.py
git commit -m "docs: document task worktree policy"
```

### Task 5: Final Regression Sweep For The New Worktree Flow

**Files:**
- Modify: `agent_team/worktree_policy.py`
- Modify: `agent_team/worktree_sessions.py`
- Modify: `agent_team/cli.py`
- Modify: `README.md`
- Modify: `tests/test_worktree_policy.py`
- Modify: `tests/test_worktree_sessions.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_docs.py`

- [ ] **Step 1: Run the full focused regression suite for the new worktree feature**

Run: `pytest tests/test_worktree_policy.py tests/test_worktree_sessions.py tests/test_cli.py tests/test_docs.py -q`

Expected: PASS with all new and updated tests green.

- [ ] **Step 2: Run the broader runtime smoke tests that already cover workspace metadata and console grouping**

Run: `pytest tests/test_workspace_metadata.py tests/test_console_data.py tests/test_board.py -q`

Expected: PASS, proving the new worktree naming and state-root behavior did not break existing workspace metadata consumers.

- [ ] **Step 3: If a regression appears, rerun only the failing test file after the targeted fix**

Run one of:

- `pytest tests/test_worktree_policy.py -q`
- `pytest tests/test_worktree_sessions.py -q`
- `pytest tests/test_cli.py -q`
- `pytest tests/test_docs.py -q`

Expected: PASS for the previously failing file before creating the final commit.

- [ ] **Step 4: Create the final implementation commit**

```bash
git add agent_team/worktree_policy.py agent_team/worktree_sessions.py agent_team/cli.py README.md \
  tests/test_worktree_policy.py tests/test_worktree_sessions.py tests/test_cli.py tests/test_docs.py
git commit -m "feat: isolate task runs with configurable clean worktrees"
```

## Self-Review Checklist

- Spec coverage:
  - `L3` local policy path is implemented in Task 1.
  - Clean base ref fallback is implemented and tested in Tasks 1 to 3.
  - New worktree behaves like plain `git worktree` and does not regenerate repo-owned five-layer docs in Task 2.
  - AGT support-state copying and runtime-history exclusion are implemented in Task 2 and verified again in Task 3.
  - README/user-facing documentation is covered in Task 4.
- Placeholder scan:
  - No `TODO` / `TBD` markers remain.
  - Every code-changing task includes concrete code blocks and exact test commands.
- Type consistency:
  - `TaskWorktree` fields, `upsert_session_index_entry()` parameters, and README field names match across all tasks.
