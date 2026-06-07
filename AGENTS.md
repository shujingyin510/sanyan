# AGENTS.md — 三言项目维护约定

## Agent 系统（v0.3，2026-05）

三言 Agent 是**可读决策 DSL**——决策过程对非程序员透明可读。

### 架构

```
用户提问 → 规则匹配 → LLM 调用 → 5 种认知态 → 5→3 映射 → 三态传播 → 保护门控 → 动作分发
  (关键词)    (DeepSeek)   AFFIRM/NEGATE     1/-1/0     上游×当前   高风险/超限   READY/TOOL
                           UNCERT/CONFLICTED   +置信度    +置信度     /增益不足    /HUMAN
```

### 文件结构

| 文件 | 用途 |
|---|---|
| `ternary_agent/agent.san` | Agent 核心逻辑（旧引擎，交互/单次模式） |
| `ternary_agent/agent_policy.san` | 纯数据策略（配置、阈值、映射规则、天气数据、场景规则） |
| `ternary_agent/decision.san` | 决策核心（信任感知规则匹配） |
| `agent_runtime.py` | **V3 引擎**：SymbolTable、MemoryStore、ProjectGraph、AgentRuntime |
| `agent_tools.py` | **V3 工具层**：analyze、find_symbol、replace_all 等 12 个工具 |
| `run_agent.py` | 启动器（`--auto` 走 V3，默认走旧引擎） |

### 运行方式

```bash
# 单次提问
python -X utf8 run_agent.py "老王找我借钱，借吗？"

# 交互模式（支持 /解释 N、/原因 N、/策略、热重载）
python -X utf8 run_agent.py
```

### 交互命令

| 命令 | 说明 |
|---|---|
| `/解释 N` | 解释第 N 轮决策的 6 步推理链 |
| `/原因 N` | 解释第 N 轮决策的原因（规则→认知→传播→动作→建议） |
| `/策略` | 显示当前策略概览（模型、阈值、场景规则） |
| `/最近` | 解释最近一次决策 |
| 修改 `agent_policy.san` | 自动热重载，无需重启 |

### 关键设计

- **配置与逻辑分离**: `agent_policy.san` 纯数据，非程序员可直接编辑
- **决策记录**: `_决策记录` 字典存储每轮完整推理链（问题、认知态、映射值、传播、动作、回答、规则上下文）
- **字典查找替代 if-else 链**: `映射到三态` 查 `五态映射规则` 字典，`认知态名` 查 `认知态中文` 字典
- **概率三态**: `TritValue.confidence` 字段，贝叶斯置信度传播（`传播置信度 = 上游 × 当前`）
- **声明式规则**: `场景规则` 列表驱动 `匹配规则()`，关键词匹配用户问题
- **`#include` 预处理**: `agent.san` 通过 `#include "ternary_agent/agent_policy.san"` 内联策略

### 测试

Agent 功能通过端到端 mock 测试验证（mock `http写` 返回模拟 LLM 响应）。

### Agent 已知修复（2026-06-02）

- **`保护()` 返回字典**: `ternary_agent/decision.san` 中 `保护()` 原返回列表，消费者用 `取键()` 期望字典，改为返回 `{action, reason, 投票结果}` 字典
- **`规则降级()` 调用方式**: `query_weather()` 未定义 → 改为 `调度工具(\"query_weather\", 城市)`
- **死代码移除**: 两个连续的 `传播后 == -1` 分支合并为一个
- **`好感要求` 安全读取**: `_V` 未定义时 try/catch 保护，默认好感=50

---

## 村庄观察器（`run_village_observe.py`，详情见 `docs/village_observer.md`）

桃花村 NPC 自主生活模拟 → LLM 驱动对话 → 三态信任演变 → SVG 图表 + JSON 日志。

```bash
python -X utf8 run_village_observe.py          # 默认 10 天
python -X utf8 run_village_observe.py --verbose # 详细三态推理链
```

核心特性：Python 主循环逐日调用 LLM、夜间 8 项负面事件池、事件记忆跨日追踪、LLM 五类语气检测、动态 δ 加权（性格×天气×长度×位置）、宏观趋势分析、SVG 交互图表。

---

## 村庄观察器（run_village_observe.py，2026-06）

桃花村 NPC 自主生活模拟 → LLM 驱动对话 → 三态信任演变 → SVG 图表 + JSON 日志。

### 运行方式

```bash
python -X utf8 run_village_observe.py          # 默认 10 天模拟
python -X utf8 run_village_observe.py --days=30 # 自定义天数
python -X utf8 run_village_observe.py --verbose # 详细三态推理链
```

### 核心特性

| 特性 | 说明 |
|---|---|
| **Python 主循环** | 逐日调用 LLM，非单次 `开始观察()` |
| **夜间事件** | 8 项负面事件池，按 NPC 角色/性格加权，可配置 delta |
| **事件记忆** | 跨日追踪 + 因果链累积，下一天对话注入历史上下文 |
| **行为分类** | 关键词匹配优先 + LLM 回退分类器 |
| **语气检测** | 友好/打趣/抱怨/平淡/冲突 5 类，按信任值覆盖语气 |
| **信任传播** | 直接对话 × 间接提及链式传播，贝叶斯置信度 |
| **动态 delta** | Δ = 基础值 × 性格均值 × 天气 × 长度 × 位置 |
| **三态区间** | 真 ●●● / 可能 ◐◐◐ / 假 ○○○ 统一显示 |
| **保守决策** | 可能区保持信任不惩罚，对冷淡 NPC 不主动攻击 |
| **SVG 图表** | 交互式多线图（复选框隐藏 NPC，hover tooltip） |
| **JSON 导出** | `village_log.json` 全量结构化数据 |
| **凝聚度指数** | 全对平均 + 活跃对平均 + 三态分布 |
| **信任矩阵热力图** | 每日详细输出（verbose 模式） |

### 技术要点

- **作用域访问**: 使用 `ev._scopes[0]` 而非已删除的 `ev.scope_vars`
- **TritValue 解包**: 所有从求值器变量读取的字典值需 `.value` 解包
- **`line2` 初始化**: 设为 `None` 防止 UnboundLocalError
- **场景描述**: 从 NPC 日程数据生成（非 LLM 幻想）

---

## 自举状态（2026-06）

**完全自举已达成。** VM 编译产出 `stdlib/bytecode_compiler.bin` 与求值器编译产出逐字节相同（5692 字节）。
新增 `tests/test_self_host.py` 作为正式自举检测测试。

**llvmgen.san 自举完成（V5）。** 11 个 Python 辅助函数和 6 个全局变量已内联到源码中，
`compile_llvmgen.py` 不再注入任何外部依赖。`llvmgen.bin`（69948 字节）可直接从源码编译。

**sugar.bin 自举验证完成。** 新增 `tests/test_sugar_self_host.py`，验证 sugar.san 编译产出
与参考 sugar.bin 字节一致（SHA256 校验）。

VM 关键修复：
- `DICT_SET` 不 push 返回值（消除主栈泄漏源）
- `CALL` 记录 `stack_base = len(stack) - arg_count`，`RET` 执行 `del stack[base:]`（栈隔离）
- `from_bin` 自动运行模块初始化代码
- `_exec_frame` 正确隔离外层 vars
- 新增 `DICT_KEYS`(0x32) 操作码
- 字节码格式升级：代码大小从 16 位改为 32 位（支持 >64KB 字节码）
- `DICT`/`LIST_NEW` 空栈安全处理（`新字典`/`新列表` 无参数时不 pop）

## 三态系统状态（2026-06）

**完整闭环已达成。** TritValue 统一承载数值/字符串/列表/字典 + 置信度(0-1) + 来源链 + 时间戳。

| 层 | 状态 | 关键实现 |
|----|------|----------|
| Python 求值器 | ✅ | 52 API（构造/传播/判定/冲突/融合/衰减/序列化/容器/信念）|
| 字节码 VM | ✅ | 算术/比较/逻辑/输出 自动传播信度 |
| C VM | ✅ | OBJ_TRIT 堆类型 + 紧凑编码 |
| LLVM 运行时 | ✅ | rt_trit_* 辅助函数系列 |

**核心文件：**
- `ternary_core.py` — TritValue 多类型承载力
- `ops/type_ops.py` — 45 个三态操作
- `ops/ternary_time_ops.py` — 衰减/序列化
- `ops/ternary_container_ops.py` — 三态列/字典
- `ops/ternary_math_ops.py` — 分布/熵/校准
- `docs/ternary-confidence.md` — 三层设计规范
- `docs/ternary-truth-table.md` — Kleene+Bayesian 真值表
- `docs/roadmap.md` — 扩展路线图

编译器关键修复：
- `(等于 (ord (子串 n 0 1)) 34)` 替代 `(str_equals ... "\"")`（tokenizer 不认 `\"` 转义）
- `(set op "set")` 对非列表节点
- `编译做体` 函数（DO 体循环编译）
- OP映射 补全了中英文双语别名（约 50 个操作，覆盖全部 VM 操作码）
- `fn` 处理器函数地址公式修正：`(减 (表长 w) 12)`，导出地址指向参数 STORE
- sugar.san `导出` 解析器修复：遇到第二个 `导出` 关键字时停止读取
- 字节码编译器源码关键字全部使用中文（`set`→`设`、`fn`→`定义`、`if`→`若` 等）

Python 求值器关键修复：
- `param_matcher.py`: `evaluate_args` 不再将列表代码表达式（如 `['取', 'a', 'i']`）当作数据字面量返回而不求值，修复自举编译时 `编译节点` 收到未求值 AST 节点导致的 C 栈溢出
- `ops/arithmetic_ops.py`: `div` 和 `mod` 补全 `_to_tritvalue()` 转换，修复变量解析返回 Python `int` 时类型检查失败
- `llvmgen/compiler.py`: `_list_get_safe` 增加未求值列表参数的保护转换

## VM 独立运行（.bin 文件）

| 部件 | .bin 路径 | 大小 | VM 加载 |
|---|---|---|---|
| 字节码编译器 | `stdlib/bytecode_compiler.bin` | ~5.7KB | ✅ |
| sugar.san 解析器 | `stdlib/sugar.bin` | ~10KB | ✅ |
| llvmgen.san LLVM 编译器 | `stdlib/llvmgen.bin` | ~72KB | ✅ |

编译方法：
```bash
# 字节码编译器
python -X utf8 -c "from compile_bytecode import compile_source; compile_source(open('stdlib/bytecode_compiler.san').read(), 'stdlib/bytecode_compiler.bin')"

# sugar.san（通过 sugar.parser 解析 + 字节码编译器编译）
python -X utf8 -c "
from sugar.parser import parse_code
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache
src = open('stdlib/sugar.san').read()
ast, _ = parse_code(src)
fixed = []
for s in ast[1:]:
    if isinstance(s, list) and s[0] == 'export':
        for n in s[1:]:
            if n != '导出': fixed.append(['export', n])
    else: fixed.append(s)
clear_cache()
e = SanyanEvaluator(max_loop_steps=500000)
compiler = e.eval(['import', 'stdlib/bytecode_compiler.san'])
compiler.call(e, ['编译字节码', ['do']+fixed, 'stdlib/sugar.bin', {}])
"

# llvmgen.san（直接编译，V5 辅助函数已内联）
python -X utf8 compile_llvmgen.py
```

注：llvmgen.san 的 LLVM IR 代码生成通过 Python evaluator 运行 .san 文件实现自举（V5 辅助函数已内联，无需 Python 注入）。

## 环境

- **Python**: `python`（≥3.12，`pyproject.toml` 要求）
- **Git**: 直接在项目目录下使用 `git`（PowerShell 终端可用，cmd.exe 需完整路径）
- **UTF-8**: 运行 `.san` 文件时始终用 `python -X utf8 main.py ...`

## Git 操作

**⚠ 提交规则**：仅在以下情况提交到 GitHub，其余情况等待用户指令：
- 重大功能完成（如新模块、新系统）
- 较大重构完成（如架构调整、文件合并拆分）
- 修复 CI 失败（如 ruff/mypy/coverage 不通过）

日常小改动、调试、提示词调优等一律不提交，等用户确认后再操作。

**⚠ 推送规则**：功能开发中优先本地保存，不做 `git push`。只有功能全通且用户明确指令时才推送：
```bash
git add -A
git commit -m "本地保存：xxx"   # 不加 --push
```
等多轮测试验证完再 `git push`。

在项目目录下直接使用 `git`（bash 工具自动使用项目 workdir）：

```bash
git add -A
git commit -m "..."
git push
```

- **提交信息使用中文**：`git commit -m "..."` 中的提交说明必须用中文书写，清晰描述改动的目的和内容

### 推送前 MD 文件检查

每次 `git push` 前，必须对仓库中所有 `*.md` 文件做内容差异检查，确认增删改内容：

```bash
# 查看自上次提交以来所有 .md 文件的变更
git diff --stat HEAD -- '*.md'
# 查看具体内容变动
git diff HEAD -- '*.md'
```

- **新增**的文件应在 `git diff` 中可见，确认内容正确
- **删除**的文件应确认是预期的删除
- **修改**的内容应检查无意外改动
- 推送至远程前先 Review 一遍 `.md` 差异，确保文档变更与代码变更一致

### 推送前 CI 检查

每次 `git push` 前，必须确认 GitHub CI（Actions）状态正常：

```bash
# 查看当前分支最近一次 CI 运行状态
gh run list --branch $(git branch --show-current) --limit 1
# 如需等待正在运行的 CI 完成
gh run watch
```

- 推送前确保本地测试全部通过（见下文#测试）
- 如有 CI 正在运行，等待其完成后再推送新提交
- 若 CI 失败，先修复再推送

### 推送前清理多余文件

每次 `git push` 前，必须清理仓库中不应提交的临时文件：

```bash
# 查看未跟踪文件
git status --short | grep "^??"
```

常见需清理的文件：
- `_diag.py`、`_test_*.py` — 临时调试/测试脚本
- `*.log` — 日志文件
- `__pycache__/` — Python 缓存
- `*.pyc` — 编译字节码
- `dist/`、`build/` — 构建产物
- `*.bin` 临时输出 — 非 stdlib 的二进制文件

确认无误后执行 `git add -A`，确保只提交有意义的文件。

## 测试

每次代码修改后必须运行全部测试（16 套）：

```bash
python -X utf8 tests/test_core.py -v      # 运行时核心单测 138 项
python -X utf8 tests/test_commands.py -v  # 命令模块单测 18 项
python -X utf8 tests/test_parser.py       # 解析器 AST 校验 28 项
python -X utf8 tests/test_ops.py -v       # ops 模块单测 92 项
python -X utf8 tests/test_ops_ext.py -v   # 扩展 ops 单测 64 项
python -X utf8 tests/test_lsp.py -v       # LSP 测试 6 项
python -X utf8 tests/test_package.py -v   # 包管理器测试 6 项
python -X utf8 tests/test_iot.py -v       # IoT 测试 25 项
python -X utf8 tests/test_sugar_san.py -v # sugar.san 测试 45 项
python -X utf8 tests/test_llvmgen.py -v   # LLVM 代码生成测试 53 项
python -X utf8 tests/test_dp_python.py -v # S 表达式解析测试 10 项
python -X utf8 tests/test_llvm_native.py -v # LLVM 原生编译测试（需 C 编译器）
python -X utf8 tests/test_self_host.py -v # 自举验证测试 5 项
python -X utf8 tests/test_sugar_self_host.py -v # sugar.bin 自举验证 3 项
python -X utf8 tests/test_vm.py -v        # VM 字节码测试 91 项
python -X utf8 tests/test_c_vm.py -v      # C VM 测试 14 项（需 gcc）
python -X utf8 tests/test_agent.py -v     # Agent 测试 31 项
python -X utf8 tests/run_all.py           # 集成测试 46 项

全部通过才算成功：
- test_core.py 138/138（含闭包+三态测试）
- test_commands.py 18/18
- test_parser.py 28/28
- test_ops.py 92/92
- test_ops_ext.py 64/64
- test_lsp.py 6/6
- test_package.py 6/6
- test_iot.py 25/25
- test_sugar_san.py 45/45
- test_llvmgen.py 53/53
- test_dp_python.py 10/10
- test_self_host.py 5/5
- test_sugar_self_host.py 3/3
- test_vm.py 91/91
- test_c_vm.py 14/14（含交叉验证，需 gcc）
- test_agent.py 31/31
- run_all.py 46/46

### 覆盖率配置

CI 使用 `pytest --cov=. --cov-report=xml` 测量覆盖率，阈值 75%。

`.coveragerc` 排除的文件及原因：

| 排除文件 | 原因 |
|----------|------|
| `build_combined.py`, `build_exe.py`, `compile_llvmgen.py`, `setup.py`, `sanyancc.py` | 构建脚本，非运行时代码 |
| `run_agent.py`, `run_v2.py`, `run_v2_demo.py`, `run_village_demo.py` | 演示/启动器，需 LLM 网络调用，无法单测 |
| `gui.py`, `dap_server.py`, `lsp_server.py`, `main.py`, `lsp/*` | GUI/服务器，需图形或网络环境 |
| `doc_sync.py`, `sanfmt.py` | 工具脚本，非核心运行时 |
| `ops/package_ops.py`, `ops/net_ops.py` | 需外网访问（GitHub 包下载/HTTP 请求） |
| `llvmgen/helpers.py`, `llvmgen/build.py`, `llvmgen/ir_fixes.py`, `llvmgen/compiler.py` | 需 llvmlite 依赖，CI 环境版本与本地不同步 |
| `utils/*`, `benchmark/*`, `scripts/*`, `examples/*`, `csrc/*` | 工具/基准/示例/C 源码 |

**未排除的核心文件**（覆盖率待提升）：
- `vm.py` (63%) — 字节码 VM，需补充更多 opcode 测试
- `compile_bytecode.py` (58%) — 字节码编译器，需补充编译路径测试
- `llvmgen/codegen.py` (58%) — LLVM 代码生成，需补充更多 IR 生成测试
- **2026-05-30 修复记录已合并到下方「架构治理记录」**

Python 文档同步：首次或每次代码修改后建议运行：
```bash
python doc_sync.py
```
这会同步版本号、检查 BUILTIN_OPS 与手册一致性、检查异常体系。

## 文档自动维护

### 任务完成后检查清单

**每次任务完成后，必须执行以下检查：**

1. **运行全部测试**：确认所有现有功能未被破坏
   ```bash
   python -X utf8 tests/test_core.py -v
   python -X utf8 tests/test_commands.py -v
   python -X utf8 tests/test_parser.py
   python -X utf8 tests/test_ops.py -v
   python -X utf8 tests/test_ops_ext.py -v
   python -X utf8 tests/test_sugar_san.py -v
   python -X utf8 tests/test_llvmgen.py -v
   python -X utf8 tests/test_self_host.py -v
   python -X utf8 tests/test_vm.py -v
   python -X utf8 tests/run_all.py
   ```

2. **更新所有 md 文件**：检查并更新以下文件中与本次改动相关的内容
   - `README.md` — 版本号、功能列表、项目结构
   - `README_EN.md` — 英文版同步
   - `ARCHITECTURE.md` — 架构文档
   - `CHANGELOG.md` — 变更日志
   - `CONTRIBUTING.md` — 贡献指南
   - `docs/manual.md` — 用户手册
   - `docs/manual.md` — 用户手册（语法、命令速查、错误说明）
   - `docs/llvm.md` — LLVM 代码生成文档
   - `docs/sugar_grammar.md` — 糖语法规范
   - `docs/llvm.md` — LLVM 文档
   - `AGENTS.md` — 本文件

3. **检查文档一致性**
   - README 版本号与 `pyproject.toml` 一致
   - README 项目结构与实际文件列表一致
   - CHANGELOG 条目格式正确（日期倒序、四分类）
   - 测试数量与实际一致

### pyproject.toml / README.md

- 发新版时同步更新 `pyproject.toml` 中 `version` 和 README 顶部版本号
- README **项目结构** 文件树需与实际文件列表一致

### CHANGELOG.md

- 新增版本条目时按日期倒序排列
- 每个条目分 **新增** / **变更** / **修复** / **文档** 四个类别
- 引用具体的文件路径和关键改动说明

### docs/manual.md

- **内置命令速查表**（第 17 节）需与 `runtime.py:BUILTIN_OPS` 一致
- **错误信息说明**（第 18 节）需与 `values.py` 中 `Sanyan*` 异常类一致

## 代码约定

### 注释

**每次增加或修改代码，必须为整段代码写中文注释。** 包括：
- 模块级 docstring：说明模块职责、核心类/函数
- 每个函数/方法：docstring 说明参数、返回值、副作用
- 每个代码块：说明目的和逻辑
- 复杂逻辑：算法思路、设计决策、非显而易见的约束
- 魔法数字/常量：解释来源和含义

注释风格：
- Python：docstring 用中文，行内注释简明扼要
- Sanyan (.san)：`//` 行注释，每个函数上方必须加注释
- C (csrc/)：`/* */` 块注释，函数头注释说明参数和返回值

不需要注释的情况：简单赋值、标准模式（if/for）、自解释的变量名。

### 全角符号

**绝对不能** 为了通过测试而将全角符号转换为半角符号。全角符号（`（` `）` `，` `；` `＂` `＂` 等）是母语编程的核心特性。

### 异常体系

运行阶段所有 `raise` 必须使用 `values.py` 中的 `Sanyan*` 系列异常：
- `SanyanSyntaxError` — 参数格式/个数错误
- `SanyanTypeError` — 类型错误
- `SanyanValueError` — 值错误（除零、无效输入等）
- `SanyanRuntimeError` — 运行时错误
- `SanyanNameError` — 未定义符号
- `SanyanKeyError` — 字典键访问错误
- `SanyanAttributeError` — 属性/方法不存在错误
- `SanyanIOError` — 文件/IO 错误

仅 `parser.py` 和 `sugar.py` 的解析阶段可用 Python 原生 `SyntaxError`。

### 作用域

- 变量查找：`evaluator.has_var(name)` / `evaluator.get_var(name)` （跨作用域）
- 变量设置：`evaluator.set_var(name, value)` 或 `evaluator.vars[name] = value`（当前作用域）
- 遍历所有变量：`evaluator.all_scoped_vars()`（调试/补全用）
- 函数调用：`evaluator.push_scope()` / `evaluator.pop_scope()`

### 预处理

`#include` 展开统一使用 `preprocess.py` 中的 `preprocess_includes(code)` 函数。

## STM32 固件开发

交叉编译工具链：`sanyancc.py` → `firmware_data.h` → `arm-none-eabi-gcc`。

### 关键教训：BSS 初始化

**`_start()` 必须显式清零所有 BSS 段全局变量**。链接脚本 `_sbss`/`_ebss` 符号在 arm-none-eabi-gcc 上可能未正确定义，导致依赖 `.bss` 段清零的循环写出错误地址：

```c
void _start(void) {
    /* 显式初始化每个 BSS 变量 */
    _sp = 0;
    _ticks = 0;
    for (int i = 0; i < 16; i++) _read_devs[i] = 0;
    for (int i = 0; i < 16; i++) _write_devs[i] = 0;
    for (uint32_t i = 0; i < FIRMWARE_VARS; i++) _vars[i] = 0;
    init();
    vm_run();
    while (1);
}
```

不要依赖 `.data` 复制循环和 `.bss` 清零循环——STM32F103 链接脚本可能未正确生成 `_sdata`/`_edata`/`_sbss`/`_ebss` 符号。

### 字节码解释器

`runtime_stm32.c` 中的 VM 使用 `switch` 分派、`firmware_code[]` 字节码。所有指令定长定宽，栈式架构。关键设备：
- ID 13: PC13 LED（active low）
- SysTick @ 8MHz HSI：重装载值 8000-1 → 1ms 中断

**不要在 delay 循环中使用 `__asm__("wfi")`**——WFI 让内核进入睡眠模式，ST-LINK SWD 连接会断开（"Unable to get core ID"）。纯忙等 `while (_ticks - start < ms);` 即可。

### 编译烧录

```bash
export PATH="$PATH:/d/Program Files (x86)/GNU Arm Embedded Toolchain/10 2021.10/bin"
arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb -Os -ffreestanding -nostartfiles \
  -I. -T stm32_flash.ld runtime_stm32.c -o firmware.elf
arm-none-eabi-objcopy -O binary firmware.elf firmware.bin
# 用 CubeProgrammer 或 st-flash 烧写 firmware.bin 到 0x08000000
```

## C VM (csrc/runtime.c)

`csrc/runtime.c` 是 C 语言字节码解释器，支持全部 52 个操作码。编译运行：

```bash
# 必须通过 MSYS2 bash 调用 gcc（直接调用 gcc.exe 无法输出文件）
# 设置环境变量 MSYS2_PATH 指向 MSYS2 安装路径，或直接使用完整路径
${MSYS2_PATH:-D:/msys64}/usr/bin/bash.exe -lc "gcc ${PROJECT_PATH:-/d/Test/sanyan}/csrc/runtime.c -o ${PROJECT_PATH:-/d/Test/sanyan}/csrc/runtime.exe -std=c99 -Wall"
./csrc/runtime.exe firmware.bin
```

### 值系统
- 标记指针：LSB=1 为整数，LSB=0 为堆对象（带 `ObjType` 头部）
- 堆类型：`rt_str_t`、`rt_list_t`、`rt_dict_t`
- 字典键支持整数和字符串，通过 `key_eq()` 按类型比较

### 递归打印
`print_value()` 递归输出任意值：
- int → `printf("%d")`
- str → `printf("%s")`
- list → `[item, …]`
- dict → `{key: val, …}`

### 已知限制
- **GCC 必须通过 MSYS2 bash 调用**：`D:/msys64/usr/bin/bash.exe -lc "gcc ..."`, 直接调用 `gcc.exe` 无法输出文件（MSYS2 路径映射问题）
- Windows 路径需转为 MSYS2 格式：`D:\xxx` → `/d/xxx`
- 字典当前有最大条目限制（`DICT_MAX=256`）

## LLVM 工具链

LLVM IR → 原生代码管线依赖 `llc` + `gcc`：

| 工具 | 路径 | 用途 |
|---|---|---|
| `llc` | `D:\msys64\ucrt64\bin\llc.exe` | LLVM IR → 目标文件 (`.o`) |
| `gcc` | MSYS2 (`D:\msys64\usr\bin\gcc.exe`) | 编译运行时 C 源码 + 链接 |

`llc` 可通过 MSYS2 ucrt64 直接调用（不依赖 bash 路径映射），`gcc` 必须通过 MSYS2 bash 调用：

```bash
# llc：IR → .o（可直接调用）
${MSYS2_PATH:-D:/msys64}/ucrt64/bin/llc.exe input.ll -filetype=obj -o output.o

# gcc：编译 C（必须通过 MSYS2 bash）
${MSYS2_PATH:-D:/msys64}/usr/bin/bash.exe -lc "gcc -c /d/path/to/source.c -o /d/path/to/output.o -std=c99 -O2"

# gcc：链接（必须通过 MSYS2 bash）
${MSYS2_PATH:-D:/msys64}/usr/bin/bash.exe -lc "gcc /d/path/to/obj1.o /d/path/to/obj2.o -o /d/path/to/output.exe -lm"
```

### llvmgen/runtime.c 已知问题

`gcc -c runtime.c -std=c99 -Wall` 编译通过，无警告。

## 架构治理记录（2026-06-02）

### 运行时合并

`runtime_components.py` → `runtime.py`，`debug_eval.py` → `evaluator.py`，`eval_helpers.py` 拆为 `eval_utils.py`（纯工具）+ 合回 `evaluator.py`（求值逻辑）。净删 3 文件。

### 标准库拆分

`stdlib/combined.san`(2960 行) → `lexer.san`(199 行) + `parser.san`(739 行) + `codegen.san`(2022 行)，原文件变薄包装器。

### VM 扩展

- PUSH_FLOAT(0x48) opcode：IEEE 754 double 浮点常量
- `_exec_arithmetic`(92 行) 拆为 `_exec_arithmetic`(算术) + `_exec_bitwise`(位运算/字节)
- VM 测试 79→91（位运算/字符串扩展/字节操作）

### C VM 修复

- UTF-8 字符计数：`utf8_char_len`/`utf8_byte_offset`/`utf8_substr`
- float 字典键：`hash_key`/`key_eq` 支持 `OBJ_FLOAT`，`rt_float_t` + `rt_float_new()`

### 类型系统

- `type_checker.py`：50+ 内置操作的类型签名表，求值前做字面量参数断言
- `values.py:check_type()`：支持英文类型名（int/float/str/list/dict/num/any）
- 函数参数类型标注：`定义 f (x: int) { ... }` 在调用时校验

### LLVM 三态

- `llvmgen/runtime.c`：`rt_trit_add/sub/mul/div/mod` 运行时函数

### 工程改进

- `#include` 预处理移到 `sugar/parser.py:parse_code()` 入口
- 常量折叠：`compile_bytecode.py:_fold_constants()`
- LLVM 工具路径环境变量化：`MSYS2_PATH`/`CC`/`LLC_PATH`/`BASH_PATH`
- 启动器 `os.chdir()` → `PROJECT_ROOT` 常量
- `ensure_trit()` 边界转换包装
- `_DEFAULT_RECURSION_LIMIT` 常量化
- `_DISPATCH_NOT_FOUND` 哨兵分派器

### 测试

- 覆盖率 69.2% → 75.32%
- `test_core.py`：100 → 137 项
- `test_vm.py`：79 → 91 项
- 新增 type_checker/eval_utils/常量折叠专项测试
- mypy 37→0 错误，ruff 24→0 lint 警告

### P0/P1 修复（2026-06-03）

- **死代码**: `ternary_core.py` 删除 10 行不可达重复分支（`isinstance(value, list)` 二次判断）
- **抽象泄漏**: `_NO_CACHE_OPS` 从 `ops/dispatcher.py` 移除，缓存不影响 LLVM op 正确性
- **API 密钥**: `run_agent.py` 占位符 `\"sk-你的key\"` 改为显式 `sys.exit(1)` 报错
- **错误信息**: `sugar/parser.py:_expect()` 补全 9 种括号不匹配提示
- **CALL 启发式**: `vm.py` 添加注释说明参数计数扫描 STORE 的限制
- **类型系统**: `check_type()` 支持中英双名（int/str/list/dict/num/any）
- **项目清理**: `.gitignore` 加 `village_log.json`/`village_trust.html`/`*.log`
- **常量折叠**: `isinstance(op, str)` 检查防止参数列表被误判为常量 op