# Agent 可读决策 DSL

[English](README_EN.md) | [操作手册](agent_operations.md) | [Operations Manual](agent_operations_en.md)

> 基于三态逻辑的 LLM Agent ——每步决策带置信度传播，不确定时自动门控拦截。

---

## 核心设计原则

**三态框架不能教模型做它不会的事。** 它解决的是模型已经具备工具调用能力后，如何在失败、冲突、不确定和退化状态下做出更可靠的决策。

```
模型能力层（LLM 本身）
  └─ 0.5B: 只会填空，不会工具调用 → 三态帮不了
  └─ DeepSeek V4: 已具备能力 → 三态让决策更可靠

三态决策层（Ternary Engine）
  └─ AFFIRM(真):  继续执行, 置信传播
  └─ UNCERT(可能): 犹豫计数, 降置信
  └─ NEGATE(假):  门控拦截, 切换策略
  └─ 退化检测:     UR < 0.30 → 强制停止

规则引擎层（Rule Engine）
  └─ 80% 代码任务纯规则匹配, 零 LLM 调用
```

**不是让模型变强，是让模型不那么容易崩。**

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
  ├─ 规则引擎        200+ 规则匹配，0 LLM 调用
  ├─ 模板管理器      11 个模板库，代码生成
  ├─ 领域知识层      LLM 动态生成领域知识
  │
  ▼
  DecompositionEngine    Phase 0: 任务分解
  │  ├─ ComplexityClassifier  复杂度分级
  │  ├─ BoundedContext        有界上下文
  │  └─ ASTParser             精准上下文加载
  │
  ▼
  DomainKnowledgeLayer   领域知识
  │  ├─ LLM 动态生成    组件/验证/终止条件
  │  ├─ SQLite 缓存     同类任务只问一次
  │  └─ 反模式约束      防止过度工程
  │
  ▼
  RuleEngine / LLM       执行
  │  ├─ 规则匹配        200+ 规则，0 成本
  │  ├─ 模板生成        11 个模板库
  │  ├─ LLM 兜底        DeepSeek V4 Pro
  │  └─ UR 退化检测     防止死循环
  │
  ▼
  LearningHandler        学习
  │  ├─ SQLite 记录     执行历史
  │  ├─ 风格提取        项目风格
  │  └─ Git 批量学习    历史分析
  │
  ▼
  反思 ──→ 继续 / 修正 / 完成
```

### 文件分层

| 文件 | 职责 |
|------|------|
| `agent_runtime.py` | 主运行时（流程控制 + 协调） |
| `agent_core.py` | 基础类（SymbolTable, MemoryStore, ProjectGraph） |
| `agent_llm_handler.py` | LLM 调用和工具解析 |
| `agent_execution.py` | 规则执行和代码生成 |
| `agent_learning_handler.py` | 学习和经验管理 |
| `agent_domain.py` | 领域知识层（LLM 动态生成） |
| `agent_rules.py` | 规则引擎（200+ 规则） |
| `template_manager.py` | 模板管理器（11 个模板） |
| `ast_parser.py` | AST 解析器（精准上下文） |
| `ur_monitor.py` | UR 退化检测 |
| `model_router.py` | 多模型路由器 |
| `agent_coordinator.py` | 多 Agent 协作 |
| `project_migrator.py` | 跨项目迁移 |
| `git_batch_learner.py` | Git 批量学习 |
| `agent_llm.py` | LLM Provider（含本地模型） |
| `ternary_engine.py` | 三态决策引擎 |
| `decision.san` | 旧引擎决策核心（已迁移到 Python） |
| `agent_runtime.san` | 三言版 Agent 运行时 |

### 目录结构

```
agent_system/
├── 核心运行时
│   ├── agent_runtime.py          # 主运行时
│   ├── agent_core.py             # 基础类
│   ├── agent_llm_handler.py      # LLM 调用
│   ├── agent_execution.py        # 规则执行
│   └── agent_learning_handler.py # 学习管理
│
├── 智能层
│   ├── agent_domain.py           # 领域知识
│   ├── agent_rules.py            # 规则引擎
│   ├── template_manager.py       # 模板管理
│   ├── ast_parser.py             # AST 解析
│   ├── ur_monitor.py             # UR 退化检测
│   └── model_router.py           # 多模型路由
│
├── 协作与迁移
│   ├── agent_coordinator.py      # 多 Agent 协作
│   ├── project_migrator.py       # 跨项目迁移
│   └── git_batch_learner.py      # Git 批量学习
│
├── 模板库
│   └── templates/
│       ├── math/                 # 数学函数
│       ├── data_structures/      # 数据结构
│       ├── algorithms/           # 算法
│       ├── utils/                # 工具函数
│       └── test_generator.py     # 测试生成器
│
├── 三言实现
│   └── sanyan/
│       ├── agent_runtime.san     # 三言版运行时
│       ├── agent.san             # Agent 主逻辑
│       ├── decision.san          # 决策核心
│       └── llm_iface.san         # LLM 接口
│
├── 数据库
│   ├── domain_knowledge.db       # 领域知识缓存
│   ├── git_task_knowledge.db     # Git 任务知识
│   └── *.db                      # 其他 SQLite 数据库
│
└── 文档
    ├── README.md                 # 中文文档
    ├── README_EN.md              # 英文文档
    ├── agent_operations.md       # 操作手册（中文）
    └── agent_operations_en.md    # 操作手册（英文）
```

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
v3.4: + 规则引擎（200条规则，80%任务零LLM）
v3.5: + 三态引擎驱动决策（五态分类+门控+最终判定）
v3.6: + 多语言通用QA + 本地模型支持
v3.7: + UR退化检测（LLM输出级，替代硬编码成功判断）
v5.0: 三阶段重构（任务分解+多假设+资源管控）
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
python -X utf8 run_agent.py                      # 交互模式（V5 引擎）
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
