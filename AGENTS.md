# AGENTS.md — 三言项目维护约定

## 🚨 最高优先级：提交前强制自查

**每次 `git commit` 前，必须先跑本地测试，绿了才能提交：**

```bash
ruff check . && ruff format --check . && mypy . && python -X utf8 preflight.py --quick
```

绿了 → 提交。红灯 → 修完再提。**不允许跳过。不允许 `--no-verify`。**
这条规则优先级高于一切——宁可慢一点，不要再把 CI 红着推上去。

---

## 📋 工作优先级（从上到下执行）

| 等级 | 触发条件 | 行为 |
|------|------|------|
| 🚨 P0 | 用户直接指令 | 立即执行，其他事暂停 |
| 🚨 P0 | CI 红灯 / bug 报错 | 立即修，修完跑 preflight 绿了再继续 |
| 🔴 P1 | 写完任何代码 | 先跑 `ruff check . && ruff format --check . && mypy .` |
| 🔴 P1 | 推送到 GitHub 前 | 必跑 `python -X utf8 preflight.py --quick`，绿了才能 push |
| 🟡 P2 | 多文件替换 / 中文内容编辑 | 用外置 `.py` 脚本操作，不要 bash 内联（避免 GBK/UTF-8 编码错误） |
| 🟡 P2 | 修改 `agent_system/` 下文件 | 改完必须验证 `import run_agent` 不崩 |
| 🟢 P3 | 日常小改动、调试、提示词调优 | 只本地 commit，不 push，等用户确认 |

---

## 汇编器（Agent 写字节码用）

> **重要**：汇编器允许 Agent 直接写 Sanyan 字节码程序。语法和陷阱见 → [`docs/asm_guide.md`](docs/asm_guide.md)

```bash
python asm.py program.sasm -o program.bin     # 汇编
python -X utf8 sanyanc.py program.bin --run   # 运行
```

关键陷阱：比较指令返回 TritValue(-1/1) 而非 int(0/1)，JZ/JNZ 需要加 1 归一化。

## Agent 系统

三言 Agent 是**可读决策 DSL**——决策过程对非程序员透明可读。

### 多 Agent 协作

父 Agent 可调度子 Agent 并行工作，每个子 Agent 独立运行决策引擎：

```
父Agent ──┬── 子Agent1 (规则分析) ──→ 返回结果
          ├── 子Agent2 (代码编写) ──→ 返回结果
          └── 子Agent3 (测试验证) ──→ 返回结果
```

| 工具 | 功能 |
|------|------|
| `调度子Agent` | task=任务 name=名称 → 子Agent独立决策 |
| `Agent消息` | to=目标 msg=消息 → Agent间通信 |
| `列出Agent` | 查看所有Agent状态 (running/done/error) |

子Agent 继承父Agent的：置信逻辑 + 传播逻辑 + 三态决策引擎 + 工具集。

**LLM 模式**：task 不以 `(` 开头时走 `Agent运行`，调用 LLM 推理。
**代码模式**：task 以 `(` 开头时直接执行 Sanyan 表达式。

### 架构

```
用户提问 → 规则匹配 → LLM 调用 → 5 种认知态 → 5→3 映射 → 三态传播 → 保护门控 → 动作分发
  (关键词)    (DeepSeek)   AFFIRM/NEGATE     1/-1/0     上游×当前   高风险/超限   READY/TOOL
                           UNCERT/CONFLICTED   +置信度    +置信度     /增益不足    /HUMAN
```

**V5 AgentRuntime**（Python 原生引擎，四阶段）+ **自主进化闭环**（`--code-evolve`）：
```
用户提问 → SymbolTable预加载 → SemanticCache缓存检查 → DecompositionEngine任务分解
         → HypothesisGenerator多假设生成 → Tournament锦标赛选优
         → 每步调 LLM 获取 tool+args（JSON 格式）→ TernaryEngine三态决策
         → 经验库跨任务模式匹配 → 完成

--code-evolve: LLM生成补丁 → 行号校准 → 多后端一致性验证 → 自举验证 → 接受/回滚
```

**LLM 连接**：DeepSeek v4（`deepseek-v4-pro`），thinking 显式启用 `{budget_tokens: 2048}`，`max_tokens: 4096`。
API 密钥通过环境变量 `SANYAN_API_KEY` 注入，`agent_policy.san` 中配置。

**工具调用格式（JSON）**：
```
{"tool":"analyze","args":{"path":"run_agent.py"}}
{"tool":"done","args":{"answer":"我是三言编程助手。"}}
```
解析器用括号计数提取 `{...}` + `json.loads`，pipe 格式 `tool|params` 作为回退。

### 安全机制

| 机制 | 触发条件 | 行为 |
|------|------|------|
| 置信度衰减检测 | 最近4轮严格单调递减 + floor<0.35 | 截断重启 |
| 轮次兜底 | Agent运行 ≥6轮 | 截断 |
| 超时硬杀 | 执行超过30秒 | killed |
| 死锁检测 | running >30秒 | stuck标记 |
| 失败分类 | info_gap / wrong_approach / unsolvable / escalation | 日志记录 |
| LLM 失败防死循环 | 连续3次返回 error\\\\|LLM调用失败 | break 退出 |
| 约束超限 | 同一工具连续5次 | break 退出 |
| **安全沙箱** | `--sandbox` 模式 | 命令黑名单 + 文件系统守卫 + 只读模式 + 审计日志 |

### 反馈闭环（agent_project.py）

| 机制 | 触发条件 | 行为 |
|------|------|------|
| 结构化重试历史 | 每轮记录 diff + 失败原因 | 注入 task.description |
| 同位置连错检测 | 连续两轮同文件同错误 | 自动 escalate |
| Toggle 检测 | 文件内容回到 baseline | 自动 escalate |
| 经验库 | 跨任务关键词匹配 | 失败2次生成 AVOID 提示 |

可配置项（`agent_policy.san`）：`Agent超时秒数`、`Agent最大轮次`、`Agent置信度衰减窗`、`Agent置信度底线`

### 文件结构

| 文件 | 用途 |
|------|------|
| `ternary_agent/agent.san` | Agent 核心逻辑 |
| `ternary_agent/agent_policy.san` | 纯数据策略（配置、阈值、规则） |
| `ternary_agent/decision.san` | 决策核心（信任感知规则匹配） |
| `agent_tools.py` | 工具层：analyze、find_symbol、spawn_sub_agent 等 |
| `agent_tool_graph.py` | 工具依赖图 + 能力注册表 + 工具元数据 + 自发现 |
| `agent_decompose.py` | Phase 0: 任务分解引擎 |
| `agent_hypothesis.py` | Phase 1: 多假设 + 锦标赛 + 失败分类 |
| `agent_resource.py` | Phase 2: 资源统一管控 |
| `agent_runtime.py` | V5 引擎: SymbolTable、MemoryStore、ProjectGraph |
| `agent_project.py` | 项目引擎: 分解→执行→验证→重试→报告+经验库 |
| `agent_context.py` | 智能上下文压缩（分层摘要+滑动窗口+重要性评分） |
| `agent_experience.py` | 经验库: 跨任务 pattern 匹配 + AVOID 提示 |
| `agent_parallel.py` | 并行执行引擎（工具链并行+假设并行验证） |
| `agent_sandbox.py` | 安全沙箱（命令过滤+文件系统守卫+审计日志） |
| `agent_learning.py` | 跨会话学习（SQLite持久化+失败模式库+自适应选择） |
| `agent_obs.py` | 可观测性（决策追踪+性能分析+仪表盘） |
| `agent_streaming.py` | 流式响应（LLM边生成边显示+可中断） |
| `agent_composition.py` | 高阶工具组合（管道+复合工具+条件链） |
| `agent_shared.py` | 多Agent共享上下文（共享空间+符号表+协调器） |
| `agent_strategy.py` | Layer 1: 策略自优化（Prompt进化+Tool学习+策略切换+A/B） |
| `agent_loop.py` | Layer 2: 自主循环（文件监控+连续循环+健康监控） |
| `agent_loop_monitor.py` | Layer 2: 循环监控（日志+统计+健康+回滚验证） |
| `agent_evolution.py` | Layer 3: 约束进化（接口不变+差分验证+多目标评估） |
| `auto_verify.py` | Layer 2: 自动验证脚本（测试→修复→提交/回退） |
| `run_agent.py` | 启动器（默认走 V5 引擎） |

### 运行方式

```bash
python -X utf8 run_agent.py "问题"                    # 单次提问
python -X utf8 run_agent.py                            # 交互模式
python -X utf8 run_agent.py "任务" --sandbox           # 安全沙箱（只读）
python -X utf8 run_agent.py "任务" --report            # 性能报告
python -X utf8 run_agent.py "任务" --stream            # 流式输出
python -X utf8 run_agent.py "任务" --pipeline NAME     # 执行管道
python -X utf8 run_agent.py "任务" --dashboard         # 仪表盘
python -X utf8 run_agent.py "任务" --trace             # 决策追踪
python -X utf8 run_agent.py --self-host                # 自举验证（第3层）
python -X utf8 run_agent.py --evolve                   # 约束进化验证（第3层）
python -X utf8 run_agent.py --auto-evolve              # 自动化进化闭环（第3层）
python -X utf8 run_agent.py --code-evolve              # Agent自主改代码闭环（第3层）
python -X utf8 run_agent.py --review-evolve             # 带审查的进化闭环（第3层）
python -X utf8 agent_loop.py --watch                   # 文件监控（第2层）
python -X utf8 agent_loop.py --continuous              # 连续循环（第2层）
python -X utf8 agent_loop.py --status                  # 查看统计（第2层）
```

### 关键设计

- **配置与逻辑分离**: `agent_policy.san` 纯数据，非程序员可直接编辑，修改后自动热重载
- **决策记录**: `_决策记录` 字典存储每轮完整推理链
- **概率三态**: `TritValue.confidence` 字段，贝叶斯置信度传播（`传播置信度 = 上游 × 当前`）
- **`#include` 预处理**: `agent.san` 通过 `#include "ternary_agent/agent_policy.san"` 内联策略

### 四层进化架构

```
Layer 3: Knowledge Layer
  - MetaLearningDB（项目经验数据库）
  - TaskEmbedding（任务向量化）
  - ClusterLearning（自动聚类）
  - 目标：不同任务→不同策略（条件最优）
        ↓
Layer 2: Evolution Layer
  - ParameterRanker（参数影响力排名）
  - CostAwareRanker（收益/成本排名）
  - ExplorationBudget（探索预算）
  - UCBExploration（UCB探索策略）
        ↓
Layer 1: Policy Layer
  - ConfigSchema（7个可进化配置参数）
  - StrategySchema（策略参数化）
  - HypothesisSchema（候选参数）
        ↓
Layer 0: Frozen Core（不可修改）
  - Reviewer（代码审查）
  - TernaryEngine（三态决策）
  - PatchHistory（历史记录）
  - TaskReplay（任务回放）
```

### 三层知识体系

```
Layer 3: Global Knowledge（云端）
  - 不共享具体Patch历史（项目差异大）
  - 共享元知识：任务模式→策略模式
  - 新用户开箱即用

Layer 2: Project Memory（项目）
  - sanyan.db = 项目大脑
  - 最有价值的一层

Layer 1: Personal Memory（个人）
  - 用户偏好/习惯
  - 绝不共享
```

### LLM知识 vs Agent知识

| 类型 | LLM有 | Agent需要 | 价值 |
|------|-------|-----------|------|
| 世界知识 | ✓ | ✗ | 低（已预训练） |
| 项目知识 | ✗ | ✓ | 高（MetaLearningDB） |
| 验证后知识 | ✗ | ✓ | 最高（有证据） |

```
LLM知识 = Prior（推测）
Agent知识 = Evidence（证据）

LLM解决"我知道什么"
Agent知识库解决"在这个项目里什么真的有效"
```

### Agent 已知修复（2026-06-13）

- **`保护()` 返回字典**: `decision.san` 中 `保护()` 原返回列表，改为返回字典
- **`规则降级()` 调用方式**: `query_weather()` 未定义 → 改为 `调度工具("query_weather", 城市)`
- **`好感要求` 安全读取**: `_V` 未定义时 try/catch 保护，默认好感=50

## 自举层级

| 层级 | 状态 | 说明 |
|------|------|------|
| Level 0 | ✅ | Python evaluator 作为宿主编译器 |
| Level 1 | ✅ | bytecode_compiler.san 用三言写 |
| Level 2 | ✅ | VM 加载 A → 编译 B → B 编译 C → B==C（不动点验证） |
| Level 3 | ✅ | 318 行 C 种子 VM → TCC ~2KB 可审计二进制 |
| Level 4 | ✅ | 617 行 x86_64 NASM 汇编 VM，无需 C 编译器 |

```bash
# Level 3 编译
tcc -nostdlib csrc/sanyan_vm_seed.c -o sanyan_vm
# Level 4 汇编
nasm -f bin -o sanyan_vm csrc/sanyan_vm_l4.asm
```

## ISA v2

| opcode | 编号 | 说明 |
|--------|------|------|
| LOAD16 | 0x3B | 2 字节变量索引 |
| STORE16 | 0x3C | 2 字节变量索引 |
| CALL32 | 0x3D | 4 字节函数地址 |
| PUSH_STR16 | 0x3E | 2 字节字符串长度 |
| CLOSURE | 0x3F | 创建堆闭包对象 |

## 工具

| 工具 | 文件 | 用途 |
|------|------|------|
| 汇编器 | `asm.py` | 汇编文本 → .bin |
| 反汇编器 | `disasm.py` | .bin → 反汇编（--hex/--brief/--export） |
| 验证器 | `verify.py` | JMP/LOAD/STORE 边界检查 |
| 编译器 | `sanyanc.py` | .san → .bin（S-表达式 + sugar 双语法） |
| 预检 | `preflight.py` | 发版前全量检查（lint/mypy/全测试/编码/自举） |

## 环境

- **Python**: `python`（≥3.12）
- **UTF-8**: 运行 `.san` 文件时始终用 `python -X utf8`

## Git 操作

**⚠ 提交规则**：仅在以下情况提交到 GitHub，其余情况等待用户指令：
- 重大功能完成（如新模块、新系统）
- 较大重构完成
- 修复 CI 失败

日常小改动、调试、提示词调优等一律不提交，等用户确认后再操作。

**⚠ 推送规则**：功能开发中优先本地保存，不做 `git push`：
```bash
git add -A
git commit -m "本地保存：xxx"   # 不加 --push
```

**⚠ 推送前强制自查**：
```bash
python -X utf8 preflight.py          # 全量: lint + mypy + 全测试 + 编码 + 自举
python -X utf8 preflight.py --quick  # 快速: 跳过自举
```

preflight 绿了 → `git push`。红了 → 修完再推。

**提交信息使用中文**。

## 测试

```bash
python -X utf8 preflight.py          # 包含全部测试
# 或单独：
python -X utf8 tests/test_core.py -v      # 138 项
python -X utf8 tests/test_self_host.py -v # 自举 8 项(含 Level 2+3)
python -X utf8 tests/test_vm.py -v        # VM 91 项
python -X utf8 tests/test_diff_fuzz.py -v # 差分模糊 12 项
python -X utf8 tests/test_effect_types.py -v # 效应类型 30 项
python -X utf8 tests/run_all.py           # 集成 46 项
```

## 代码约定

### 操作注册双语规则

每个 `ops/*.py` 文件必须同时注册中英文操作名：

```python
from ops.registry import register, register_alias as _ra
register('source', _source_op)
_ra('来源', 'source')
```

### 异常体系

使用 `values.py` 中的 `Sanyan*` 系列异常：`SanyanSyntaxError`、`SanyanTypeError`、`SanyanValueError`、`SanyanRuntimeError`、`SanyanNameError`、`SanyanKeyError`、`SanyanAttributeError`、`SanyanIOError`

### 全角符号

**绝对不能** 为了通过测试而将全角符号（`（` `）` `，` `；` 等）转换为半角。

### 注释

每次增加或修改代码，必须为整段代码写中文注释。

### 预处理

`#include` 展开统一使用 `preprocess.py` 中的 `preprocess_includes(code)` 函数。
