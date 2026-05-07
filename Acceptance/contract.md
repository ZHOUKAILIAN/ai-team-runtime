---
name: acceptance
description: 产品级验收，产出自 AI 建议，等人工 Go/No-Go。
---

# Acceptance 契约

## 输入

- `product-requirements.md`
- `acceptance_plan.md`

## 输出

- `acceptance_report.md`

报告必须：验收输入、逐条对照判断、验收方案证据覆盖、产品级观察、剩余风险、建议（`recommended_go` | `recommended_no_go` | `blocked`）、给 CEO 的建议。

## 边界

- 判断用户可见行为，不判断实现细节
- 不重启外部工具、不修改环境（除非显式授权）
- 缺凭证/环境/外部系统 → `blocked`
- 只给 AI 建议，不做最终决策

## 完成

- `acceptance_report.md` 存在
- 明确记录 `recommended_go` | `recommended_no_go` | `blocked`
- 产品级观察对照 PRD 和验收方案
- 返工 finding 含结构化发现和完成信号
