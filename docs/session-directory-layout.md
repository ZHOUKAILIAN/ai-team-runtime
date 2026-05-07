# Session 目录结构说明

以一个跑完 Product → Dev(技术方案+实现) → QA → Acceptance 完整管线的 session 为例。

```
20260507T081540573744Z-hello-js/           # session 目录，命名格式: {UTC时间戳}Z-{需求摘要}
├── session.json                           # session 元信息：请求原文、stage 引用、人工决策、findings 汇总
├── workflow_summary.json                  # 当前流程快照：状态、阶段、各 stage 产物路径、阻塞原因
├── events.jsonl                           # 事件流日志，每行一个 JSON 事件（创建、stage 开始/结束、决策等）
└── roles/                                 # 各角色执行记录
    ├── product/attempt-001/               # Product 角色，第一次执行
    │   ├── execution-contexts/
    │   │   └── product-task-contract.json # 阶段契约：目标、必需产出、禁止动作、角色上下文（context+contract）
    │   └── stage-results/
    │       ├── product-stage-result.json  # 阶段执行记录：run 状态、gate 结果、trace steps、stage_result 信封
    │       ├── product-output-product-requirements.md  # 主产物：PRD 文档
    │       └── supplemental-artifacts/
    │           └── acceptance_plan.md     # 附加产物：验收方案（Product 专属）
    ├── dev/attempt-001/                   # Dev 第一次执行 = 技术方案
    │   ├── execution-contexts/
    │   │   ├── dev-input-context.json     # 执行上下文：上游产物摘要、验收矩阵、findings、预算
    │   │   └── dev-task-contract.json     # 阶段契约：required_outputs=["technical_plan.md"]
    │   └── stage-results/
    │       ├── dev-stage-result.json      # 执行记录（含 gate_result、trace steps）
    │       └── dev-output-technical_plan.md  # 主产物：技术方案文档
    ├── dev/attempt-002/                   # Dev 第二次执行 = 实现（技术方案审批通过后）
    │   ├── execution-contexts/
    │   │   └── dev-task-contract.json     # 阶段契约：required_outputs=["implementation.md"]
    │   └── stage-results/
    │       ├── dev-stage-result.json      # 执行记录
    │       └── dev-output-implementation.md  # 主产物：实现报告（变更摘要、自检证据、QA 回归清单）
    ├── qa/attempt-001/                    # QA 独立验证
    │   ├── execution-contexts/
    │   │   └── qa-task-contract.json      # 阶段契约：验证 Dev 交付物是否满足验收方案
    │   └── stage-results/
    │       ├── qa-stage-result.json       # 执行记录
    │       └── qa-output-qa_report.md     # 主产物：QA 报告（测试用例、验证结果、缺陷、结论）
    └── acceptance/attempt-001/            # Acceptance 产品级验收
        ├── execution-contexts/
        │   └── acceptance-task-contract.json  # 阶段契约：对照 PRD 验证最终产物
        └── stage-results/
            ├── acceptance-stage-result.json   # 执行记录
            └── acceptance-output-acceptance_report.md  # 主产物：验收报告 + Go/No-Go 建议
```

---

## 1. session.json

```jsonc
{
  "session_id": "20260507T081540573744Z-hello-js",  // 唯一标识，时戳 + 需求摘要
  "request": "hello js",                              // 原始用户需求
  "created_at": "2026-05-07T08:15:40+00:00",
  "session_dir": ".../_runtime/sessions/{id}",        // 运行时存储（机器消费）
  "artifact_dir": ".../.agent-team/{id}",             // 对外产物（人类阅读）
  "initiator": "human",                               // human | agent
  "stage_runs": [                                     // 轻量引用，完整数据在 per-role 文件
    {
      "run_id": "product-run-1",                      // 唯一标识: {stage}-run-{N}
      "stage": "Product",
      "attempt": 1,                                   // 第几次尝试（从 1 开始）
      "state": "PASSED",                              // RUNNING → SUBMITTED → VERIFYING → PASSED | FAILED | BLOCKED
      "created_at": "2026-05-07T08:15:40.577944+00:00",
      "updated_at": "2026-05-07T08:15:40.591316+00:00",
      "result_path": ".../product-stage-result.json"  // 完整记录文件路径
    }
  ],
  "stage_records": [                                  // 每个通过 gate 的 stage 产物索引
    {
      "stage": "Product",
      "artifact_name": "product-requirements.md",
      "artifact_path": ".../product-requirements.md", // public artifact dir 中的路径
      "round_index": 1
    }
  ],
  "findings": [],                                     // 所有 stage 产生的缺陷（跨 stage 返工依据）
  "acceptance_status": "recommended_go",              // 最终验收结论: recommended_go | recommended_no_go | blocked
  "human_decision": "go"                              // 最后一次人工决策
}
```

---

## 2. workflow_summary.json

```jsonc
{
  "session_id": "20260507T081540573744Z-hello-js",
  "runtime_mode": "runtime_driver",                   // runtime_driver | runtime_driver_interactive
  "current_state": "WaitForHumanDecision",            // 状态机当前状态
  "current_stage": "Acceptance",                      // 当前所在角色
  "prd_status": "drafted",                            // pending → drafted
  "dev_status": "completed",                          // pending → planning → plan_drafted → plan_approved → completed
  "qa_status": "passed",                              // pending → passed | failed
  "acceptance_status": "recommended_go",              // pending → recommended_go | recommended_no_go | blocked
  "human_decision": "go",                             // pending → go | no_go | rework
  "qa_round": 1,                                      // QA 返工轮次
  "blocked_reason": "",                               // 阻塞原因（非空时流程停在此处）
  "artifact_paths": {                                 // 各阶段产物 public 路径
    "product": ".../product-requirements.md",
    "acceptance_plan": ".../acceptance_plan.md",
    "technical_plan": ".../technical_plan.md",
    "dev": ".../implementation.md",
    "qa": ".../qa_report.md",
    "acceptance": ".../acceptance_report.md"
  }
}
```

### 状态机流转图

```
Product → WaitForCEOApproval ──go──→ Dev (technical_plan)
  → WaitForTechnicalPlanApproval ──go──→ Dev (implementation)
  → QA → Acceptance → WaitForHumanDecision ──go──→ Done
```

---

## 3. events.jsonl

每行一个 JSON 事件，按时间顺序追加。事件类型：

| kind | 触发时机 |
|---|---|
| `session_created` | session 初始化 |
| `execution_context_saved` | 执行上下文写入磁盘 |
| `runtime_driver_stage_started` | runtime 开始驱动一个 stage |
| `stage_result_recorded` | stage 产物写入完成 |
| `workflow_state_changed` | 状态机跳转（人工决策后） |
| `human_decision_recorded` | 人工 go/rework/no-go 记录 |

---

## 4. {role}-stage-result.json

每个 stage 执行的核心记录，每个 attempt 一份。结构对所有 stage 一致。

```jsonc
{
  "run_id": "dev-run-1",                              // 本轮执行唯一标识
  "session_id": "20260507T081540573744Z-hello-js",
  "stage": "Dev",                                     // 角色名
  "state": "PASSED",                                  // 本轮状态: RUNNING → SUBMITTED → VERIFYING → PASSED | FAILED | BLOCKED
  "contract_id": "4073c0964595f084",                  // 匹配 task-contract.json 中的 contract_id，防串
  "attempt": 1,                                       // 当前角色第几次尝试
  "required_outputs": ["technical_plan.md"],          // 本轮必须产出的文件
  "required_evidence": ["implementation_plan"],        // 本轮必须提供的证据名
  "worker": "dry-run",                                // 执行器: dry-run | command | codex-exec
  "created_at": "2026-05-07T08:15:40.746037+00:00",
  "updated_at": "2026-05-07T08:15:40.757950+00:00",
  "blocked_reason": "",                               // 被阻塞时的原因

  "artifact_paths": {                                 // 产物索引
    "technical_plan": ".../public/technical_plan.md", // 对人对外的产物路径
    "stage_result": ".../dev-stage-result.json"       // 自身路径
  },

  "stage_result": {                                   // 执行器产出的结果信封
    "status": "completed",                            // completed | failed | blocked
    "artifact_name": "technical_plan.md",             // 主产物文件名
    "artifact_path": ".../dev-output-technical_plan.md", // 归档副本路径
    "journal": "Dry-run executor produced ...",       // 执行摘要
    "summary": "Dev dry-run result satisfied ...",    // 结果简述
    "findings": [],                                   // 本轮发现的缺陷（返工时非空）
    "evidence": [                                     // 本轮产生的证据
      {
        "name": "implementation_plan",                // 证据名（对应 contract.evidence_requirements）
        "kind": "report",                             // 证据类型: artifact | report | command | screenshot
        "summary": "Technical plan identifies ...",   // 证据摘要
        "producer": "runtime-driver"                  // 证据来源
      }
    ]
  },

  "steps": [                                          // 不可跳过的 trace 链路（8 步）
    //  1. contract_built      阶段契约生成完毕
    //  2. execution_context_built  上下文构建完毕
    //  3. stage_run_acquired  执行环境准备完毕
    //  4. executor_started    执行器开始工作
    //  5. executor_completed  执行器返回结果
    //  6. result_submitted    结果提交到 store
    //  7. gate_evaluated      门禁检查
    //  8. state_advanced      状态机推进
  ],

  "gate_result": {                                    // 门禁检查结果
    "status": "PASSED",                               // PASSED | FAILED | BLOCKED
    "reason": "All contract and evidence gates satisfied.",
    "missing_outputs": [],                            // 缺失的产物
    "missing_evidence": [],                           // 缺失的证据
    "findings": [],                                   // gate 本身发现的问题
    "checked_at": "2026-05-07T08:15:40.755454+00:00"
  }
}
```

### 各 stage 差异对比

| 字段 | Product | Dev attempt-001 (tech plan) | Dev attempt-002 (impl) | QA | Acceptance |
|---|---|---|---|---|---|
| `required_outputs[0]` | `product-requirements.md` | `technical_plan.md` | `implementation.md` | `qa_report.md` | `acceptance_report.md` |
| `required_evidence[0]` | `explicit_acceptance_plan` | `implementation_plan` | `self_code_review` | `independent_verification` | `product_level_validation` |
| `stage_result.artifact_name` | `product-requirements.md` | `technical_plan.md` | `implementation.md` | `qa_report.md` | `acceptance_report.md` |
| `stage_result.acceptance_status` | `""` | `""` | `""` | `""` | `"recommended_go"` |
| `artifact_paths` key | `product` | `technical_plan` | `dev` | `qa` | `acceptance` |

---

## 5. {role}-task-contract.json

```jsonc
{
  "session_id": "20260507T081540573744Z-hello-js",
  "stage": "Dev",                                     // 当前角色
  "contract_id": "4073c0964595f084",                  // 唯一契约 ID（内容哈希一下）
  "goal": "As Dev, draft a concrete technical ...",   // 本轮要完成的目标（来自 stage_policies.py）
  "input_artifacts": {                                // 上游交付物（仅 public 路径）
    "product": ".../product-requirements.md",
    "acceptance_plan.md": ".../acceptance_plan.md"
  },
  "required_outputs": ["technical_plan.md"],          // 必须产出的文件
  "forbidden_actions": [                              // 禁止动作
    "must_not_change_stage_order",
    "must_not_skip_required_artifacts",
    "must_not_claim_workflow_done"
  ],
  "evidence_requirements": ["implementation_plan"],   // 必须提供的证据名
  "evidence_specs": [                                 // 证据规格
    {
      "name": "implementation_plan",                  // 证据名
      "required": true,                               // 是否必需
      "allowed_kinds": ["artifact", "report"],        // 允许的证据类型
      "required_fields": ["summary"],                 // 必须填写的字段
      "minimum_items": 1                              // 最少提供几份
    }
  ],
  "role_context": "# Role Context\n\n..."             // 角色的 context.md + contract.md 全文拼接
}
```

### 各 stage task-contract 差异

| 字段 | Product | Dev tech plan | Dev impl | QA | Acceptance |
|---|---|---|---|---|---|
| `required_outputs[0]` | `product-requirements.md` | `technical_plan.md` | `implementation.md` | `qa_report.md` | `acceptance_report.md` |
| `evidence_requirements[0]` | `explicit_acceptance_plan` | `implementation_plan` | `self_code_review` | `independent_verification` | `product_level_validation` |
| `input_artifacts` 数量 | 0 | 2 (product, acceptance_plan) | 3 (+technical_plan) | 3 | 2 |
| `role_context` 大小 | ~8.6K | ~5K | ~5K | ~7.5K | ~5.8K |

---

## 6. {role}-input-context.json

执行上下文，为 worker 提供当前 session 的快照。

```jsonc
{
  "session_id": "20260507T081540573744Z-hello-js",
  "stage": "Dev",                                     // 当前角色
  "round_index": 2,                                   // 当前 attempt 编号
  "context_id": "5b1bde32ef620c16",                   // 唯一上下文 ID
  "contract_id": "33b7bbfd85272a27",                  // 匹配 task-contract

  // 上游产物摘要（已截断到 4000 字符）
  "original_request_summary": "hello js",
  "approved_prd_summary": "# 需求方案\n\n...",
  "approved_acceptance_plan_content": "# 验收方案\n\n...",
  "approved_tech_plan_content": "# 技术方案\n\n...",  // 仅 Dev impl / QA / Acceptance 有

  "acceptance_matrix": [                              // 验收标准清单
    {"id": "AC-001", "criterion": "...", "source": "acceptance_plan"}
  ],
  "constraints": [],                                  // 来自 AcceptanceContract 的约束
  "required_outputs": ["implementation.md"],          // 本轮必需产物
  "required_evidence": ["self_code_review"],          // 本轮必需证据

  "relevant_artifacts": [                             // 上游产物引用（含哈希校验）
    {
      "name": "product",                              // 产物名
      "sha256": "b97f2888144f0862...",                // 内容哈希（防篡改）
      "content_chars": 197,                           // 内容长度
      "artifact_path": ".../product-requirements.md"  // 绝对路径
    }
  ],

  "actionable_findings": [],                          // 指向本轮 target_stage 的返工 finding

  "repo_context_summary": "doc map: ...",             // 项目文档结构摘要

  "role_context_digest": "sha256:8d86d2631595db...; chars:3814",  // role_context 的哈希指纹

  "budget": {                                         // 上下文预算约束
    "max_context_tokens": 24000,
    "max_artifact_snippet_chars": 4000,               // 上游产物最大截断长度
    "max_findings": 20                                // 最多注入的返工 findings 数量
  }
}
```

---

## 文件生命周期

| 文件 | 谁写入 | 写入时机 |
|---|---|---|
| `session.json` | `StateStore._save_stage_run()`, `append_stage_record()`, `set_human_decision()`, `record_feedback()` | 每次 stage run 状态变更、stage 产物记录、人工决策时 |
| `workflow_summary.json` | `StateStore.save_workflow_summary()` | session 创建、每次 stage gate 通过/失败、人工决策后 |
| `events.jsonl` | `StateStore.record_event()` | 每次状态变更事件追加一行 |
| `*-task-contract.json` | `runtime_driver._execute_stage()` | 每个 stage 执行前 |
| `*-input-context.json` | `StateStore.save_execution_context()` | 每个 stage 执行前 |
| `*-stage-result.json` | `StateStore._save_stage_run()` | stage run 状态每次变更 |
| `*-output-*.md` | `StateStore.submit_stage_run_result()` | stage 执行完成后 |

---

## 与旧格式的差异

| | 旧 | 新 |
|---|---|---|
| `output-schema.json` | 每个 attempt 存一份 | 项目级一份（`.agent-team/output-schema.json`） |
| `session.json` 中 `stage_runs[]` | 完整 StageRunRecord (~4K/条) | 轻量引用（run_id + result_path） |
| 角色目录名 | `development`、`quality-assurance` | `dev`、`qa` |
| 静态 `{Role}/memory.md` | 存在（boilerplate） | 已删除，统一用 `.agent-team/memory/{Role}/` |
| artifact archive | `record_stage()` 双写 | 只写 public dir |
| 无效 attempt | 残留空壳目录 | `create_stage_run()` 时自动清理 |
