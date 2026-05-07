# Roles 目录冗余文件清理分析

分析对象: `.agent-team/_runtime/sessions/{session_id}/roles/`

## 当前文件结构

每个 role 的每个 attempt 下有 11 个文件（58 个文件，404KB）：

```
roles/{role}/attempt-{N}/
├── execution-contexts/
│   ├── {role}-agent-prompt-bundle.md       # ~10-23KB
│   ├── {role}-input-context.json
│   ├── {role}-output-schema.json
│   └── {role}-task-contract.json
└── stage-results/
    ├── {role}-stage-result.json            # 阶段输出
    ├── {role}-stage-record.json            # 文件路径索引
    ├── {role}-run-state.json               # 运行时状态
    ├── {role}-runtime-trace.json           # 执行步骤追踪
    ├── {role}-execution-journal.md         # 流水日志（一行）
    ├── {role}-review-findings.json         # review 发现列表
    └── {role}-output-{name}.md             # 产物文件
```

---

## 一、内容完全重复的文件（可直接删除）

### 1. `{role}-execution-journal.md`

- **原来是做什么的**: 记录阶段执行的一句话流水日志
- **和谁重叠**: `{role}-stage-result.json` 的 `journal` 字段
- **实际内容对比**: execution-journal.md 内容是 `"Dry-run executor produced acceptance_report.md for Acceptance."`，stage-result.json.journal 完全一样的字符串
- **干掉原因**: 100% 内容重复，只是存储格式不同（.md vs JSON 字段）。保留 JSON 字段即可，不需要额外文件

### 2. `{role}-review-findings.json`

- **原来是做什么的**: 存储阶段 review 发现的缺陷/问题列表
- **和谁重叠**: `{role}-stage-result.json` 的 `findings` 字段 + `{role}-run-state.json` 的 `gate_result.findings` 字段
- **实际内容对比**: 当前 session 中全部是空数组 `[]`。即使有内容，也是 stage-result.json.findings 的完整副本
- **干掉原因**: 三份相同数据。一份在 stage-result.json 里足够。stage-record.json 里还专门维护了 `findings_path` 指向这个文件，删掉后连指针维护都省了

### 3. `{role}-stage-record.json`

- **原来是做什么的**: 一个"路径索引文件"，记录各产物/日志/ findings 的文件系统路径
- **和谁重叠**: 所有路径都可以通过命名约定推导出来
- **包含字段**: stage, artifact_name, artifact_path, journal_path, findings_path, acceptance_status, round_index, supplemental_artifact_paths, archive_path
- **干掉原因**:
  - `artifact_path` / `journal_path` / `findings_path` / `archive_path` 都是按固定规则命名的路径，代码可以直接构造
  - `acceptance_status` 已经在 stage-result.json 里
  - `round_index` = attempt 目录名里的数字
  - `stage` / `artifact_name` 已在 stage-result.json 里
  - 纯元数据文件，不包含任何不可推导的信息

---

## 二、可合并的文件

### 4. `{role}-stage-result.json` + `{role}-run-state.json`

- **stage-result.json 是**: Agent 产出的阶段结果（产物内容、证据、findings、journal）
- **run-state.json 是**: Runtime 驱动器的状态追踪（状态机状态、gate 判定结果、时间戳、路径映射）
- **重叠字段**: `session_id`, `stage`, `contract_id`, `blocked_reason` 都在两个文件里重复；`findings` 在 stage-result 和 run-state.gate_result 里各有一份
- **合并方案**: 将 run-state 的 gate_result / state / worker / timing 等运行时字段并入 stage-result.json，或反过来将 stage-result 作为 run-state 的子对象。两个文件变一个
- **当前冗余度**: 两个文件加起来定义了同一件事的"Agent 视角"和"Runtime 视角"，但使用者读的时候需要跨文件对照

### 5. `{role}-runtime-trace.json` → 合并到 `run-state.json`

- **原来是做什么的**: 记录运行时每个步骤的执行时间和状态（contract_built → context_built → executor_started → ...共 8 步）
- **和谁重叠**: run-state.json 已经有 `created_at` / `updated_at`，state 字段也表达了最终结果
- **干掉原因**: 每一步的 trace 是同一个执行过程的展开版本，可以和 run-state 合并为一个 `steps` 数组。分开存储让读取者需要额外一次文件 IO

---

## 三、内容冗余但格式不同（保留其一）

### 6. `{role}-output-{name}.md` 中的内容在 `stage-result.json.artifact_content` 中也有

- **原来是做什么的**: `.md` 文件是阶段的规范产物（如 acceptance_report.md），`artifact_content` 是 stage-result.json 中嵌入的完整产物文本
- **重叠情况**: 两个地方存了完全相同的产物内容
- **建议**: 保留 `.md` 文件为规范产物（方便直接阅读、diff），**从 stage-result.json 中删除 `artifact_content` 字段**，改为只存 `artifact_path`。避免大 JSON 里嵌大段 Markdown

---

## 四、体积大且可选的调试产物

### 7. `{role}-agent-prompt-bundle.md`

- **原来是做什么的**: 发送给 LLM 的完整 prompt 的快照，用于调试/追溯
- **大小**: 10-23KB 每个，5 个文件共 ~95KB（占 roles 目录 404KB 的 23%）
- **和谁重叠**: 内容是 `task-contract.json` + `input-context.json` + `output-schema.json` + 固定模板渲染出来的 Markdown。所有信息都可以从另外三个 JSON 文件中完整还原
- **干掉原因**: 纯派生文件。如果真想保留用于调试，应该做成 **opt-in**（如 `--debug` 或 `--trace-prompts` 时才写入），而不是每次都写
- **补充**: runtime-trace.json 的 `stage_run_acquired` 步骤里记录了 `skill_injection.included_in_prompt: false`，说明 prompt bundle 并不总对应实际发送的 prompt（因为可能有 skill 注入），进一步降低了它的追溯价值

### 8. `{role}-output-schema.json`（内容层面冗余，非文件层面）

- **原来是做什么的**: 定义 Agent 输出必须符合的 JSON Schema
- **问题不在于删文件，而在于 schema 内容本身冗余**（详见之前讨论）
- **必须字段过多**: 11 个 required 顶层字段，findings 子对象 11 个 required 字段，evidence 子对象 7 个 required 字段
- **`supplemental_artifacts`**: 定义为 `additionalProperties: false` + `properties: {}`，永远只能是 `{}`，纯噪音
- **`blocked_reason`**: 只在 status=blocked 时有意义却标记为 required
- **`acceptance_plan_content`**: 是输入而非输出，放在 output schema 里语义不对

---

## 五、孤儿文件（不完整的 attempt 残留）

### 9. `development/attempt-003/` 和 `development/attempt-004/`

- **原来是做什么的**: Dev 阶段的第 3、4 次尝试
- **实际内容**: 每个目录下只有一个 `execution-contexts/development-input-context.json`，没有 stage-results
- **干掉原因**: 输入上下文已构建但从未执行（没有 stage-result、没有 run-state），说明这些 attempt 根本没有跑起来。是中断/重试留下的垃圾目录

---

## 清理建议汇总

| 优先级 | 文件 | 操作 | 理由 |
|---|---|---|---|
| **P0** | `execution-journal.md` | 删除 | 与 stage-result.json.journal 100% 重复 |
| **P0** | `review-findings.json` | 删除 | 与 stage-result.json.findings 100% 重复 |
| **P0** | `stage-record.json` | 删除 | 纯路径索引，所有路径可推导 |
| **P0** | 不完整 attempt 目录 | 删除 | 孤儿数据，从未执行 |
| **P1** | `stage-result.json` + `run-state.json` | 合并 | 两个文件描述同一件事的两个视角 |
| **P1** | `runtime-trace.json` | 合并进 run-state | 同一次执行的生命周期数据 |
| **P1** | `agent-prompt-bundle.md` | 改为 opt-in | 派生文件，95KB，调试时才需要 |
| **P2** | `stage-result.json.artifact_content` | 改为 artifact_path | 避免大 JSON 嵌大段文本 |
| **P2** | `output-schema.json` | 精简 required 字段 | 去掉永远为空的字段和语义不对的字段 |

**清理后预期**: 每个 attempt 从 11 个文件减少到 4-5 个，总体积减少约 50-60%。
