# Agent 已迁出

**日期**：2026-09-10  
**新仓**：<https://github.com/shujingyin510/sanyan-agent>

## 为什么

- 本体聚焦语言 / 编译器 / VM / 约束系统
- Agent 自更新线已冻结，独立仓便于只读维护与将来解冻
- 减 monorepo 体量与 CI 噪音

## 依赖

`sanyan-agent` 通过 `pip install sanyan` 使用本仓运行时（`core` / `ops` / `sugar` / `vm`），**不复制语言实现**。

## 本仓现状

- `agent_system/` 代码与 Agent 专用测试已移除
- CLI 的 `sanyan agent` / `sanyan bench` 子命令改为指路提示
- 设计决策 / 死因考古 / 冻结条件 → 知识库 `sanyan-obsidian`
