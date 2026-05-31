# 开发日志

## 2026-05-30 — v0.1.0

### 新增
- `config.san`：配置文件（LLM API、超时、保护阈值）
- `prompts.san`：协议 §1–§12 提示词模板
- `llm_http.san`：curl LLM 调用封装
- `decision.san`：5→3 映射、传播、保护、投票
- `llm_iface.san`：JSON 响应解析
- `memory.san`：TTL 记忆系统
- `agent.san`：Agent 主循环
- `context_mgr.san`：上下文压缩 + 冲突统计
- `tool_sched.san`：工具调度 + 安全门控
- `demo_compress.san`：上下文压缩演示
- `demo_ambient.san`：模糊查询多轮演示
- `tests_boundary.san`：5 条边界测试
- `tests.san`：6 条关键路径测试
- `protocol_versions.md`、`future.md`、`CHANGELOG.md`
