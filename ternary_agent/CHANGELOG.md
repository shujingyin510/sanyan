# 开发日志

## 2026-05-30 — v0.3.0

### 修复
- `agent.san:246`：移除孤立 `}` 语法错误
- 置信度传播：`上游置信度` 从始终 1.0 改为追踪上一轮传播后的实际置信度
- 记忆系统：新增 `清理过期记忆()` 函数，在每轮对话开始时自动清理过期条目

### 变更
- `agent_policy.san`：API密钥 优先从环境变量 `DEEPSEEK_API_KEY` 读取
- `agent.san`：LLM 调用增加 API 密钥未配置检查和更详细的错误信息
- `config.san`：标记为遗留文件（已被 `agent_policy.san` 替代）
- `agent.san`：添加注释说明与 `decision.san` 的关系（策略扩展 vs 基础版）

### 新增
- `decision.san` 与 `agent.san` 代码关系文档化
- `agent_policy.san` 环境变量回退机制

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
