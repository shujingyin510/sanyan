# Agent 可读决策 DSL

[English](README_EN.md) | [操作手册](agent_operations.md) | [Operations Manual](agent_operations_en.md)

> 基于 [ternary-engine](https://pypi.org/project/ternary-engine/) 的 LLM Agent ——每步决策带置信度，不确定时自动门控拦截。

---

## 快速开始

```bash
set SANYAN_API_KEY=sk-你的key

# 单次提问
python -X utf8 run_agent.py "run_agent.py有哪些函数超过50行"
# → ⚠ >50行: init_evaluator, run_once, main, _analyze_file

# 自主模式（读→改→测→修→完成）
python -X utf8 run_agent.py "修复 _test_verify.py 让测试通过" --auto
# → [AFFIRM]→真 ●●● [0.81] → 修复成功

# 只读不改
python -X utf8 run_agent.py "把AGENTS.md里v0.3改成v0.4" --dry-run
# → [干跑] 将在 AGENTS.md 替换 v0.3 → v0.4
```

---

## 架构

```
用户任务
  │
  ├─ _force_tool()        智能首轮：检测"函数"→直接 analyze，省一次 LLM
  ├─ SemanticCache        P5: 语义缓存，重复任务零成本
  │
  ▼
  DecompositionEngine    Phase 0: 任务分解 → 递归拆解 → 每层摘要
  │  ├─ ComplexityClassifier  复杂度分级（simple/medium/complex）
  │  ├─ BoundedContext        有界上下文（硬限 4000 token）
  │  └─ ToolDependencyGraph   P1: 工具链合法性校验
  │
  ▼
  HypothesisGenerator    Phase 1: 多假设生成
  │  ├─ LLM 生成 5 个候选方案
  │  ├─ P1 依赖图过滤    工具顺序合法性
  │  ├─ P9 能力匹配过滤  任务需求 vs 工具能力
  │  └─ P8 多样性去重    关键词聚类，避免 5≈1
  │
  ▼
  Tournament             Phase 1: 锦标赛
  │  ├─ P2 并行早停      每假设执行 2 步，低置信度淘汰
  │  ├─ 经典淘汰         置信度差距 / 步骤差距 / LLM 兜底
  │  ├─ P3 失败分类      6 类 FailureMode + 重试策略
  │  └─ P4 自适应阈值    50 轮后从历史自动调参
  │
  ▼
  Execute 最优假设 ──→ TernaryEngine.step()
  │                    ├─ classify()   分类：AFFIRM/NEGATE/UNCERT
  │                    ├─ map_trit()   映射：1/0/-1
  │                    ├─ propagate()  Kleene 传播
  │                    ├─ confidence() 贝叶斯置信度衰减
  │                    └─ protect()    门控：高风险+不确定=拦截
  │
  ▼
  ResourceManager        Phase 2: 资源统一管控
  │  ├─ tool_reliability()    工具可靠性（时间衰减）
  │  ├─ P7 MetricsCollector   全链路可观测指标
  │  ├─ P10 CostPredictor     成本预测（历史数据）
  │  └─ P11 ReplayEngine      执行回放 + diff 对比
  │
  ▼
  反思 ──→ 继续 / 修正 / 完成
```

### 文件分层

| 文件 | 职责 | 补丁 |
|------|------|------|
| `ternary_engine.py` | 三态决策引擎（Kleene + 贝叶斯 + 门控） | — |
| `agent_tool_graph.py` | 工具依赖图 + 能力注册表 + 任务能力提取 | P1+P9 |
| `agent_decompose.py` | 任务分解引擎 + 有界上下文 + 复杂度分类器 | Phase 0 |
| `agent_hypothesis.py` | 多假设 + 多样性控制 + 锦标赛 + 失败分类 + 自适应阈值 | P2+P3+P4+P8 |
| `agent_resource.py` | 资源统一管控 + 语义缓存 + 可观测 + 成本预测 + 回放 | P5+P7+P10+P11 |
| `agent_runtime.py` | V5 运行时（三阶段全集成） | — |
| `agent_tools.py` | 工具层（12 个工具，纯函数，0 外部依赖） | — |
| `agent_policy.san` | 策略配置（模型 / 阈值 / 场景规则，热重载） | — |
| `decision.san` | 旧引擎决策核心（待迁移） | — |
| `run_agent.py` | 启动器（CLI 参数 + 双引擎切换） | — |

### 测试覆盖

| 模块 | 测试文件 | 项数 |
|------|----------|------|
| Agent 决策 | `test_agent.py` | 31 |
| AgentRuntime V5 | `test_agent_runtime.py` | 39 |
| Agent V5 新模块 | `test_agent_v5.py` | 158 |
| **合计** | | **228** |

### P6 Prompt 缓存

- system_prompt 稳定化（缓存一次，不含可变内容）
- BoundedContext.build() 复用同一对象引用
- 部署侧配置：OpenAI/Anthropic/vLLM 各自的 prefix caching

### 架构演进

```
v3.0: 单轮决策 + 工具调用
v3.1: + 多假设并行（多路径探索）
v3.2: + 经验学习（ExperienceStore）
v3.3: + 上下文压缩（TokenBudget）
v5.0: 三阶段重构
       Phase 0: 任务分解 + 有界上下文 + 工具依赖图[P1] + 能力注册[P9]
       Phase 1: 多假设 + 多样性[P8] + 锦标赛[P2] + 失败分类[P3] + 自适应阈值[P4]
       Phase 2: 资源管控 + 缓存[P5] + 可观测[P7] + 成本预测[P10] + 执行回放[P11]
```

---

## 工具

| 工具 | 用途 | 参数格式 |
|------|------|----------|
| `analyze` | 分析文件结构（函数/导入/行数），自动标记 >50 行函数 | `文件路径` |
| `find_symbol` | 查找符号定义和所有引用 | `符号名` |
| `read_file` | 读文件，支持行范围 | `路径\|起始行\|结束行` |
| `search_code` | 全局搜索关键词，返回匹配行 | `关键词` |
| `replace_in_file` | 单文件替换，`\n` 转义为换行 | `路径\|旧\|新` |
| `replace_all` | 批量跨文件替换 | `模式\|旧\|新` |
| `write_file` | 写文件，`\n` 转义为换行 | `路径\|内容` |
| `list_files` | 列文件，递归搜索 | `模式` |
| `run_test` | 运行 pytest，返回通过/失败+错误摘要 | `测试路径` |
| `git_diff` | 查看 git 修改（--stat） | （无参数） |
| `git_status` | 查看 git 状态（--short） | （无参数） |

---

## CLI

```bash
python -X utf8 run_agent.py "任务"              # 单次提问（V3 引擎）
python -X utf8 run_agent.py                      # 交互模式（旧引擎）
python -X utf8 run_agent.py "任务" --auto        # 自主模式：跑完才停
python -X utf8 run_agent.py "任务" --dry-run     # 只读不改：写操作返回预览
python -X utf8 run_agent.py "任务" --report      # 完成后输出任务报告
python -X utf8 run_agent.py "任务" --rounds 5    # 限制最大轮次
python -X utf8 run_agent.py --list-tasks          # 查看 SQLite 任务历史
python -X utf8 run_agent.py --resume             # 续接上次未完成任务
```

---

## 配置

编辑 `agent_policy.san`（修改后热重载，无需重启）：

```san
# 模型
设 模型提供商 = "deepseek"  # deepseek / openai / qwen / gemini / mimo / ollama / tokenplan
设 模型URL = "https://api.deepseek.com/v1/chat/completions"
设 模型名 = "deepseek-v4-pro"  # 或 deepseek-v4-flash
设 超时秒数 = 60
设 API密钥 = 环境变量("SANYAN_API_KEY")

# 决策阈值
设 最大轮次 = 10
设 最大犹豫次数 = 3
设 最小增益阈值 = 0.05

# 场景规则（非程序员可直接编辑）
设 场景规则 = 列表(
    字典("场景", "借钱", "关键词", "借钱,借款...", "风险", "高", "要求好感", 30, "信任阈值", 25),
    字典("场景", "修改Agent配置", "关键词", "最大轮次,API密钥...", "风险", "高", "要求好感", 60),
    ...
)
```

支持 7 家模型提供商，一行切换。高风险场景自动门控 + 信任感知权重。

---

## 三态显示

每步工具调用后显示三态传播链：

```
[AFFIRM]→真 ●●● [0.81]     ← 认知态 → 三态值 置信度
[NEGATE]→假 ○○○ [0.34]     ← 失败降为假
[UNCERT]→可能 ◐◐◐ [0.15]  ← 不确定进入犹豫计数
```

三态符号：`●`=真 / `◐`=可能 / `○`=假。门控触发时自动拦截。

---

## 村庄观察器

```bash
python -X utf8 run_village_observe.py --days=5
```

NPC 自主生活 + LLM 驱动对话 + TernaryEngine 三态信任演变 + SVG 图表 + JSON 日志。

每轮对话后三元引擎追踪村庄全局置信度：

```
凝聚力: 0.237  假:2 可能:1 真:1  三态: 真 ●●● [0.25]
凝聚力: 0.198  假:8 可能:2 真:1  三态: 真 ●●● [0.01]
```

---

## 测试

```bash
python -X utf8 tests/test_agent.py -v          # 31 项：决策流水线（映射/传播/投票/保护/规则）
python -X utf8 tests/test_agent_runtime.py -v  # 39 项：V5 引擎（SymbolTable/MemoryStore/约束/工具/分解/锦标赛）
python -X utf8 tests/run_all.py                # 46 项集成测试
```
