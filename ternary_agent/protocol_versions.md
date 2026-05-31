# 协议版本记录

## v1.0 — 2026-05-30

### 核心协议 §1–§12（嵌入 prompts.san）

| 节号 | 主题 | 说明 |
|---|---|---|
| §1 | 基础状态系统 | 5 种认知态（AFFIRM/UNCERT/CONFLICTED/PENDING/NEGATE）+ 5 种执行态（READY/NEED_TOOL/NEED_HUMAN/BLOCKED/UNSAFE） |
| §2 | 五态到三态映射 | AFFIRM→真(1), NEGATE→假(-1), UNCERT/CONFLICTED/PENDING→可能(0) |
| §3 | 犹豫保护 | 次数上限 + 信息增益阈值 + 高风险直接拒绝 |
| §4 | 传播规则 | 上游假→下游假，上游可能+下游真→降为可能 |
| §5 | 上下文压缩 | 相关保留全文，不相关摘要（前50字），关键词命中≥2判定相关 |
| §6 | 冲突记录 | 双源不一致记录（源A、源B、主题、时间戳） |
| §7 | TTL 记忆 | 键值对 + 过期时间（默认30分钟） |
| §8 | 双轴语义 | 认知×执行 独立判断，仅认知=0且执行=就绪才算真正犹豫 |
| §9 | 工具调度 | 风险分级（高/低），高风险需门控 |
| §10 | 信息增益 | 新信息长度 / 已有信息长度（上限1） |
| §11 | 多数投票 | 统计真票/假票，可能弃权 |
| §12 | 最终目标 | 不确定性可见/可量化/可追溯，安全门控可靠 |

### 模块依赖图

```
config.san          ← 所有模块
  ↓
llm_http.san        ← llm_iface.san
  ↓
prompts.san         ← llm_iface.san, agent.san
  ↓
llm_iface.san       ← agent.san
  ↓
decision.san        ← memory.san, context_mgr.san, tool_sched.san, agent.san
  ↓
memory.san          ← context_mgr.san, agent.san
  ↓
context_mgr.san     ← agent.san
  ↓
tool_sched.san      ← agent.san
  ↓
agent.san           ← 入口
```

### 版本变更

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-05-30 | 初始版本，包含 §1–§12 全协议 |
