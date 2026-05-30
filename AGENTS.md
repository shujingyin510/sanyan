# AGENTS.md — 三言项目维护约定

## 自举状态（2026-06）

**完全自举已达成。** VM 编译产出 `stdlib/bytecode_compiler.bin` 与求值器编译产出逐字节相同（5692 字节）。
新增 `tests/test_self_host.py` 作为正式自举检测测试。

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
- test_ops_ext.py 26/26（含 1 项 skip）
- test_lsp.py 6/6
- test_package.py 6/6
- test_iot.py 25/25
- test_sugar_san.py 45/45
- test_llvmgen.py 53/53
- test_dp_python.py 10/10
- test_self_host.py 1/1
- test_vm.py 73/73
- test_c_vm.py 1/1（需 C 编译器）
- test_llvm_native.py（需 C 编译器，否则 skip）
- run_all.py 43/43

Python 文档同步：首次或每次代码修改后建议运行：
```bash
python doc_sync.py
```
这会同步版本号、检查 BUILTIN_OPS 与手册一致性、检查异常体系。

## 文档自动维护

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

**必须为关键代码添加中文注释**，尤其是：
- 模块级 docstring：说明模块职责、核心类/函数
- 公共函数/方法：参数说明、返回值、副作用
- 复杂逻辑：算法思路、设计决策、非显而易见的约束
- 魔法数字/常量：解释来源和含义

注释风格：
- Python：docstring 用中文，行内注释简明扼要
- Sanyan (.san)：`//` 行注释，关键函数上方加注释
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