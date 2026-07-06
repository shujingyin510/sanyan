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
set SANYAN_API_KEY=sk-你的key      # 密钥只走环境变量，绝不写进源码

# 单次提问（仓库根执行）
python -X utf8 agent_system/run_agent.py "run_agent.py有哪些函数超过50行"
# → ⚠ >50行: init_evaluator, run_once, main, _analyze_file

# 自主模式（读→改→测→修→完成）
python -X utf8 agent_system/run_agent.py "修复 _test_verify.py 让测试通过" --auto
# → [AFFIRM]→真 ●●● [0.81] → 修复成功

# 只读不改
python -X utf8 agent_system/run_agent.py "把AGENTS.md里v0.3改成v0.4" --dry-run
# → [干跑] 将在 AGENTS.md 替换 v0.3 → v0.4

# 自更新闭环（agent 在隔离 worktree 里改自己的仓库，oracle 把关，产出分支由人合并）
python -X utf8 agent_system/run_self_update.py --pick ternary_match --attempts 4
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
| `agent_runtime.py` | 主运行时（工具注册、约束限额、各子系统协调） |
| `loop.py` | LLM 多轮主循环（时间预算、徘徊顶推、LLM 哨兵、零改动 done 顶回、停机原因如实） |
| `loop_policy.py` | 循环策略（UR 退化判定、上下文过大判定） |
| `agent_core.py` | 基础类（SymbolTable, MemoryStore, ProjectGraph） |
| `agent_llm_handler.py` | LLM 调用（9 家提供商、3 重试）+ 工具解析（五级兜底、列表参数按行拼接） |
| `agent_tools.py` | 工具层（read/replace/replace_lines/run_test 等纯函数） |
| `agent_execution.py` | 规则执行和代码生成 |
| `agent_learning_handler.py` | 学习和经验管理（认 `AGENT_DATA_DIR`） |
| **自更新闭环（北极星）** | |
| `self_update.py` | `SelfUpdateLoop`：worktree 隔离→编辑→fail-closed oracle→留分支/回滚；oracle 工厂（shrink 静态四连闸 / pytest 基线 / 差分） |
| `run_self_update.py` | 自更新 CLI：挖掘→任务书→`--attempts` 带记忆重试（七类对症纠偏+两课链）→尸检落盘 |
| `task_mining.py` | 任务挖掘（failing_test / todo / long_function，静态候选块标注） |
| **脊梁** | |
| `contracts.py` | `ToolResult` / `LLMProvider` 类型契约 |
| `registry.py` | `LazyRegistry` 能力懒加载（13 个非热路径子系统） |
| `paths.py` / `store.py` | 数据目录统一（`AGENT_DATA_DIR`）/ 单一 `agent.db` |
| `config.py` | `AgentConfig`（`agent_policy.san` 热重载） |
| **智能层** | |
| `agent_domain.py` | 领域知识层（LLM 动态生成） |
| `agent_rules.py` | 规则引擎（200+ 规则） |
| `template_manager.py` | 模板管理器（11 个模板） |
| `ast_parser.py` | AST 解析器（精准上下文） |
| `ur_monitor.py` | UR 退化检测 |
| `model_router.py` | 多模型路由器 |
| `agent_coordinator.py` | 多 Agent 协作 |
| `git_batch_learner.py` | Git 批量学习 |
| `core/ternary_engine.py` | 三态决策引擎（五态分类 + Kleene 传播 + 置信度回血 + 连续犹豫计数 + 门控，位于 `core/`） |

### 目录结构

```
agent_system/
├── 入口
│   ├── run_agent.py              # Agent CLI（交互/单次/自主/沙箱/进化）
│   ├── run_self_update.py        # 自更新闭环 CLI（挖掘→隔离编辑→oracle→分支）
│   └── agent_loop.py             # 自主循环（文件监控/连续模式）
│
├── 核心运行时
│   ├── agent_runtime.py          # 主运行时（工具注册/约束限额/协调）
│   ├── loop.py                   # LLM 多轮主循环（预算/顶推/哨兵/停机如实）
│   ├── loop_policy.py            # 循环策略（UR 退化/上下文判定）
│   ├── agent_core.py             # 基础类（SymbolTable/MemoryStore/ProjectGraph）
│   ├── agent_llm_handler.py      # LLM 调用 + 工具解析（五级兜底）
│   ├── agent_tools.py            # 工具层（纯函数，零依赖）
│   ├── agent_execution.py        # 规则执行与代码生成
│   └── agent_learning_handler.py # 学习管理
│
├── 自更新闭环（北极星：agent 安全迭代自己的代码）
│   ├── self_update.py            # SelfUpdateLoop + oracle 工厂（shrink/pytest/差分）
│   └── task_mining.py            # 任务挖掘（failing_test/todo/long_function）
│
├── 脊梁（阶段 0-2 收敛产物）
│   ├── contracts.py              # ToolResult / LLMProvider 契约
│   ├── registry.py               # LazyRegistry 能力懒加载
│   ├── paths.py                  # 数据目录统一（AGENT_DATA_DIR）
│   ├── store.py                  # 单一 agent.db（连接/迁移）
│   └── config.py                 # AgentConfig（agent_policy.san 热重载）
│
├── 智能层
│   ├── agent_domain.py           # 领域知识（LLM 动态生成 + 缓存）
│   ├── agent_rules.py            # 规则引擎（200+ 规则）
│   ├── template_manager.py       # 模板管理（11 个模板库）
│   ├── ast_parser.py             # AST 解析（精准上下文）
│   ├── ur_monitor.py             # UR 退化检测
│   ├── model_router.py           # 多模型路由
│   └── truth_calibration.py      # 答案置信度校准
│
├── 能力插件（懒加载，经 registry 按需构造）
│   ├── agent_hypothesis.py       # 多假设 + 锦标赛
│   ├── agent_decompose.py        # 任务分解 + 有界上下文
│   ├── agent_evolution.py / agent_evolution_v2.py   # 约束进化 / Patch DSL
│   ├── agent_learning.py         # 跨会话经验（ExperienceStore）
│   ├── agent_coordinator.py / agent_shared.py       # 多 Agent 协作/共享
│   ├── agent_obs.py / agent_dashboard.py            # 可观测性/仪表盘
│   └── …（validation/stress/knowledge/cost_aware 等 20+ 模块，见文件分层表）
│
├── templates/                    # 模板库（math/data_structures/algorithms/utils + 测试生成）
├── sanyan/                       # 三言侧 DSL（agent.san/agent_policy.san/decision.san/runtime_v2/）
│
└── 文档
    ├── README.md / README_EN.md          # 本文档（中/英）
    ├── agent_operations.md / _en.md      # 操作手册（中/英）
    └── REFACTOR_PLAN.md                  # 北极星路线：P0-P5 进度日志 + S0-S6 前瞻规划
```

> 运行副产物（`agent.db`、`learned_styles.md` 等）不列入结构——它们由 `paths.py` 统一
> 落到 `AGENT_DATA_DIR`（默认本目录），且被自更新闭环排除在提交外。

### 测试覆盖

| 范围 | 测试文件 |
|------|----------|
| 决策引擎 / 三态传播 | `test_agent.py` |
| 运行时（工具解析/约束/构造） | `test_agent_runtime.py` |
| V5 模块（分解/假设/资源） | `test_agent_v5.py` |
| LLM 主循环（预算/顶推/哨兵/⑥/B） | `test_loop.py` |
| 自更新闭环（隔离/回滚/排除） | `test_self_update.py` |
| oracle 静态四连闸 | `test_shrink_oracle.py` |
| 自更新 CLI（重试/纠偏/尸检） | `test_selfupdate_cli.py` |
| 任务挖掘 | `test_task_mining.py` |
| 学习存储 | `test_learning_store.py` |

Agent 线合计 **321 项**（2026-07-06；全仓套件 2554 passed，以 `pytest tests/` 实测为准）。

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
——以下为自更新闭环线（REFACTOR_PLAN 北极星）——
v3.51: P1 安全自更新闭环（worktree 隔离 + fail-closed oracle + 绝不自动合并）
v3.52: P2 真 LLM 首跑闭环（自造任务 + 差分 oracle + 12 轮探针挖出 10 个真 bug）
v3.53: P3 循环内生存性（尸检可观测链 + 副产物排除 + 置信度回血）
v3.54: P3 实跑迭代周（oracle 静态四连闸 + 带记忆重试 + 七轮 22 次尝试死因全闭环）
```

---

## 自更新闭环（北极星）

Agent 在**隔离的 git worktree** 里修改本仓库代码，fail-closed oracle 把关，通过则产出
`self-update/<名>-<时间戳>` 分支**由人合并**，被拒则整体回滚零残留。两条红线：oracle
（tests/、self_update.py 等考官域）在 agent 写权限之外；绝不自动合并。

```bash
python -X utf8 agent_system/run_self_update.py --list                 # 看挖掘出的任务榜
python -X utf8 agent_system/run_self_update.py --pick ternary_match --attempts 4
# EXIT: 0=有候选被接受(打印分支名)  1=尝试耗尽全拒  2=--pick 未命中
```

- **oracle 栈**（依序短路）：shrink 静态四连闸（变短 → 嵌套 def/大粘贴诊断 → 引用可
  解析（作用域感知）→ 守恒检查"只搬不改"）→ pytest 全量基线（带失败用例名）→ 差分
  一致性。静态闸毫秒级，坏候选不烧 pytest。
- **带记忆重试**：每次拒绝的原因经 `classify_tip` 分类成对症纠偏（七类死法对照表见
  REFACTOR_PLAN），连同候选块行区间塞回下一轮任务书；最多带两课，防丢课也防膨胀。
- **尸检**：被拒改动的 patch+stat 在回滚前自动落 agent 日志（`%TEMP%/sanyan-su-agent-*.log`），
  分支蒸发后仍可判读死因。
- **调参**（CLI 自动设置，经子进程继承）：`SANYAN_LOOP_TIME_BUDGET=900`（循环总预算）、
  `SANYAN_TOOL_REPEAT_LIMIT=10`（同工具限额）、`SANYAN_REQUIRE_EDIT=1`（零改动顶回+徘徊
  顶推）、`SANYAN_SKIP_RULE_GEN=1`。
- 路线图与逐轮实跑记录：见 [REFACTOR_PLAN.md](REFACTOR_PLAN.md)（P0-P5 进度日志 +
  S0-S6 前瞻规划——按交接文档标准维护）。

---

## 工具

| 工具 | 用途 | 参数格式 |
|------|------|----------|
| `analyze` | 分析文件结构（函数/导入/行数），自动标记 >50 行函数 | `文件路径` |
| `find_symbol` | 查找符号定义和所有引用 | `符号名` |
| `read_file` | 读文件，支持行范围 | `路径\|起始行\|结束行` |
| `search_code` | 全局搜索关键词，返回匹配行 | `关键词` |
| `replace_in_file` | 单文件替换，`\n` 转义为换行；未命中附最接近原文 | `路径\|旧\|新` |
| `replace_lines` | 按行号整段替换（无需逐字抄原文，弱模型友好） | `路径\|起始行\|结束行\|新文本` |
| `replace_all` | 批量跨文件替换 | `模式\|旧\|新` |
| `write_file` | 写文件，`\n` 转义为换行 | `路径\|内容` |
| `list_files` | 列文件，递归搜索 | `模式` |
| `run_test` | 运行 pytest，返回通过/失败+错误摘要 | `测试路径` |
| `git_diff` | 查看 git 修改（--stat） | （无参数） |
| `git_status` | 查看 git 状态（--short） | （无参数） |

---

## CLI

```bash
python -X utf8 agent_system/run_agent.py "任务"              # 单次提问（V3 引擎）
python -X utf8 agent_system/run_agent.py       # 交互模式（V5 引擎）
python -X utf8 agent_system/run_agent.py "任务" --auto        # 自主模式：跑完才停
python -X utf8 agent_system/run_agent.py "任务" --dry-run     # 只读不改：写操作返回预览
python -X utf8 agent_system/run_agent.py "任务" --report      # 完成后输出任务报告
python -X utf8 agent_system/run_agent.py "任务" --rounds 5    # 限制最大轮次
python -X utf8 agent_system/run_agent.py --list-tasks          # 查看 SQLite 任务历史
python -X utf8 agent_system/run_agent.py --resume             # 续接上次未完成任务
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
python -X utf8 examples/run_village_observe.py --days=5
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
