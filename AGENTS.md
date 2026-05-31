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
| `ternary_agent/agent.san` | Agent 核心逻辑（决策函数、记忆系统、追踪输出、规则引擎） |
| `ternary_agent/agent_policy.san` | 纯数据策略（配置、阈值、映射规则、天气数据、场景规则） |
| `run_agent.py` | 启动器（单次/交互/热重载） |

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

# llvmgen.san（通过 compile_llvmgen.py 注入辅助函数后编译）
python -X utf8 compile_llvmgen.py
```

注：llvmgen.san 的 LLVM IR 代码生成仍需 Python evaluator 执行（依赖 `compile_llvmgen.py` 注入的 28 个辅助函数）。

## 环境

- **Python**: `python`（≥3.12，`pyproject.toml` 要求）
- **Git**: 直接在项目目录下使用 `git`（PowerShell 终端可用，cmd.exe 需完整路径）
- **UTF-8**: 运行 `.san` 文件时始终用 `python -X utf8 main.py ...`

## Git 操作

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

每次代码修改后必须运行全部测试（14 套）：

```bash
python -X utf8 tests/test_core.py -v      # 运行时核心单测 52 项
python -X utf8 tests/test_commands.py -v  # 命令模块单测 18 项
python -X utf8 tests/test_parser.py       # 解析器 AST 校验 28 项
python -X utf8 tests/test_ops.py -v       # ops 模块单测 78 项
python -X utf8 tests/test_ops_ext.py -v   # 扩展 ops 单测 26 项
python -X utf8 tests/test_lsp.py -v       # LSP 测试 6 项
python -X utf8 tests/test_package.py -v   # 包管理器测试 6 项
python -X utf8 tests/test_iot.py -v       # IoT 测试 25 项
python -X utf8 tests/test_sugar_san.py -v # sugar.san 测试 45 项
python -X utf8 tests/test_llvmgen.py -v   # LLVM 代码生成测试 53 项
python -X utf8 tests/test_dp_python.py -v # S 表达式解析测试 10 项
python -X utf8 tests/test_llvm_native.py -v # LLVM 原生编译测试（需 C 编译器）
python -X utf8 tests/test_self_host.py -v # 自举验证测试 1 项
python -X utf8 tests/test_vm.py -v        # VM 字节码测试 73 项
python -X utf8 tests/test_c_vm.py -v      # C VM 测试 1 项（需 gcc）
python -X utf8 tests/run_all.py           # 集成测试 43 项

全部通过才算成功：
- test_core.py 52/52
- test_commands.py 18/18
- test_parser.py 28/28
- test_ops.py 78/78
- test_ops_ext.py 26/26（skip=0）
- test_lsp.py 6/6
- test_package.py 6/6
- test_iot.py 25/25
- test_sugar_san.py 45/45
- test_llvmgen.py 53/53
- test_dp_python.py 10/10
- test_self_host.py 1/1
- test_vm.py 73/73
- test_c_vm.py 1/1（需 C 编译器）
- test_llvm_native.py 2/3（dp_harness 测试需完整 LLVM→原生管线，parse_sanyan 已修复返回正确 AST）
- run_all.py 43/43

2026-05-30 修复记录：
- llvmgen/runtime.c：struct rt_list_s 移到使用函数之前，rt_list_push → rt_list_push_item，新增公共接口 `rt_make()` 用于 C 字符串→三言字符串转换
- LLVM compiler bootstrap 路径：S-expression set 字面量字符串创建全局变量；_make_bootstrap_harness 用 rt_make 包装 C 字符串参数（修复 parse_sanyan 入口函数不返回问题）
- VM import：.san → .bin 自动转换 + 自动编译 .bin 不存在时
- VM from_bin：导出表边界检查（不完整文件不崩溃）
- VM 所有操作码处理：栈下溢保护 + 类型安全比较/算术
- Python 求值器 dict ops 中 list→tuple 键转换
- Python 求值器 container_ops.generic_get 越界返回 0 替代抛异常
- test_http_get：改用 unittest.mock.patch 替代外网请求（去掉 skip）
- test_import_resolves / test_text_analysis：取消 skip，import 系统实际已可用（去掉 2 个 skip）
- LLVM codegen `_normalize_fn_format`：多语句函数体被截断为仅第一条语句，修复为将 `node[3:]` 包装为 `do` 块
- LLVM codegen `(div 1 0)`：`_check_div_zero` 生成 `icmp eq 0, 0`（常量 true）→ `rt_throw` 污染 `g_error`，修复为 AST 级别检测常量除零并跳过检查

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
   - `docs/syntax.md` — 语法文档
   - `docs/commands.md` — 命令参考
   - `docs/errors.md` — 错误说明
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
D:/msys64/usr/bin/bash.exe -lc "gcc /d/Test/sanyan/csrc/runtime.c -o /d/Test/sanyan/csrc/runtime.exe -std=c99 -Wall"
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
D:/msys64/ucrt64/bin/llc.exe input.ll -filetype=obj -o output.o

# gcc：编译 C（必须通过 MSYS2 bash）
D:/msys64/usr/bin/bash.exe -lc "gcc -c /d/path/to/source.c -o /d/path/to/output.o -std=c99 -O2"

# gcc：链接（必须通过 MSYS2 bash）
D:/msys64/usr/bin/bash.exe -lc "gcc /d/path/to/obj1.o /d/path/to/obj2.o -o /d/path/to/output.exe -lm"
```

### llvmgen/runtime.c 已知问题

`llvmgen/runtime.c` 存在编译错误（`rt_list_t` incomplete typedef、`rt_list_push` 未声明、`rt_str_join` 返回类型错误），这些是预存 bug，不影响 C VM (`csrc/runtime.c`)。