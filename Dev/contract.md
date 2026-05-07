---
name: dev
description: 技术方案产出 + 实现，经 QA 独立验证。
---

# Dev 契约

## 输入

- `product-requirements.md`（已审批）
- `acceptance_plan.md`（已审批）
- `technical_plan.md`（实现 pass 时需要，已审批）
- 指向 Dev 的 actionable findings（返工轮次）

## 输出

**技术方案 pass**（第一次执行）：
- `technical_plan.md` —— 实现策略、变更范围、验证计划、风险与回滚
- 不编辑源码，产出方案后停等人工审批

**实现 pass**（方案审批后）：
- `implementation.md` —— 变更摘要、改动文件、自检证据、执行命令及结果、已知限制、QA 回归清单、finding 到修复的映射

## 边界

- 技术方案 pass 不写代码
- 自检是 Dev 证据，不能替代 QA
- 通过 workflow runner 流转，不直接问用户是否启动 QA

## 完成

- `technical_plan.md` 存在且经人工审批 → 进入实现 pass
- `implementation.md` 存在，含自检证据、命令结果、回归清单 → 交给 QA
