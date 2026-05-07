# Roles JSON 字段级重叠分析

分析对象：每个 attempt 下的 7 个 JSON/MD 文件的全部字段。

## 文件清单

| 简称 | 文件 | 所属目录 |
|---|---|---|
| **SR** | `{role}-stage-result.json` | stage-results |
| **RC** | `{role}-stage-record.json` | stage-results |
| **RS** | `{role}-run-state.json` | stage-results |
| **RT** | `{role}-runtime-trace.json` | stage-results |
| **EJ** | `{role}-execution-journal.md` | stage-results |
| **RF** | `{role}-review-findings.json` | stage-results |
| **TC** | `{role}-task-contract.json` | execution-contexts |
| **IC** | `{role}-input-context.json` | execution-contexts |
| **OS** | `{role}-output-schema.json` | execution-contexts |

---

## 一、字段含义词典

每个字段是做什么的、谁写的、谁读的。

### 1. SR — `{role}-stage-result.json`（Agent 输出，Runtime 读取并校验）

| 字段 | 类型 | 含义 | 谁写入 | 谁消费 |
|---|---|---|---|---|
| `session_id` | string | 工作流会话的唯一标识，格式为 `{RFC3339时间戳}Z-{项目名}-runtime` | Runtime 注入 | 调试/日志 |
| `stage` | string | 当前阶段的角色名，如 `Product` / `Dev` / `QA` / `Acceptance` | Runtime 注入 | 调试/日志 |
| `status` | enum | Agent 自报的执行结果：`completed`=正常完成，`failed`=Agent 发现缺陷判定失败，`blocked`=缺少环境/凭证/数据无法继续 | Agent | Runtime → 决定是否推进到下一阶段 |
| `artifact_name` | string | 产物文件名，如 `acceptance_report.md` | Agent | Runtime → 归档时用作文件名 |
| `artifact_content` | string | 产物的完整文本内容（Markdown） | Agent | 下游阶段 Agent（作为输入）、人类阅读 |
| `contract_id` | string | 本次执行的阶段合同哈希 ID，关联到 task-contract.json | Runtime 注入 | 调试/审计 |
| `journal` | string | Agent 执行过程的简要流水账，通常一句话 | Agent | 调试/追溯 |
| `findings[]` | array | Agent 发现的缺陷/问题列表，每个元素包含 source_stage / issue / severity / lesson 等 | Agent | Runtime gate → 决定是否回退到上游阶段；下游 Agent → 了解历史问题 |
| `evidence[]` | array | Agent 执行期间收集的证据项，如执行的命令、退出码、截图、测试结果等 | Agent | Runtime gate → 与 contract.evidence_specs 比对，判定是否通过 |
| `suggested_next_owner` | string | Agent 建议下一步交给哪个角色处理 | Agent | Runtime（当前未实际使用，始终为空） |
| `summary` | string | Agent 对本次执行的结论性摘要，1-2 句话 | Agent | 人类快速浏览 |
| `acceptance_status` | string | 验收判定：`recommended_go`=建议通过 / `recommended_no_go`=建议驳回 / `blocked`=无法判断。非 Acceptance 阶段为空字符串 | Agent（仅 Acceptance） | Runtime → 决定 WaitForHumanDecision 状态 |
| `blocked_reason` | string | 阻塞原因说明，仅 status=blocked 时填写 | Agent | 人类了解阻塞原因 |
| `supplemental_artifacts` | object | 补充产物，当前 schema 定义为空对象（`additionalProperties: false`），永远为 `{}` | Agent（从未使用） | 无人使用 |

**`findings[]` 子字段**：

| 子字段 | 含义 |
|---|---|
| `source_stage` | 缺陷由哪个阶段引入 |
| `target_stage` | 缺陷影响哪个阶段，也暗示应回退到哪个阶段修复 |
| `issue` | 缺陷的具体描述 |
| `severity` | 严重程度 |
| `lesson` | 从该缺陷中提炼的经验教训，供后续 session 复用 |
| `proposed_context_update` | Agent 建议写入 role context（上下文文件）的内容 |
| `proposed_skill_update` | Agent 建议写入 role skill（技能定义）的内容 |
| `evidence` | 支撑该 finding 的证据文本 |
| `evidence_kind` | 证据类型 |
| `required_evidence` | 验证该缺陷已修复需要的证据清单 |
| `completion_signal` | 如何判断该缺陷已被修复的信号描述 |

**`evidence[]` 子字段**：

| 子字段 | 含义 |
|---|---|
| `name` | 证据名称，对应 contract.evidence_requirements 中的名称 |
| `kind` | 证据类型：`command`=命令执行结果 / `report`=报告 / `artifact`=产物文件 / `screenshot`=截图 等 |
| `summary` | 证据摘要描述 |
| `artifact_path` | 关联产物文件路径（可选） |
| `command` | 执行的命令（kind=command 时填写） |
| `exit_code` | 命令退出码（kind=command 时填写），非命令证据为 null |
| `producer` | 证据生产者，如 `runtime-driver` / `claude-agent` |

---

### 2. RC — `{role}-stage-record.json`（纯路径索引，Runtime 写入和维护）

| 字段 | 含义 | 可推导？ |
|---|---|---|
| `stage` | 阶段名 | 是，目录路径 `roles/{stage}/` |
| `artifact_name` | 产物文件名 | 否（但与 SR.artifact_name 重复） |
| `artifact_path` | 产物文件的绝对路径 | 是，约定路径 |
| `journal_path` | execution-journal.md 的绝对路径 | 是，约定路径 |
| `findings_path` | review-findings.json 的绝对路径 | 是，约定路径 |
| `acceptance_status` | 同 SR.acceptance_status | 否（与 SR 重复） |
| `round_index` | 第几次尝试 | 是，目录名 `attempt-{N}` |
| `supplemental_artifact_paths` | 补充产物路径映射，永远为 `{}` | — |
| `archive_path` | 产物归档副本路径 | 是，约定路径 |

**定位**：Runtime 在 Agent 执行完毕后写入，作为"目录文件"，方便其他组件不用猜路径就能找到产物文件。但由于所有路径都遵循 `roles/{stage}/attempt-{N}/stage-results/{role}-{type}.{ext}` 的约定，这个文件的实用价值很低。

---

### 3. RS — `{role}-run-state.json`（Runtime 状态机视角，Runtime 写入）

| 字段 | 含义 | 谁写入 | 谁消费 |
|---|---|---|---|
| `run_id` | 本次运行的唯一 ID，格式 `{stage}-run-{N}` | Runtime | 日志关联 |
| `session_id` | 会话 ID | Runtime | 日志关联 |
| `stage` | 阶段名 | Runtime | 状态机 |
| `state` | 运行时判定结果：`PASSED`=门禁通过 / `FAILED`=门禁未通过 / `BLOCKED`=阻塞 | Runtime（gate 判定后） | 状态机 → 决定 next_stage |
| `contract_id` | 关联的合同 ID | Runtime | 审计 |
| `attempt` | 第几次尝试（等同于 RC.round_index） | Runtime | 状态机 |
| `required_outputs[]` | 合同要求的产物文件列表，从 TC 复制 | Runtime | gate 校验 |
| `required_evidence[]` | 合同要求的证据名称列表，从 TC 复制 | Runtime | gate 校验 |
| `worker` | 执行器类型：`dry-run`=空跑模拟 / `claude-agent`=真实 Agent | Runtime | 审计 |
| `created_at` | 运行创建时间（ISO 8601） | Runtime | 审计/超时判断 |
| `updated_at` | 最后更新时间 | Runtime | 审计 |
| `candidate_bundle_path` | 指向 SR 文件的路径——gate 评估的对象 | Runtime | gate（告诉 gate 去哪读 Agent 输出） |
| `blocked_reason` | 阻塞原因，同 SR.blocked_reason | Runtime | 状态机 |
| `artifact_paths{}` | key=stage 名，value=产物路径。用于下游阶段引用上游产物 | Runtime | 下游阶段的 IC/T C 构建 |
| `gate_result` | 门禁判定结果（见下方子字段） | Runtime（gate 判定后） | 状态机 |

**`gate_result` 子字段**：

| 子字段 | 含义 |
|---|---|
| `status` | `PASSED`=所有 required_outputs 和 required_evidence 齐全 / `FAILED`=有缺失 |
| `reason` | 判定原因的自然语言描述 |
| `missing_outputs[]` | 缺失的产物列表（为空表示全部产出） |
| `missing_evidence[]` | 缺失的证据列表（为空表示全部收集） |
| `findings[]` | 从 SR.findings 复制过来的发现列表 |
| `checked_at` | gate 判定时间 |

---

### 4. RT — `{role}-runtime-trace.json`（步骤级执行时间线，Runtime 写入）

| 字段 | 含义 | 谁写入 | 谁消费 |
|---|---|---|---|
| `session_id` | 会话 ID | Runtime | 调试 |
| `run_id` | 运行 ID | Runtime | 关联到 RS |
| `stage` | 阶段名 | Runtime | 调试 |
| `required_pass_steps[]` | 必须全部通过的步骤名称列表，用于健康检查 | Runtime | 调试/监控 |
| `steps[]` | 按时间顺序的步骤记录 | Runtime | 调试/性能分析 |

**`steps[]` 子字段**：

| 子字段 | 含义 |
|---|---|
| `step` | 步骤名，8 个固定步骤：`contract_built` → `execution_context_built` → `stage_run_acquired` → `executor_started` → `executor_completed` → `result_submitted` → `gate_evaluated` → `state_advanced` |
| `status` | `ok`=成功 / `error`=失败 |
| `at` | 步骤完成时间（ISO 8601） |
| `details` | 步骤详情：如 contract_id、context_id、worker 类型、gate_status 等 |

**每个 step 的含义**：

| step | 含义 | 关键 detail |
|---|---|---|
| `contract_built` | Runtime 根据 role skill 和 stage policies 构建阶段合同 | contract_id, required_outputs |
| `execution_context_built` | Runtime 收集输入上下文（上游产物、findings、repo 结构等） | context_id, context_path |
| `stage_run_acquired` | Runtime 确定执行器（dry-run 或真实 Agent）并注入 skill | worker, skill_injection |
| `executor_started` | 执行器开始工作 | executor |
| `executor_completed` | 执行器完成工作，返回结果 | result_status |
| `result_submitted` | Runtime 将 Agent 输出写入 stage-result.json | candidate_bundle_path |
| `gate_evaluated` | Runtime 根据 contract 校验 stage-result | gate_status, gate_reason |
| `state_advanced` | 状态机更新，决定下一阶段 | from_state, to_state |

---

### 5. EJ — `{role}-execution-journal.md`（流水日志文件，Agent 写入）

| 字段 | 含义 |
|---|---|
| 整个文件 | 与 SR.journal 一字不差的一句话执行日志 |

---

### 6. RF — `{role}-review-findings.json`（findings 副本，Agent 写入）

| 字段 | 含义 |
|---|---|
| 整个文件 | 与 SR.findings 完全相同的 JSON 数组 |

---

### 7. TC — `{role}-task-contract.json`（阶段合同，Runtime 写入，Agent 读取）

| 字段 | 含义 | 谁写入 | 谁消费 |
|---|---|---|---|
| `session_id` | 会话 ID | Runtime | Agent（prompt 中展示） |
| `stage` | 阶段名 | Runtime | Agent |
| `contract_id` | 合同哈希 ID | Runtime | 审计 |
| `goal` | 本阶段目标，自然语言一句话 | Runtime（从 skill 提取） | Agent → 理解要做什么 |
| `input_artifacts{}` | key=产物名，value=绝对路径。告诉 Agent 去哪读上游产物 | Runtime | Agent → 读取输入文件 |
| `required_outputs[]` | 必须产出的文件名列表，如 `["acceptance_report.md"]` | Runtime（从 skill 提取） | Agent → 知道要写什么文件；gate → 校验产物是否产出 |
| `forbidden_actions[]` | 禁止 Agent 执行的操作列表，如 `must_not_change_stage_order` | Runtime（从 stage policies 提取） | Agent → 约束行为边界 |
| `evidence_requirements[]` | 必须收集的证据名称列表，如 `["product_level_validation"]` | Runtime（从 skill 提取） | Agent → 知道需要收集哪些证据；gate → 校验证据是否齐全 |
| `evidence_specs[]` | 每个证据的详细规格：名称、是否必须、允许的类型、必填字段、最少条数 | Runtime（从 skill 提取） | Agent → 知道每条证据的具体格式要求；gate → 校验证据格式 |
| `role_context` | 角色的完整定义文本，包含三段内容：Skill（技能定义）+ Context（上下文文件）+ Memory（记忆文件） | Runtime（从 assets/roles 读取） | Agent → 核心 prompt 组成部分，告诉 Agent "你是谁、你的职责、你该怎么做" |

---

### 8. IC — `{role}-input-context.json`（上下文快照，Runtime 写入，Agent 读取）

| 字段 | 含义 | 谁写入 | 谁消费 |
|---|---|---|---|
| `session_id` | 会话 ID | Runtime | 调试 |
| `stage` | 阶段名 | Runtime | 调试 |
| `round_index` | 第几次尝试 | Runtime | Agent |
| `context_id` | 上下文快照的哈希 ID | Runtime | 调试 |
| `contract_id` | 关联的合同 ID | Runtime | 关联 TC |
| `original_request_summary` | 用户最初需求的摘要，贯穿整个 session 不变 | Runtime（从用户输入提取） | Agent → 始终知道"最终目标是什么" |
| `approved_prd_summary` | 已确认的 PRD 摘要文本 | Runtime（从 Product 产物提取） | 下游 Agent → 知道产品需求是什么 |
| `approved_tech_plan_content` | 已确认的技术方案全文 | Runtime（从 Dev attempt-001 产物提取） | QA/Acc Agent → 知道技术实现方案 |
| `approved_acceptance_plan_content` | 已确认的验收方案全文 | Runtime（从 Product 产物提取） | QA/Acc Agent → 知道验收标准 |
| `acceptance_matrix[]` | 验收标准矩阵，每条包含 id / criterion / source | Runtime（从 acceptance_plan 解析） | QA/Acc Agent → 逐条对照验证 |
| `constraints[]` | 约束条件列表，当前始终为空数组 | Runtime（从 stage policies 提取） | Agent |
| `required_outputs[]` | 同 TC.required_outputs，在此处冗余存储 | Runtime（复制自 TC） | Agent |
| `required_evidence[]` | 同 TC.evidence_requirements，在此处冗余存储 | Runtime（复制自 TC） | Agent |
| `relevant_artifacts[]` | 上游所有产物的**完整内容快照**，每个元素含 name / summary / sha256 / content_chars | Runtime（读取上游产物文件） | Agent → **核心输入**，包含 PRD、技术方案、实现、QA 报告等全部上下文 |
| `actionable_findings[]` | 上游阶段传入的需要在本阶段处理的 findings | Runtime（从上游 SR.findings 筛选） | Agent → 知道要处理哪些遗留问题 |
| `repo_context_summary` | 仓库结构摘要：文档目录映射 + role context/memory 文件位置 | Runtime（扫描仓库） | Agent → 了解项目结构 |
| `role_context_digest` | TC.role_context 的 sha256 哈希，用于验证 prompt 中注入的 role context 是否完整 | Runtime | 调试/验证 |
| `budget` | Token 预算限制：`max_context_tokens`=最大上下文 / `max_artifact_snippet_chars`=单个产物片段截断长度 / `max_findings`=最大 findings 数 | Runtime（从配置读取） | Runtime → 控制 IC 体积，对超长内容截断 |

---

### 9. OS — `{role}-output-schema.json`（输出格式约束，Runtime 写入，Agent 读取）

| 字段 | 含义 |
|---|---|
| `type` | 固定为 `"object"` |
| `required[]` | 必须填写的顶层字段名列表 |
| `properties{}` | 每个字段的类型定义（type / enum / items / required 等） |
| `additionalProperties` | 固定为 `false`，禁止 Agent 输出 schema 未定义的字段 |

---

## 二、字段 → 出现位置 矩阵

### `session_id`

| 文件 | 字段路径 | 示例值 |
|---|---|---|
| SR | `session_id` | `"20260506T1036...runtime"` |
| RS | `session_id` | 同上 |
| RT | `session_id` | 同上 |
| TC | `session_id` | 同上 |
| IC | `session_id` | 同上 |

**5 个文件** 重复存储同一个 session_id。这些文件都在同一个 session 目录下，目录名本身就包含 session_id。

---

### `stage`

| 文件 | 字段路径 | 示例值 |
|---|---|---|
| SR | `stage` | `"Acceptance"` |
| RC | `stage` | `"Acceptance"` |
| RS | `stage` | `"Acceptance"` |
| RT | `stage` | `"Acceptance"` |
| TC | `stage` | `"Acceptance"` |
| IC | `stage` | `"Acceptance"` |

**6 个文件**。目录路径 `roles/acceptance/` 已经包含了这个信息。

---

### `contract_id`

| 文件 | 字段路径 | 示例值 |
|---|---|---|
| SR | `contract_id` | `"0fe808617e44cae3"` |
| RS | `contract_id` | 同上 |
| TC | `contract_id` | 同上 |
| IC | `contract_id` | 同上 |

**4 个文件**。

---

### `status` / `state`（同一个概念不同命名）

| 文件 | 字段路径 | 值 | 命名 |
|---|---|---|---|
| SR | `status` | `"completed"` | 小写下划线 |
| RS | `state` | `"PASSED"` | 大写下划线 |
| RS | `gate_result.status` | `"PASSED"` | 同上 |
| RT | `steps[N].details.gate_status` | `"PASSED"` | 同上（第 3 种命名） |

同一个执行结果用 **3 种不同命名**（status / state / gate_status）和 **2 种不同值格式**（completed/failed/blocked vs PASSED/FAILED/BLOCKED）表达了 4 次。

---

### `blocked_reason`

| 文件 | 字段路径 |
|---|---|
| SR | `blocked_reason` |
| RS | `blocked_reason` |

**2 个文件**。而且当 status != blocked 时始终为空字符串。

---

### `findings`（阶段发现的问题列表）

| 文件 | 字段路径 | 备注 |
|---|---|---|
| SR | `findings` | Agent 产出的原始 findings |
| RF | 整个文件 | **100% 等同于 SR.findings** |
| RS | `gate_result.findings` | Gate 评估时复制的同一份数据 |

**3 处存储**，内容完全相同。

---

### `journal`（执行流水日志）

| 文件 | 字段路径 | 内容 |
|---|---|---|
| SR | `journal` | `"Dry-run executor produced acceptance_report.md for Acceptance."` |
| EJ | 整个文件 | `"Dry-run executor produced acceptance_report.md for Acceptance."` |

**2 处存储**，一字不差。

---

### `summary` / `gate_result.reason`（结论性摘要）

| 文件 | 字段路径 | 内容 |
|---|---|---|
| SR | `summary` | `"Acceptance dry-run result satisfied the stage contract."` |
| RS | `gate_result.reason` | `"All contract and evidence gates satisfied."` |

两个字段语义高度重叠——都在描述"为什么通过了"。SR.summary 偏 Agent 视角，RS.gate_result.reason 偏 Runtime 视角，但信息量等价。

---

### `acceptance_status`

| 文件 | 字段路径 | 示例值 |
|---|---|---|
| SR | `acceptance_status` | `"recommended_go"` |
| RC | `acceptance_status` | `"recommended_go"` |

**2 个文件**。且对非 Acceptance 阶段，这个字段永远是空字符串（见 Dev/QA 的 stage-result）。

---

### `artifact_name` / 产物标识

| 文件 | 字段路径 | 示例值 |
|---|---|---|
| SR | `artifact_name` | `"acceptance_report.md"` |
| RC | `artifact_name` | 同上 |
| RS | `artifact_paths.{stage}` | 路径中包含文件名 |

**2 处**（不算 RS 路径推导）。

---

### `artifact_content` / 产物内容

| 文件 | 字段路径 | 示例值 |
|---|---|---|
| SR | `artifact_content` | 完整 Markdown 文本 |
| 输出 .md 文件 | 整个文件 | 完全相同的文本 |

**2 处存储** 完整产物内容。当产物很大时，stage-result.json 会被严重撑大。

---

### `required_outputs`

| 文件 | 字段路径 | 示例值 |
|---|---|---|
| TC | `required_outputs` | `["acceptance_report.md"]` |
| IC | `required_outputs` | 同上 |
| RS | `required_outputs` | 同上 |

**3 个文件** 存储同一份列表。

---

### `required_evidence` / `evidence_requirements`

| 文件 | 字段路径 | 内容 |
|---|---|---|
| TC | `evidence_requirements` | `["product_level_validation"]` |
| IC | `required_evidence` | 同上 |
| RS | `required_evidence` | 同上 |

**3 个文件**。TC 里叫 `evidence_requirements`，IC 和 RS 里叫 `required_evidence`——同一份数据两个名字。

---

### `evidence[]`（实际证据）vs `evidence_specs[]`（证据规格）

| 文件 | 字段路径 | 含义 |
|---|---|---|
| SR | `evidence[]` | Agent 实际产出的证据项 |
| TC | `evidence_specs[]` | 合同要求的证据规格（name, allowed_kinds, required_fields, minimum_items） |

这两个不重叠——一个是"要求"，一个是"产出"。但 RS.gate_result 用 TC 的 specs 去校验 SR 的 evidence，判定逻辑分散在三处。

---

### `round_index` / `attempt`

| 文件 | 字段路径 | 值 | 命名 |
|---|---|---|---|
| RC | `round_index` | `1` | `round_index` |
| RS | `attempt` | `1` | `attempt` |
| IC | `round_index` | `1` | `round_index` |

同一个概念 **3 个文件 2 种命名**。目录名 `attempt-001` 已经包含此信息。

---

### 产物 / 文件路径（散落在多处）

| 文件 | 字段路径 | 指向 |
|---|---|---|
| RC | `artifact_path` | 产物 .md 文件路径 |
| RC | `journal_path` | execution-journal.md 路径 |
| RC | `findings_path` | review-findings.json 路径 |
| RC | `archive_path` | output-*.md 归档路径 |
| RC | `supplemental_artifact_paths` | 补充产物路径 |
| RS | `candidate_bundle_path` | 指向 SR 文件路径 |
| RS | `artifact_paths` | 产物路径映射 |
| TC | `input_artifacts` | 输入产物路径映射 |

RC 里 6 个路径字段，RS 里 2 个，TC 里 1 个映射。**9 个路径字段分布在 3 个文件中**，且大部分可按约定推导。

---

### `role_context` / `role_context_digest`

| 文件 | 字段路径 | 内容 | 大小 |
|---|---|---|---|
| TC | `role_context` | 完整 Skill + Context + Memory 文本 | ~5400 chars |
| IC | `role_context_digest` | `sha256:979a16...` | ~80 chars |

IC 只存了 digest，TC 存了全文。但 agent-prompt-bundle.md 也包含全文——prompt bundle 是 TC + IC 的渲染版。

---

### `relevant_artifacts[]`  vs  `input_artifacts{}`

| 文件 | 字段路径 | 内容 |
|---|---|---|
| IC | `relevant_artifacts[]` | 每个 artifact 的完整文本 + sha256 + 元数据 |
| TC | `input_artifacts{}` | 仅路径映射（name → file path） |

IC 存了全部上游产物的**完整文本**（含 PRD、技术方案、实现、QA 报告等），导致 IC 体积巨大（15KB+）。TC 只存路径。两者互补但 IC 承担了"把全量上下文喂给 Agent"的职责。

---

### `supplemental_artifacts` / `supplemental_artifact_paths`

| 文件 | 字段路径 | 值 |
|---|---|---|
| SR | `supplemental_artifacts` | `{}` |
| RC | `supplemental_artifact_paths` | `{}` |

永远是空对象。OS 里定义为 `additionalProperties: false` 且 `properties: {}`。

---

### 独有字段（不存在重叠）

| 文件 | 字段 | 说明 |
|---|---|---|
| TC | `goal` | 阶段目标描述，仅此一处 |
| TC | `forbidden_actions` | 禁止行为列表，仅此一处 |
| TC | `evidence_specs` | 证据规格详情，仅此一处 |
| IC | `original_request_summary` | 用户原始需求摘要，仅此一处 |
| IC | `approved_prd_summary` | 已确认 PRD 摘要，仅此一处 |
| IC | `approved_tech_plan_content` | 已确认技术方案全文，仅此一处 |
| IC | `approved_acceptance_plan_content` | 已确认验收方案全文，仅此一处 |
| IC | `acceptance_matrix` | 验收标准矩阵，仅此一处 |
| IC | `constraints` | 约束列表（始终为空），仅此一处 |
| IC | `actionable_findings` | 上游传入的待处理 findings，仅此一处 |
| IC | `repo_context_summary` | 仓库上下文摘要，仅此一处 |
| IC | `budget` | token 预算限制，仅此一处 |
| RS | `run_id` | 运行 ID，仅此一处 |
| RS | `worker` | 执行器名称，仅此一处 |
| RS | `created_at` / `updated_at` | 时间戳，仅此一处 |
| RS | `gate_result` | 完整的 gate 判定结果，仅此一处 |
| RT | `required_pass_steps` | 必须通过的步骤列表，仅此一处 |
| RT | `steps[]` | 步骤级时间线，仅此一处 |
| RC | `archive_path` | 归档路径，仅此一处（但可推导） |

---

## 三、重叠热力图

```
字段                  SR  RC  RS  RT  EJ  RF  TC  IC  重复次数
────────────────────────────────────────────────────────────
stage                 ✓   ✓   ✓   ✓           ✓   ✓    6
session_id            ✓       ✓   ✓           ✓   ✓    5
contract_id           ✓       ✓               ✓   ✓    4
status/state/gate_*   ✓       ✓   ✓                    4(含命名不一致)
findings              ✓           ✓       ✓   ✓        3
required_outputs              ✓               ✓   ✓    3
required_evidence              ✓               ✓   ✓    3
round/attempt             ✓   ✓               ✓        3(含命名不一致)
blocked_reason        ✓       ✓                        2
journal               ✓               ✓                2
summary/gate.reason   ✓       ✓                        2(语义等价)
acceptance_status     ✓   ✓                            2
artifact_name         ✓   ✓                            2
artifact_content      ✓       (输出.md 也算 1)           2
artifact 路径集合         ✓   ✓           ✓            3(分散在多处)
supplemental_*        ✓   ✓                            2(永为空)
```

---

## 四、关键发现

### 1. `session_id` 和 `stage` 是最大的重复项

分别出现在 5 和 6 个文件中。这些值都可以从目录结构中推导（`roles/{stage}/attempt-{N}/` 下方，session_id 在父目录路径中）。

### 2. 合同信息被撕裂在两处

`TC`（task-contract）有 goal / forbidden_actions / evidence_specs，`IC`（input-context）有 acceptance_matrix / constraints / budget / relevant_artifacts。两者共同构成"这个阶段要做什么 + 有什么上下文"。但读的人必须同时打开两个文件才能看到完整合同。

### 3. `status` vs `state` vs `gate_status` — 同一个值三种叫法

SR 里叫 `status`（`completed`），RS 里叫 `state`（`PASSED`），RT 里叫 `gate_status`（`PASSED`）。没有统一术语，代码里处理这三种命名的逻辑散落各处。

### 4. `required_outputs` 和 `required_evidence` 在 TC、IC、RS 各存一份

合同（TC）定义 → 上下文（IC）复制 → 运行时状态（RS）再复制。一份数据三处存储，合同变更时容易不一致。

### 5. IC 的 `relevant_artifacts[]` 是体积炸弹

每个 artifact 都存了 `summary`（完整文本）、`sha256`、`content_chars`。一个 IC 文件可达 15KB+，而 TC 的 `input_artifacts{}` 只存路径。两者职责重叠——TC 说"去哪拿"，IC 直接把内容塞进去了。

### 6. RC（stage-record）几乎全是重复字段

RC 的 9 个字段中：4 个路径可推导、2 个已在 SR 中、1 个可从目录名推导、1 个永远为空、只剩 `archive_path` 稍微有点用但也可推导。

### 7. `supplemental_artifacts` 在两个文件中占位但永远为空

SR 和 RC 都有，output-schema 定义为不允许任何属性。存了个寂寞。

---

## 五、精简建议

### 方案：以 stage-result.json 为唯一输出，合并 run-state 信息

**合并后的 stage-result.json**：

```json
{
  "session_id": "...",
  "stage": "Acceptance",
  "contract_id": "...",
  "attempt": 1,

  "status": "completed",
  "blocked_reason": "",

  "artifact_name": "acceptance_report.md",
  "artifact_path": "/path/to/acceptance_report.md",

  "summary": "Acceptance dry-run result satisfied the stage contract.",
  "journal": "Dry-run executor produced acceptance_report.md for Acceptance.",

  "findings": [],
  "evidence": [...],

  "acceptance_status": "recommended_go",

  "gate": {
    "status": "PASSED",
    "reason": "All contract and evidence gates satisfied.",
    "missing_outputs": [],
    "missing_evidence": [],
    "checked_at": "2026-05-06T10:36:29.736907+00:00"
  },

  "trace": {
    "worker": "dry-run",
    "created_at": "...",
    "updated_at": "...",
    "steps": [
      {"step": "contract_built", "status": "ok", "at": "...", "details": {...}},
      ...
    ]
  }
}
```

### 可删除的文件

| 文件 | 原因 |
|---|---|
| `stage-record.json` | 全部字段可推导或已在 stage-result 中 |
| `execution-journal.md` | = stage-result.journal |
| `review-findings.json` | = stage-result.findings |
| `runtime-trace.json` | 合并进 stage-result.trace |
| `run-state.json` | 合并进 stage-result（gate + timing） |

### 可精简的字段

| 文件 | 删除/合并的字段 | 原因 |
|---|---|---|
| SR | `artifact_content` | 保留 .md 文件即可，SR 只存 `artifact_path` |
| SR | `supplemental_artifacts` | 永远为空 |
| TC | `required_outputs` | 已在 IC 中 |
| TC | `evidence_requirements` | 与 IC.required_evidence 重复 |
| IC | `required_outputs` | 与 TC 重复，保留一处即可 |
| IC | `required_evidence` | 与 TC.evidence_requirements 重复 |
| IC | 删除 `relevant_artifacts[].summary` | 改为引用路径，需要时再读文件 |

### 统一命名

| 当前 | 统一为 |
|---|---|
| SR.status=completed, RS.state=PASSED, RT.gate_status=PASSED | 统一用 `status: "completed"` |
| RC.round_index=1, RS.attempt=1, IC.round_index=1 | 统一用 `attempt` |
| TC.evidence_requirements, IC.required_evidence, RS.required_evidence | 统一用 `required_evidence` |

### 清理效果预估

- 每个 attempt 从 **7 个 JSON/MD 文件** 减少到 **2 个**（stage-result.json + task-contract.json）
- 实际需要保留的 execution-contexts 文件：`task-contract.json`（合同）、`input-context.json`（上下文快照）、`output-schema.json`（精简后的 schema）
- 需要保留的 stage-results 文件：合并后的 `stage-result.json`、`{role}-output-{name}.md`（产物）
- 总体字段去重率约 **40%**（从约 80 个非嵌套字段实例减少到约 50 个）
