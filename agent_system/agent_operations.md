# Sanyan Agent 操作手册

> [English Version](agent_operations_en.md)

---

## 快速开始

```bash
# 基础用法
python -X utf8 run_agent.py "你的问题"

# 交互模式
python -X utf8 run_agent.py
```

## 核心概念

### 三层架构

```
┌─────────────────────────────────────────────────────┐
│  Layer 5: Knowledge Layer（知识层）                  │
│  - TaskClassifier / TaskEmbedding / ClusterLearning │
├─────────────────────────────────────────────────────┤
│  Layer 2: Evolution Layer（进化层）                  │
│  - Ranking / Cost / Budget / UCB                    │
├─────────────────────────────────────────────────────┤
│  Layer 1: Policy Layer（策略层）                     │
│  - Config / Strategy / Hypothesis                   │
├─────────────────────────────────────────────────────┤
│  Layer 0: Frozen Core（冰冻核心）                    │
│  - Reviewer / Replay / History / Ternary            │
└─────────────────────────────────────────────────────┘
```

### 三态逻辑

| 层 | 三态表现 | 说明 |
|---|---|---|
| 语言层 | TRUE / FALSE / UNKNOWN | Kleene三值逻辑 |
| Agent层 | 高置信度 / 低置信度 / 未知 | 决策门控 |
| Knowledge Layer | 可信知识 / 弱知识 / 未知知识 | 知识可靠性评估 |

---

## 工具列表

### 文件操作

| 工具 | 参数 | 说明 |
|------|------|------|
| `read_file` | `path\|start\|end` | 读取文件内容 |
| `write_file` | `path\|content` | 写入文件 |
| `replace_in_file` | `path\|old\|new` | 替换文件内容（未命中附最接近原文） |
| `replace_lines` | `path\|start\|end\|new` | 按行号整段替换（无需逐字抄原文） |
| `replace_all` | `pattern\|old\|new` | 批量替换 |
| `list_files` | `pattern` | 列出文件 |
| `analyze` | `path` | 分析文件结构 |

### 搜索工具

| 工具 | 参数 | 说明 |
|------|------|------|
| `search_code` | `keyword` | 搜索代码内容 |
| `find_symbol` | `name` | 查找符号定义/引用 |

### 测试工具

| 工具 | 参数 | 说明 |
|------|------|------|
| `run_test` | `test_file` | 运行测试 |

### Git 工具

| 工具 | 参数 | 说明 |
|------|------|------|
| `git_diff` | - | 查看 git 差异 |
| `git_status` | - | 查看 git 状态 |
| `git_stash` | - | 保存现场并回退 |
| `git_reset_hard` | - | 硬回退到上一个提交 |
| `git_commit_auto` | `msg` | 自动提交 |

### 控制工具

| 工具 | 参数 | 说明 |
|------|------|------|
| `run_shell` | `cmd` | 执行 shell 命令 |
| `done` | `answer` | 任务完成，输出最终答案 |

### SQLite 操作

| 工具 | 参数 | 说明 |
|------|------|------|
| `sqlite_open` | `path` | 打开数据库连接 |
| `sqlite_close` | `path` | 关闭连接 |
| `sqlite_exec` | `path\|sql` | 执行 SQL |
| `sqlite_query` | `path\|sql` | 查询 SQL（返回列表） |
| `sqlite_tables` | `path` | 列出所有表 |
| `sqlite_schema` | `path\|table` | 获取表结构 |
| `sqlite_insert` | `path\|table\|dict` | 插入数据 |
| `sqlite_update` | `path\|table\|dict\|where` | 更新数据 |
| `sqlite_delete` | `path\|table\|where` | 删除数据 |
| `sqlite_count` | `path\|table` | 统计行数 |

---

## CLI 命令

### 基础命令

```bash
# 交互模式
python -X utf8 run_agent.py

# 单次提问
python -X utf8 run_agent.py "你的问题"

# 直接执行三言代码
python -X utf8 run_agent.py "(设 x 10)(输出(加 x 5))"
```

### 规则管理命令

```bash
# 列出所有规则
python -X utf8 run_agent.py --list-rules

# 审批待生成的规则
python -X utf8 run_agent.py --approve-rule

# 拒绝待生成的规则
python -X utf8 run_agent.py --reject-rule

# 导出规则到文件
python -X utf8 run_agent.py --export-rules my_rules.tar.gz

# 从文件导入规则
python -X utf8 run_agent.py --import-rules my_rules.tar.gz
```

### 学习命令

```bash
# 从 git 历史批量学习项目风格
python -X utf8 run_agent.py --learn
```

### 模型选择命令

```bash
# 指定模型
python -X utf8 run_agent.py "任务" --model deepseek-v4-pro
python -X utf8 run_agent.py "任务" --model local/qwen2.5-0.5b
```

### 进化系统命令

```bash
# 约束进化验证
python -X utf8 run_agent.py --evolve

# 自举验证
python -X utf8 run_agent.py --self-host

# 自动化进化闭环
python -X utf8 run_agent.py --auto-evolve --max-cycles 3

# Agent自主改代码闭环
python -X utf8 run_agent.py --code-evolve --max-cycles 3

# 带审查的进化闭环
python -X utf8 run_agent.py --review-evolve

# MetaConfig进化
python -X utf8 run_agent.py --metaconfig

# 进化验证
python -X utf8 run_agent.py --validate

# 进化仪表盘
python -X utf8 run_agent.py --evo-dashboard
```

### 自主循环命令

```bash
# 文件监控模式
python -X utf8 agent_system/agent_loop.py --watch

# 连续循环模式
python -X utf8 agent_system/agent_loop.py --continuous

# 查看统计和健康状态
python -X utf8 agent_system/agent_loop.py --status
```

### 自更新闭环命令（北极星：agent 安全迭代自己的代码）

```bash
# 列出挖掘到的任务榜（failing_test > todo > long_function）
python -X utf8 agent_system/run_self_update.py --list

# 按子串挑任务跑闭环（隔离 worktree → oracle → 产出分支由人合并）
python -X utf8 agent_system/run_self_update.py --pick ternary_match --attempts 4

# 自定义任务书 / 喂失败测试来源 / 调 oracle 参数
python -X utf8 agent_system/run_self_update.py --task "任务书"
python -X utf8 agent_system/run_self_update.py --pytest-log fail.log
python -X utf8 agent_system/run_self_update.py --baseline 0 --pytest-timeout 900 --no-differential
```

| 项 | 说明 |
|---|---|
| 退出码 | `0`=有候选被接受（打印分支名）；`1`=尝试耗尽全拒；`2`=`--pick` 未命中 |
| 跑前检查 | `git status` 干净、无残留 `self-update/*` 分支、`git worktree list` 只有主树 |
| 红线 | oracle（tests/、self_update.py 等考官域）在 agent 写权限外；**绝不自动合并** |
| oracle 栈 | shrink 静态四连闸（变短→嵌套/大粘贴诊断→引用可解析→守恒）→ pytest 基线 → 差分 |
| 带记忆重试 | 每次拒绝分类成对症纠偏塞回下一轮任务书（最多带两课） |
| 尸检 | 被拒 diff+stat 回滚前落 `%TEMP%/sanyan-su-agent-<时间戳>.log` |

自更新专用环境变量（CLI 自动设置、经 agent 子进程继承）：

| 变量 | 值 | 语义 |
|---|---|---|
| `SANYAN_LOOP_TIME_BUDGET` | 900 | 主循环总预算秒（默认 420） |
| `SANYAN_TOOL_REPEAT_LIMIT` | 10 | 同工具调用上限（默认 5） |
| `SANYAN_REQUIRE_EDIT` | 1 | 零改动 done 顶回 + 徘徊顶推 |
| `SANYAN_SKIP_RULE_GEN` | 1 | 跳过规则生成前奏 |

详见 `agent_system/REFACTOR_PLAN.md`（P0-P5 进度日志 + S0-S6 前瞻规划，含尸检工作流
与死法↔反制对照表）。

---

## 交互命令

| 命令 | 说明 |
|------|------|
| `/状态` | 三态决策摘要 |
| `/记忆` | 任务记忆 |
| `/仪表盘` | 实时仪表盘 |
| `/追踪` | 决策链可视化 |
| `/性能` | 性能报告（Token用量、工具耗时） |
| `/经验` | 跨会话经验（工具可靠性、失败模式） |
| `/安全` | 安全沙箱状态（审计日志） |
| `/共享` | 共享上下文空间 |
| `/管道` | 工具管道列表 |

---

## LLM 配置

### 支持的模型厂商

| 厂商 | Base URL | 默认模型 |
|------|----------|----------|
| DeepSeek | https://api.deepseek.com/v1 | deepseek-v4-pro |
| OpenAI | https://api.openai.com/v1 | gpt-4o |
| Anthropic | https://api.anthropic.com | claude-sonnet-4 |
| Gemini | https://generativelanguage.googleapis.com/v1beta | gemini-2.5-flash |
| Qwen | https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen-max |
| GLM | https://open.bigmodel.cn/api/paas/v4 | glm-4 |
| Moonshot | https://api.moonshot.cn/v1 | moonshot-v1-8k |
| SiliconFlow | https://api.siliconflow.cn/v1 | deepseek-ai/DeepSeek-V3 |
| OpenRouter | https://openrouter.ai/api/v1 | anthropic/claude-sonnet-4 |

### 配置方式

```bash
# 环境变量
export SANYAN_API_KEY=sk-xxx
export LLM_PROVIDER=deepseek
export LLM_MODEL=deepseek-v4-pro
```

或修改 `agent_system/sanyan/agent_policy.san`：

```san
设 模型提供商 = "deepseek"
设 模型名 = "deepseek-v4-pro"
```

---

## 架构说明

### 五层架构

| 层 | 组件 | 职责 |
|---|---|---|
| Layer 5 | Knowledge Validation | 知识置信度、聚类、一致性 |
| Layer 4 | Knowledge Layer | MetaLearningDB、TaskEmbedding、ClusterLearning |
| Layer 3 | Evolution Layer | Ranking、Cost、Budget、UCB |
| Layer 2 | Policy Layer | Config、Strategy、Hypothesis |
| Layer 1 | Frozen Core | Reviewer、Replay、History、Ternary |

### 三层知识体系

| 层 | 内容 | 共享策略 |
|---|---|---|
| Global Knowledge | 任务模式→策略模式（元知识） | 共享统计规律 |
| Project Memory | 项目专属经验（最优参数/Patch模式） | 项目内共享 |
| Personal Memory | 用户偏好/习惯 | 不共享 |

### 核心公式

**Knowledge Confidence:**
```
confidence = sample_factor × 0.4 + sr_factor × 0.3 + consistency_factor × 0.3
```

**Cost-Aware Efficiency:**
```
efficiency = improvement / cost
cost = verification_time + tokens/1000
```

**UCB1 Exploration:**
```
UCB_score = avg_value + c × sqrt(ln(total_plays) / n_plays)
```

---

## 实验数据

### 因果链闭环

| Agent | 预测SR | 实际SR | 差距 |
|-------|--------|--------|------|
| Baseline | 40.8% | 40.9% | 0.1% |
| Knowledge | 82.9% | 82.5% | 0.4% |
| Knowledge+Conf | 83.0% | 84.5% | 1.5% |

### 知识迁移

| 目标项目 | Baseline | 配置迁移 | 规律迁移 |
|----------|----------|----------|----------|
| iot_system | 30.4% | 25.8% (-4.6%) | 58.4% (+24.2%) |
| web_app | 33.8% | 31.0% (-2.8%) | 65.0% (+31.6%) |

### 知识置信度

| 任务类型 | 样本数 | 成功率 | 置信度 |
|----------|--------|--------|--------|
| documentation | 151 | 90.0% | 0.92 |
| analysis | 111 | 84.0% | 0.87 |
| feature | 172 | 80.2% | 0.84 |
| bug_fix | 183 | 74.2% | 0.79 |

---

## 核心洞察

> Knowledge → Confidence → Selection → Success

**三态逻辑贯穿整个系统：**
- 语言时代：TRUE / FALSE / UNKNOWN
- Agent时代：高置信度 / 低置信度 / 未知
- Knowledge Layer：可信知识 / 弱知识 / 未知知识

**LLM知识 vs Agent知识：**
- LLM = Prior（推测）
- Agent = Evidence（证据）
