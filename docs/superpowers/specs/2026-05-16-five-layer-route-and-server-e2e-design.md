# 五层路由与服务端 E2E Runtime 设计

## 背景

当前的五层 runtime 虽然已经引入了 `Route`、`ProductDefinition`、`ProjectRuntime`、`TechnicalDesign` 等阶段，但实际执行仍然更接近固定九阶段流水线。`Route` 产出了分类结果，却没有真正驱动后续阶段选择，导致几乎所有需求都会先经过 `ProductDefinition`，即使它只是纯 `L2` 实现修改或 `L3` 项目落地调整。

同时，runtime 已经在 prompt 和 contract 中要求“服务端改动要做端到端验证”，但这还只是原则性要求，没有形成稳定的项目级协议。当前缺少一套明确机制来说明：

- 服务如何启动
- 如何连接测试环境
- API 流程如何执行
- 如何收集独立验证证据

## 问题

1. `Route` 目前只有描述作用，没有真正控制 stage 选择。
2. `ProductDefinition` 目前几乎只有一种有效路径：产出 delta 并等待审批，这让 `L1` 看起来像每个任务都必须经过的门。
3. 服务端端到端验证的长期配置应该放在哪一层，目前没有清晰正式规则。
4. 验证政策、项目运行配方、本地私密连接信息，当前没有在 `L3`、`L4`、`L5` 之间清晰拆开。

## 目标

- 让 `Route` 成为真正的流程路由器。
- 只有当需求变更稳定产品语义时，才进入 `L1` 审批。
- 保持“下层不能静默改写上层真相”的五层边界。
- 增加一套由仓库 `L3` 正式声明、由 runtime 执行的服务端 E2E 验证协议。
- 让测试环境访问保持“项目本地可用、但不进入共享版本历史”。

## 非目标

- 本次变更不设计 canonical `L1/L3/L4` 文档的自动回写或自动晋升机制。
- 本次变更不构建一个通用外部测试框架。
- 本次变更不允许把测试环境私密连接信息写入仓库追踪文件。
- 本次变更不重新发明一套新的层级分类法。

## 核心决策

### 层级职责

- `L1 ProductDefinition`
  - 负责稳定产品语义、核心对象、API/业务含义、长期验收语义。
  - 例如：某个接口成功是否代表订单已创建并进入某个业务状态。
  - 不负责服务启动、测试环境接入、验证私密信息。

- `L2 ProductImplementation`
  - 负责代码、测试、运行时行为、实现报告、实现 drift 报告。
  - 可以实现，也可以报告 drift。
  - 不能把实现现实直接晋升为 `L1` 产品真相。

- `L3 ProjectRuntime`
  - 负责长期存在的项目运行默认值，包括服务端端到端验证运行配方。
  - 服务启动命令、healthcheck、默认 API 验证流程、依赖服务、需要哪些本地私密配置项，都属于这一层。

- `L4 Governance`
  - 负责验证政策与流程门禁。
  - 什么时候必须跑 E2E、必须提交哪些证据、什么情况下必须 `blocked`，都属于这一层。

- `L5 LocalControl`
  - 负责项目级本地私有运行配置，以及 session 级执行现场。
  - 真实测试环境 URL、token、cookie、私有 header、本地端口覆写等属于这一层，并且不得提交。

### ProductDefinition 三态结果

`ProductDefinition` 不应再表现得像一个对所有任务都生效的统一审批门。它必须显式产出以下三种结果之一：

- `no_l1_delta`
  - 本次需求不改变稳定产品语义。
  - 不进入 `L1` 审批等待状态。

- `l1_delta_pending_approval`
  - 本次需求提出了真实的 `L1` 语义变更候选。
  - 进入现有人工审批门。

- `blocked_missing_decision`
  - 实现前缺失必要的产品决策，不能靠猜。
  - 流程直接阻塞，并给出聚焦问题。

### Route 作为执行路由器

`Route` 仍然必须先执行，但它不再只是 intake 备注阶段，而要变成真正的执行控制器。

`route-packet.json` 必须成为以下流程决策的来源：

- `affected_layers`
- `required_stages`
- `stage_decisions`
- `baseline_sources`
- `red_lines`
- `verification_mode`
- `unresolved_questions`

`Route` 需要明确判断每个 stage 的状态：

- `required`
- `skipped`
- `blocked`

状态机必须根据“下一个 required stage”推进，而不是继续沿用固定线性链路。

### 服务端 E2E 验证归属

服务端端到端验证采用“仓库声明，runtime 执行”的模式：

- 仓库在 `L3` 声明运行配方
- runtime 加载并执行该配方
- `L4` 检查是不是用了正确的配方和正确的证据标准
- 本地私密连接信息从 `L5` 读取

这样做的目的，是避免每个任务都临场发明一套验证方式，也避免把私密测试环境信息误写进共享文档。

## 流程变更

### 当前流程问题

现在的流程在执行效果上更接近：

`Route -> ProductDefinition -> wait -> ProjectRuntime -> TechnicalDesign -> wait -> Implementation -> Verification -> GovernanceReview -> Acceptance -> SessionHandoff`

这条链路只适合真正有 `L1` 语义变更的需求，对于普通 `L2/L3` 工作过重。

### 新流程语义

`Route` 永远先执行。

`Route` 完成后，状态机从 `required_stages` 中选取下一个真正需要执行的 stage。

示例：

- 纯 `L2` bugfix：
  - `Route -> TechnicalDesign -> Implementation -> Verification -> GovernanceReview -> Acceptance -> SessionHandoff`

- `L3` 运行/部署/配置调整：
  - `Route -> ProjectRuntime -> TechnicalDesign -> Implementation -> Verification -> GovernanceReview -> Acceptance -> SessionHandoff`

- 真正的 `L1` 产品语义变更：
  - `Route -> ProductDefinition(等待审批) -> 如有需要进入 ProjectRuntime -> TechnicalDesign -> Implementation -> Verification -> GovernanceReview -> Acceptance -> SessionHandoff`

### Route Packet 要求

`route-packet.json` 至少要支持以下语义：

```json
{
  "affected_layers": ["L2", "L3", "L4", "L5"],
  "required_stages": [
    "ProjectRuntime",
    "TechnicalDesign",
    "Implementation",
    "Verification",
    "GovernanceReview",
    "Acceptance",
    "SessionHandoff"
  ],
  "stage_decisions": {
    "ProductDefinition": {
      "decision": "skipped",
      "reason": "no_l1_delta"
    },
    "ProjectRuntime": {
      "decision": "required",
      "reason": "server_e2e_recipe_changed"
    }
  },
  "verification_mode": "server_e2e_required",
  "baseline_sources": [
    "docs/project-runtime/verification.md",
    "docs/governance/verification-policy.md"
  ],
  "red_lines": [
    "lower_layers_must_not_rewrite_upper_layer_truth",
    "do_not_promote_l5_or_research_to_formal_truth"
  ],
  "unresolved_questions": []
}
```

字段名后续实现可以调整，但上述语义必须保留。

## 服务端 E2E 验证设计

### L3 正式工件

新增两类 `L3` 正式验证运行工件：

- `docs/project-runtime/verification.md`
  - 给人看的验证运行说明。
  - 说明本项目服务端 E2E 怎么做、覆盖哪些服务、依赖什么、每条 flow 在验证什么语义、哪些数据只能通过接口准备。

- `docs/project-runtime/verification.yaml`
  - 给 runtime 执行的机器配置。

推荐顶层结构：

- `service_profiles`
- `environment_requirements`
- `data_policy`
- `flows`
- `evidence`

示例结构：

```yaml
service_profiles:
  api:
    workdir: apps/api
    start_command: npm run dev:test
    healthcheck:
      url: http://127.0.0.1:38080/health
      expect_status: 200
      timeout_seconds: 90
    dependencies:
      - redis
      - mysql

environment_requirements:
  profile: integration-test
  required_private_keys:
    - TEST_BASE_URL
    - TEST_AUTH_TOKEN
    - TEST_DB_READONLY_DSN

data_policy:
  db_readonly: true
  mutation_via_api_only: true

flows:
  - id: create_order
    description: 通过公开 API 创建订单并确认结果状态
    steps:
      - kind: request
        request:
          method: POST
          path: /api/orders
          body_template: order_create_basic
      - kind: assert_response
        expect_status: 200
        expect_json_path:
          - path: $.code
            equals: 0
      - kind: request
        request:
          method: GET
          path: /api/orders/${response.body.data.id}
      - kind: assert_response
        expect_status: 200
      - kind: readonly_db_check
        query_id: order_status_by_id

evidence:
  save_request_response: true
  save_healthcheck_output: true
  save_readonly_db_results: true
```

### L4 治理工件

新增一个正式治理工件：

- `docs/governance/verification-policy.md`

这份策略文档必须定义：

- 哪些变更类型需要 `server_e2e_required`
- 通过时必须具备哪些证据
- 哪些情况必须 `blocked`
- 哪些场景允许退化为 static 或 unit-only 验证

必须明确的治理规则：

- 任何影响 API 行为、持久化行为、编排行为、请求/响应契约的服务端行为变更，都必须跑 server E2E，除非 route packet 明确说明为什么可以用更窄的验证模式。
- `Verification` 的证据必须独立于 `Implementation` 自检证据。
- 允许使用只读数据库验证。
- 验证阶段禁止直接写数据库。
- 如果需要准备或清理测试数据，必须通过已声明的 API flow 执行，不能通过数据库直改。

### L5 本地私有配置

新增一个不进版本库的项目级本地私有配置文件：

- `.agent-team/local/verification-private.json`

这个文件是项目级长期存在、本地可复用、但不共享的配置。

它可以包含：

- 真实 base URL
- token
- cookie
- 私有 header
- 本地端口覆写
- 只读数据库 DSN

它不应该包含：

- session 总结
- 治理政策
- 共享产品真相

推荐结构：

```json
{
  "profiles": {
    "integration-test": {
      "TEST_BASE_URL": "https://test-api.example.internal",
      "TEST_AUTH_TOKEN": "redacted-local-secret",
      "TEST_DB_READONLY_DSN": "mysql://readonly@host/db"
    }
  }
}
```

session 级执行现场继续保留在现有 `.agent-team/<session>/...` 目录树下。

### Verification 执行顺序

当 `verification_mode: server_e2e_required` 时，`Verification` 应固定按以下顺序执行：

1. 读取 `L4` 验证政策
2. 加载 `L3` 验证配方
3. 从 `L5` 解析所需本地私有配置
4. 启动声明的 service profile
5. 执行 healthcheck
6. 执行声明的 API flow
7. 收集声明的证据
8. 产出 `verification-report.md` 和结构化证据文件

### 通过所需证据

至少包括：

- 服务启动命令及其退出状态或进程状态
- healthcheck 结果
- 每个 flow step 的请求和响应证据
- 任何声明的只读验证输出
- 最终 `passed / failed / blocked` 结论

### 必须 blocked 的条件

以下情况 `Verification` 必须返回 `blocked`：

- `L5` 缺失必需的本地私有连接信息
- `L3` 配方缺失、格式非法、或者对必需 flow 描述不完整
- service profile 无法启动或无法通过 healthcheck
- 验证需要数据变更，但没有声明对应 API flow
- 无法采集独立证据

## Runtime 与状态变更

### Route / Stage Machine

- 状态机消费 `route-packet.json` 的 `required_stages`
- 新增 `skipped` 或 `not_applicable` 之类的 stage 状态
- 从“固定 stage 跳转”改成“查找下一个 required stage”
- 只有真正 required 的 stage 才会保留对应 wait state

### ProductDefinition 结果契约

新增显式字段 `product_definition_outcome`，取值为：

- `no_l1_delta`
- `l1_delta_pending_approval`
- `blocked_missing_decision`

行为规则：

- `no_l1_delta`：跳过 `WaitForProductDefinitionApproval`
- `l1_delta_pending_approval`：进入审批等待
- `blocked_missing_decision`：进入 blocked，并附带聚焦问题

### Verification 结果契约

为 runtime 驱动的服务端 E2E 增加显式验证元数据：

- `verification_mode`
- `service_profile`
- `flow_ids`
- `evidence_paths`
- `blocked_reason`

## 文件与变更面

预期涉及的仓库改动：

- Runtime 逻辑
  - `agent_team/stage_machine.py`
  - `agent_team/runtime_driver.py`
  - `agent_team/stage_inputs.py`
  - `agent_team/execution_context.py`
  - `agent_team/stage_policies.py`
  - `agent_team/models.py`
  - `agent_team/state.py`
  - `agent_team/cli.py`

- 角色 contract 与 guidance
  - `agent_team/assets/roles/Route/contract.md`
  - `agent_team/assets/roles/Route/context.md`
  - `agent_team/assets/roles/ProductDefinition/contract.md`
  - `agent_team/assets/roles/ProductDefinition/context.md`
  - `agent_team/assets/roles/ProjectRuntime/contract.md`
  - `agent_team/assets/roles/ProjectRuntime/context.md`
  - `agent_team/assets/roles/Verification/contract.md`
  - `agent_team/assets/roles/Verification/context.md`
  - `agent_team/assets/roles/GovernanceReview/contract.md`

- 新增项目正式工件
  - `docs/project-runtime/verification.md`
  - `docs/project-runtime/verification.yaml`
  - `docs/governance/verification-policy.md`

- 本地非版本化支持
  - `.agent-team/local/verification-private.json` 模板或本地生成文件
  - 如有需要，对 `.gitignore` 进行补充

- 测试
  - `tests/test_stage_machine.py`
  - `tests/test_runtime_driver.py`
  - `tests/test_execution_context.py`
  - `tests/test_stage_policies.py`
  - `tests/test_cli.py`
  - 如有必要，新增 route-driven skipping 和 verification recipe loading 的聚焦测试

## 验收标准

- 一个没有 `L1` 语义变更的任务，不会卡在 `ProductDefinition` 审批门。
- `Route` 的输出能够真正决定下一个执行阶段。
- `ProductDefinition` 能显式返回 `no_l1_delta`、`l1_delta_pending_approval`、`blocked_missing_decision`。
- 服务端验证可以由 `L3` 声明、由 runtime 执行，同时不把私密测试环境信息写入仓库追踪文件。
- `L4` 可以强制要求何时必须跑 E2E，以及必须提交哪些证据。
- 验证阶段数据库只读，任何测试数据准备必须通过接口 flow 完成。

## 风险

- `Route` 权限增强后，如果分类错误，可能错误跳过本应执行的上层审查。
- 如果验证配方 schema 设计过重，runtime 容易被做成半个测试框架。
- 如果本地环境纪律不足，`L5` 私有配置缺失或过期，验证仍会频繁 blocked。

## 缓解

- 继续要求 `GovernanceReview` 检查 skipped stage 是否合理。
- 第一版验证 schema 只覆盖启动、healthcheck、API flow、证据采集，不追求过度抽象。
- 所有不确定条件都 fail closed，返回 `blocked`，而不是靠 agent 猜测。

## 后续开放项

- session delta 如何正式回写/晋升为 canonical `L1/L3/L4`，留待后续单独设计。
- `Route` 如何更强地感知 diff、文件模式和变更类型，从而更稳地决定 `verification_mode`，也留待后续增强。
