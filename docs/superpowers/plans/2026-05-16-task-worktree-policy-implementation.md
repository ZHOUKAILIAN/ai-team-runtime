# 任务级 Worktree 策略实施计划

> **给执行型 agent：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步执行本计划。步骤使用复选框语法（`- [ ]`）跟踪。

**目标：** 让每次新的 `agent-team run` 都从一个可配置的干净 base ref 拉出独立的最小分支和 worktree，同时不碰仓库内的五层正式文档，只把 AGT 的本地支持状态复制到新 worktree。

**架构：** 先增加一个很小的本地策略加载器，读取 `.agt/local/worktree-policy.json`；然后把 worktree 创建逻辑统一收口到 `agent_team/worktree_sessions.py`，负责解析 clean base ref、生成 ASCII 分支名、复制允许继承的 `.agt/` 支持文件和目录。CLI 层只做窄改动：`run` 使用更完整的 `TaskWorktree` 元数据写入 session index，`continue` 语义保持不变。

**技术栈：** Python 3.13、`pytest`、现有 CLI 集成测试、`git worktree`、放在 `.agt/local/` 下的 JSON 本地配置，以及当前的 `StateStore` / workspace metadata 辅助函数。

---

## 命名迁移前提

这份计划默认采用新的目录命名基线：

- `agt-control/`
  - 仓库内共享、正式、可提交的 Agent Team 控制面。
- `.agt/`
  - 本地隐藏的运行态、私有配置、session 状态、memory、runtime trace。

实现时不能一次性只改写新路径、不处理旧路径。必须保留一个兼容期：

- 读取时兼容旧的 `agent-team/` 和 `.agent-team/`
- 新写入优先落到 `agt-control/` 和 `.agt/`
- 在 worktree 方案真正启用前，先完成根目录命名迁移的最小兼容层

---

## 计划文件映射

- `agent_team/harness_paths.py`
  - 把默认本地状态根从 `.agent-team` 切到 `.agt`，并作为兼容迁移入口。
- `agent_team/project_structure.py`
  - 把共享控制面根从 `agent-team/` 切到 `agt-control/`，并兼容探测旧目录。
- `agent_team/worktree_policy.py`
  - 新增本地策略模型与加载器，负责读取 `.agt/local/worktree-policy.json`，并提供确定性的需求摘要 slug 和策略快照输出。
- `agent_team/worktree_sessions.py`
  - 负责解析 clean base ref、按策略创建 branch/worktree、复制 AGT 支持状态，并写入更完整的 session-index 元数据。
- `agent_team/cli.py`
  - 把 `run` 的工作区准备逻辑从“只返回几个字符串”改成“返回完整 `TaskWorktree` 元数据”，`continue` 行为保持不变。
- `README.md`
  - 记录新的 task-worktree 行为、本地策略文件路径、哪些 AGT 状态会复制、哪些 runtime 历史不会复制。
- `tests/test_worktree_policy.py`
  - 新增聚焦单测，覆盖内建默认值、非法本地 JSON、确定性 slug 生成。
- `tests/test_worktree_sessions.py`
  - 新增聚焦测试，覆盖 clean-base fallback、worktree 命名、复制的 AGT 支持状态、以及不会复制的 runtime 历史。
- `tests/test_cli.py`
  - 更新 `run` / `continue` 集成覆盖，校验 `feature/` 分支命名、clean base 选择、复制的支持状态、以及新的 session-index 字段。
- `tests/test_docs.py`
  - 断言 README 已记录本地 worktree 策略和 AGT 状态复制规则。
- `tests/test_harness_paths.py`
  - 校验默认 state root 已切换为 `.agt`，并覆盖兼容场景。
- `tests/test_project_structure.py`
  - 校验共享控制面根已切到 `agt-control/`，同时仍能识别旧的 `agent-team/`。

## 实施约束

- 在创建 task worktree 时，不要调用 `agent-team init`。
- 不要把 `agt-control/` 与 `.agt/` 的命名迁移省略掉，只实现 worktree 逻辑。
- 在迁移完成前，必须兼容旧的 `agent-team/` 与 `.agent-team/` 读取。
- 在创建 worktree 时，不要生成或改写 `agt-control/project/`、`docs/product-definition/`、`docs/project-runtime/`、`docs/governance/` 这类仓库正式文档。
- 当源工作区中存在这些内容时，要复制 `.agt/executor-env.json`、`.agt/skill-preferences.yaml`、`.agt/local/`、`.agt/memory/` 到新 worktree。
- 不要把 `.agt/session-index.json`、`.agt/_runtime/`、`.agt/sessions/`、或历史 session 产物复制到新 worktree。
- 必须保持现有 `continue` 语义：它只能重新打开已记录的 worktree，不能新建 worktree。

### 任务 0：建立新旧目录命名的兼容迁移层

**文件：**
- 修改：`agent_team/harness_paths.py`
- 修改：`agent_team/project_structure.py`
- 测试：`tests/test_harness_paths.py`
- 测试：`tests/test_project_structure.py`

- [ ] **步骤 1：先写失败测试，明确新的默认根目录和旧目录兼容要求**

```python
def test_default_state_root_prefers_dot_agt(self) -> None:
    from agent_team.harness_paths import default_state_root

    repo_root = Path("/tmp/example-repo")
    self.assertEqual(default_state_root(repo_root=repo_root), repo_root.resolve() / ".agt")


def test_detect_project_structure_prefers_agt_control_root(self) -> None:
    repo_root = Path(temp_dir) / "repo"
    (repo_root / "agt-control" / "project").mkdir(parents=True)
    structure = detect_project_structure(repo_root)
    self.assertEqual(structure.agent_team_root, repo_root / "agt-control")


def test_detect_project_structure_falls_back_to_legacy_agent_team_root(self) -> None:
    repo_root = Path(temp_dir) / "repo"
    (repo_root / "agent-team" / "project").mkdir(parents=True)
    structure = detect_project_structure(repo_root)
    self.assertEqual(structure.agent_team_root, repo_root / "agent-team")
```

- [ ] **步骤 2：运行兼容迁移测试，确认在实现前先失败**

运行：`pytest tests/test_harness_paths.py tests/test_project_structure.py -q`

预期：FAIL，暴露当前默认根仍然是 `.agent-team`，且共享控制面仍然只认 `agent-team/`。

- [ ] **步骤 3：实现最小兼容层，写入新路径、读取兼容旧路径**

```python
def default_state_root(*, repo_root: Path, codex_home: Path | None = None) -> Path:
    del codex_home
    return repo_root.resolve() / ".agt"
```

```python
def detect_project_structure(repo_root: Path) -> ProjectStructure:
    repo_root = repo_root.resolve()
    preferred_root = repo_root / "agt-control"
    legacy_root = repo_root / "agent-team"
    agent_team_root = preferred_root if preferred_root.exists() or not legacy_root.exists() else legacy_root
    project_root = agent_team_root / "project"
    doc_map_path = project_root / "doc-map.json"
    ...
```

- [ ] **步骤 4：重新运行兼容迁移测试，确认通过**

运行：`pytest tests/test_harness_paths.py tests/test_project_structure.py -q`

预期：PASS，且新的默认目录基线已经固定为 `agt-control/` 与 `.agt/`。

- [ ] **步骤 5：提交这一小段兼容迁移**

```bash
git add agent_team/harness_paths.py agent_team/project_structure.py tests/test_harness_paths.py tests/test_project_structure.py
git commit -m "refactor: rename agent team control and state roots"
```

### 任务 1：增加本地 Worktree 策略加载器与 Slug 规则

**文件：**
- 新建：`agent_team/worktree_policy.py`
- 测试：`tests/test_worktree_policy.py`

- [ ] **步骤 1：先写失败测试，覆盖内建默认值、本地覆盖和 slug fallback**

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
            state_root = Path(temp_dir) / ".agt"
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
            state_root = Path(temp_dir) / ".agt"
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
            state_root = Path(temp_dir) / ".agt"
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

- [ ] **步骤 2：运行新单测，确认在实现前先失败**

运行：`pytest tests/test_worktree_policy.py -q`

预期：FAIL，并出现 `ModuleNotFoundError: No module named 'agent_team.worktree_policy'`。

- [ ] **步骤 3：实现 `agent_team/worktree_policy.py`，补齐默认值、校验和确定性摘要**

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

- [ ] **步骤 4：重新运行策略测试，确认通过**

运行：`pytest tests/test_worktree_policy.py -q`

预期：PASS，并显示 `4 passed`。

- [ ] **步骤 5：提交这一小段实现**

```bash
git add agent_team/worktree_policy.py tests/test_worktree_policy.py
git commit -m "feat: add local task worktree policy loader"
```

### 任务 2：从 Clean Base Ref 创建 Worktree，并且只复制 AGT 支持状态

**文件：**
- 修改：`agent_team/worktree_sessions.py`
- 测试：`tests/test_worktree_sessions.py`

- [ ] **步骤 1：先写失败测试，覆盖 clean-base fallback、支持状态复制、以及 runtime 历史排除**

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
            self.assertRegex(worktree.branch, r"^feature/\d{8}-add-login-button$")
            self.assertEqual((worktree.path / "README.md").read_text(), "# clean test branch\n")
            self.assertTrue((worktree.path / ".agt" / "executor-env.json").exists())
            self.assertTrue((worktree.path / ".agt" / "skill-preferences.yaml").exists())
            self.assertTrue((worktree.path / ".agt" / "local" / "verification-private.json").exists())
            self.assertTrue((worktree.path / ".agt" / "memory" / "Implementation" / "lessons.md").exists())
            self.assertFalse((worktree.path / ".agt" / "_runtime").exists())
            self.assertFalse((worktree.path / ".agt" / "session-index.json").exists())

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

- [ ] **步骤 2：运行 worktree session 测试，确认它们先失败**

运行：`pytest tests/test_worktree_sessions.py -q`

预期：FAIL，并出现 `TypeError`，因为当前 `create_task_worktree()` 还不接受 `source_state_root`；同时还会暴露当前分支前缀和复制行为不符合新预期。

- [ ] **步骤 3：扩展 `worktree_sessions.py`，补齐 clean base ref 解析、支持状态复制、以及更完整的元数据**

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

- [ ] **步骤 4：重新运行聚焦测试，确认通过**

运行：`pytest tests/test_worktree_policy.py tests/test_worktree_sessions.py -q`

预期：PASS，并显示 `6 passed`。

- [ ] **步骤 5：提交这一小段实现**

```bash
git add agent_team/worktree_sessions.py tests/test_worktree_sessions.py
git commit -m "feat: create task worktrees from configured clean bases"
```

### 任务 3：把新的 Worktree 元数据接到 CLI 和 Session Index

**文件：**
- 修改：`agent_team/cli.py`
- 修改：`agent_team/worktree_sessions.py`
- 测试：`tests/test_cli.py`

- [ ] **步骤 1：更新 CLI 集成测试，断言 clean-base 元数据和复制过来的 AGT 支持状态**

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

        state_root = repo_root / ".agt"
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

        entry = json.loads((repo_root / ".agt" / "session-index.json").read_text())["sessions"][0]
        worktree_path = Path(entry["worktree_path"])
        self.assertEqual(entry["base_ref"], "test")
        self.assertTrue(entry["base_commit"])
        self.assertEqual(entry["worktree_policy_source"], "local_file")
        self.assertEqual(entry["naming_source"], "request_summary")
        self.assertTrue((worktree_path / ".agt" / "skill-preferences.yaml").exists())
        self.assertTrue((worktree_path / ".agt" / "memory" / "Implementation" / "lessons.md").exists())
        self.assertFalse((worktree_path / ".agt" / "_runtime").exists())

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

- [ ] **步骤 2：运行聚焦 CLI 测试，确认在改 wiring 前先失败**

运行：`pytest tests/test_cli.py -k "clean_base_policy and continue_reuses_created_worktree" -q`

预期：FAIL，因为现在仍然会打印 `branch: agent-team/`，`base_ref` 元数据还不存在，而且当前只会复制 `executor-env.json`。

- [ ] **步骤 3：修改 CLI 工作区准备逻辑，让它把完整 `TaskWorktree` 元数据写进 session index**

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

- [ ] **步骤 4：重新运行 CLI 聚焦测试，然后运行完整的 worktree 相关测试子集**

运行：`pytest tests/test_cli.py -k "clean_base_policy or continue_accepts_session_id_positional_alias" -q`

预期：PASS，并且新的分支前缀和 session-index 断言都成立。

运行：`pytest tests/test_worktree_policy.py tests/test_worktree_sessions.py tests/test_cli.py -q`

预期：PASS，同时旧的 `continue` alias 测试不能回归。

- [ ] **步骤 5：提交这一小段实现**

```bash
git add agent_team/cli.py agent_team/worktree_sessions.py tests/test_cli.py
git commit -m "feat: wire task worktree policy through cli"
```

### 任务 4：补齐本地策略与复制规则的文档

**文件：**
- 修改：`README.md`
- 修改：`tests/test_docs.py`

- [ ] **步骤 1：先加失败的文档测试，覆盖新的 task worktree 策略章节**

```python
def test_readme_documents_task_worktree_policy(self) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    readme = (repo_root / "README.md").read_text()

    self.assertIn("Task worktrees", readme)
    self.assertIn(".agt/local/worktree-policy.json", readme)
    self.assertIn("feature/<date>-<slug>", readme)
    self.assertIn('["origin/test", "origin/main", "test", "main"]', readme)
    self.assertIn(".agt/executor-env.json", readme)
    self.assertIn(".agt/skill-preferences.yaml", readme)
    self.assertIn(".agt/memory/", readme)
    self.assertIn(".agt/session-index.json", readme)
    self.assertIn(".agt/_runtime/", readme)
```

- [ ] **步骤 2：运行文档测试，确认 README 目前还没有这段说明**

运行：`pytest tests/test_docs.py -q`

预期：FAIL，并在 `test_readme_documents_task_worktree_policy` 中失败。

- [ ] **步骤 3：给 README 增加一节，说明本地策略路径、clean base fallback、以及 AGT 支持状态复制规则**

````markdown
## Task worktrees

`agent-team run` 默认会从一个干净基线创建新的任务 branch 和新的 `.worktrees/` 工作区，而不是直接从当前 `HEAD` 继续分叉。

本地策略文件：

```text
.agt/local/worktree-policy.json
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

- `.agt/executor-env.json`
- `.agt/skill-preferences.yaml`
- `.agt/local/`
- `.agt/memory/`

新 worktree 不会复制这些运行历史：

- `.agt/session-index.json`
- `.agt/_runtime/`
- 历史 session 产物
````

- [ ] **步骤 4：重新运行文档测试，确认通过**

运行：`pytest tests/test_docs.py -q`

预期：PASS，并满足新的 README 断言。

- [ ] **步骤 5：提交这一小段文档改动**

```bash
git add README.md tests/test_docs.py
git commit -m "docs: document task worktree policy"
```

### 任务 5：做最终回归，确认新的 Worktree 流程稳定

**文件：**
- 修改：`agent_team/worktree_policy.py`
- 修改：`agent_team/worktree_sessions.py`
- 修改：`agent_team/cli.py`
- 修改：`README.md`
- 修改：`tests/test_worktree_policy.py`
- 修改：`tests/test_worktree_sessions.py`
- 修改：`tests/test_cli.py`
- 修改：`tests/test_docs.py`

- [ ] **步骤 1：运行新功能的完整聚焦回归测试**

运行：`pytest tests/test_worktree_policy.py tests/test_worktree_sessions.py tests/test_cli.py tests/test_docs.py -q`

预期：PASS，所有新增和更新的测试都绿。

- [ ] **步骤 2：运行更广一点的 runtime smoke tests**

运行：`pytest tests/test_workspace_metadata.py tests/test_console_data.py tests/test_board.py -q`

预期：PASS，证明新的 worktree 命名和 state-root 行为没有破坏 workspace metadata 消费方。

- [ ] **步骤 3：如果有回归，只重新跑对应失败文件，直到针对性修复通过**

运行其中之一：

- `pytest tests/test_worktree_policy.py -q`
- `pytest tests/test_worktree_sessions.py -q`
- `pytest tests/test_cli.py -q`
- `pytest tests/test_docs.py -q`

预期：之前失败的那个测试文件单独恢复 PASS，然后再继续最终提交。

- [ ] **步骤 4：创建最终实现提交**

```bash
git add agent_team/worktree_policy.py agent_team/worktree_sessions.py agent_team/cli.py README.md \
  tests/test_worktree_policy.py tests/test_worktree_sessions.py tests/test_cli.py tests/test_docs.py
git commit -m "feat: isolate task runs with configurable clean worktrees"
```

## 自检清单

- 规格覆盖：
  - `L3` 本地策略路径在任务 1 中实现。
  - clean base ref fallback 在任务 1 到任务 3 中实现并测试。
  - 新 worktree 像普通 `git worktree` 一样工作，且不会重建仓库正式五层文档，这一点在任务 2 中落实。
  - AGT 支持状态复制和 runtime 历史排除，在任务 2 中实现，在任务 3 中再次验证。
  - README / 用户侧说明在任务 4 中补齐。
- 占位词扫描：
  - 没有残留 `TODO` / `TBD`。
  - 每个会改代码的任务都给了明确代码块和准确测试命令。
- 类型一致性：
  - `TaskWorktree` 字段、`upsert_session_index_entry()` 参数名、以及 README 里的字段名在整份计划中保持一致。
