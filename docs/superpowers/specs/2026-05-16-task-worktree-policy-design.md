# 任务级独立分支与隔离 Worktree 本地策略设计

## 背景

当前 `agent-team run` 在创建新任务工作区时，会直接从当前 `HEAD` 拉出新 branch 和新 worktree。这使得“小需求”虽然物理上进入了独立 worktree，但语义上仍然继承了当前开发分支的上下文，容易出现两类问题：

- 小需求默认叠在一个长期开发分支之上，无法保证最小化变更基线。
- branch/worktree 命名直接来自需求文本，中文需求会生成中文路径，不适合稳定的 GitHub/worktree 工作流。

用户希望默认工作方式改为：

- 一个需求，对应一个独立 branch。
- 一个需求，对应一个独立 worktree。
- 新 branch 从“干净基线”拉出，而不是从当前 `HEAD` 继续分叉。
- branch 和 worktree 目录采用英文风格命名，并带上日期和大致需求内容。

## 问题

1. 当前 worktree 基线绑定当前 `HEAD`，无法自然形成“最小化需求分支”。
2. branch/worktree 命名没有项目级策略入口，默认行为不稳定。
3. 不同项目的默认基线和命名前缀可能不同，不能写死在 runtime 代码里。
4. 这类规则语义上是项目运行默认值，但用户明确要求它只在本地生效、不要提交仓库。

## 目标

- 让 `run` 在默认情况下从干净基线创建任务级独立 branch 和独立 worktree。
- 让 clean base ref、branch 前缀、worktree 根目录、命名策略成为项目级可配置项。
- 保持配置本地生效且默认不提交。
- 对中文需求文本生成英文风格 branch/worktree 名称，并在失败时稳定回退。
- 保持 `continue` 语义不变，继续复用已记录的 worktree。

## 非目标

- 本次不修改五层 stage machine，也不改变 `Route` 的流程控制逻辑。
- 本次不自动 `git fetch` 或更新远端引用，只使用当前仓库已经可解析的 ref。
- 本次不要求用户每次手动输入 branch slug。
- 本次不设计跨项目共享的全局 worktree 策略中心。

## 核心决策

### 决策一：语义归属与存储位置分离

这套规则的语义归属属于 `L3 ProjectRuntime`，因为它描述的是“这个项目默认如何起任务工作区、从哪里分支、命名约定是什么”。

但其物理存储位置采用本地私有配置承载，不进入仓库版本历史。也就是说：

- 规则语义：`L3`
- 文件载体：`L5` 本地私有配置

这样可以同时满足：

- 不同项目有不同默认值
- 用户本地能调整
- 不污染共享仓库

### 决策二：配置文件放在 `.agent-team/local/worktree-policy.json`

新增本地配置文件：

`.agent-team/local/worktree-policy.json`

该路径已经符合现有 runtime 的本地私有配置习惯，也天然适合加入 `.gitignore`。

如果文件不存在，runtime 使用内建默认值。

### 决策三：clean base ref 使用候选链解析

默认候选顺序：

```json
["origin/test", "origin/main", "test", "main"]
```

runtime 创建新任务 worktree 时，按顺序解析第一个存在的 ref，作为这次任务 branch 的基线。

如果所有候选都不存在，`run` 直接阻塞并输出明确错误，而不是退回当前 `HEAD`。

这样可以确保“隔离任务”真的从干净基线开始，而不是悄悄回到旧行为。

### 决策四：branch/worktree 名称采用“日期 + 英文摘要”策略

新任务名称格式：

- branch: `<branch_prefix><date>-<slug>`
- worktree: `<worktree_root>/<date>-<slug>`

默认示例：

- branch: `feature/20260516-add-login-button`
- worktree: `.worktrees/20260516-add-login-button`

其中：

- `date` 默认使用 `YYYYMMDD`
- `slug` 来自对需求文本的英文摘要
- 如果摘要失败或结果为空，回退为 `task`

用户对命名的要求不是“逐字精确翻译”，而是“看得出大致在做什么”。因此这里采用 best-effort 策略：

1. 先尝试把需求文本压缩成 2 到 4 个英文词。
2. 再做 ASCII slug 清洗，只保留 `[a-z0-9-]`。
3. 如果无法得到有效 slug，则回退为 `task`。

命名生成失败不能阻塞任务创建。

### 决策五：当前工作区是否脏，不影响新任务隔离

当前仓库所在 worktree 可能已经有未提交改动，甚至正在承载另一个长期任务分支。

这次改动的目标正是让新需求脱离这些上下文。因此：

- 新任务 worktree 的创建，不以当前工作区是否干净为前提。
- 唯一基线来源是解析出来的 clean base ref。

这样可以避免“因为当前分支很脏，所以无法起隔离任务”的反直觉行为。

## 配置结构

推荐最小配置结构：

```json
{
  "base_ref_candidates": [
    "origin/test",
    "origin/main",
    "test",
    "main"
  ],
  "branch_prefix": "feature/",
  "worktree_root": ".worktrees",
  "date_format": "%Y%m%d",
  "slug_max_length": 40,
  "naming_mode": "request_summary_with_fallback"
}
```

字段说明：

- `base_ref_candidates`
  - clean base ref 候选列表，按顺序解析。
- `branch_prefix`
  - 新 branch 的前缀，默认建议 `feature/`。
- `worktree_root`
  - worktree 根目录，相对 repo root 解析。
- `date_format`
  - 日期格式，默认 `%Y%m%d`。
- `slug_max_length`
  - 需求 slug 最大长度，不含日期和前缀。
- `naming_mode`
  - 当前版本只实现 `request_summary_with_fallback`。

## 运行时行为

### 新任务创建

当用户执行 `agent-team run --message "<需求>"`，且不是 `--continue`、也没有显式覆盖 `state_root` 时：

1. 从当前项目根读取 `.agent-team/local/worktree-policy.json`。
2. 如果不存在，加载内建默认配置。
3. 解析 `base_ref_candidates`，找到第一个可用 ref。
4. 基于需求文本生成英文摘要 slug。
5. 组合日期和 slug，生成 branch/worktree 名称。
6. 使用解析出的 clean base ref 执行 `git worktree add -b ... <path> <base-ref>`。
7. 将 session 运行环境切换到这个新 worktree 下继续执行。

### continue 行为

`agent-team continue` 不重新解析 worktree 策略，也不新建 branch。

它只复用 session index 中已经记录的 worktree 路径和 session id。

### 配置快照

为了方便排查，这次运行使用的有效 worktree policy 应该落一份快照到新 worktree 的：

`<worktree>/.agent-team/local/worktree-policy.json`

如果原始本地配置文件存在，就复制它的内容。

如果原始本地配置文件不存在，就把本次解析后的内建默认配置写成快照文件。

这样即使后续用户改了原始本地配置，也能追溯某次 session 启动时采用的策略快照。

## 命名规则细节

### branch 名称

格式：

`<branch_prefix><date>-<slug>`

示例：

- `feature/20260516-add-login-button`
- `feature/20260516-fix-order-submit`
- `feature/20260516-task`

### worktree 目录名

格式：

`<date>-<slug>`

示例：

- `.worktrees/20260516-add-login-button`
- `.worktrees/20260516-fix-order-submit`

### 唯一性

如果 branch 或 worktree 目录已存在，runtime 自动追加数值后缀：

- `feature/20260516-add-login-button-2`
- `.worktrees/20260516-add-login-button-2`

唯一性冲突不能导致回退到当前 `HEAD`。

## Session 元数据

session index 除现有字段外，建议增加：

- `base_ref`
  - 这次创建 worktree 时实际命中的 ref 名。
- `base_commit`
  - `base_ref` 解析后的 commit SHA。
- `worktree_policy_source`
  - `local_file` 或 `builtin_default`。
- `worktree_policy_snapshot_path`
  - 新 worktree 内快照文件的路径。
- `naming_source`
  - `request_summary` 或 `fallback_task`。

这样后续排查“这个需求是从哪条干净线起出来的”会直接很多。

## 失败与回退

### base ref 全部不可用

直接阻塞：

- 输出尝试过的 ref 列表
- 提示用户在本地配置里修改候选顺序，或先同步目标分支

不能回退到当前 `HEAD`。

### 摘要生成失败

不阻塞：

- `slug = task`
- `naming_source = fallback_task`

### 本地配置损坏

如果 JSON 非法或字段类型错误，直接阻塞并给出具体字段错误，避免静默使用错误策略。

## 兼容性

- 当前默认 `.worktrees/` 根目录保留不变，但变为可配置。
- `continue` 逻辑保留不变。
- 现有 `agent-team/<name>` branch 前缀改为配置驱动，默认迁移为 `feature/`。
- 现有中文 slug 行为废弃，改为英文摘要 + fallback。

这属于有意的默认行为调整，但只影响“新创建任务 worktree”的路径和 branch 命名，不影响已存在 session。

## 测试范围

需要补充或更新的测试至少包括：

1. 无配置文件时，使用内建默认候选链和 `feature/` 前缀。
2. 存在本地配置文件时，branch 前缀、worktree 根目录、base ref 候选能生效。
3. `origin/test` 不存在时，会正确 fallback 到后续候选。
4. 所有 base ref 都不存在时，`run` 明确失败。
5. 中文需求文本会生成英文风格命名；摘要失败时回退为 `task`。
6. 已存在同名 branch/worktree 时，会自动追加唯一性后缀。
7. `continue` 不重新创建 worktree。
8. worktree policy 会被快照复制到新 worktree。

## 后续实现边界

本次设计只覆盖“任务级 worktree/branch 隔离策略”。

后续如果要扩展，可以继续做：

- CLI 显式覆盖 `branch_prefix` 或 `base_ref`
- 人工指定 slug
- 更强的命名摘要模型
- 与 `Route` 或 `ProjectRuntime` 文档建立正式回写关系

但这些都不属于当前最小可用范围。
