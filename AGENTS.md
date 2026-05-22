# AGENTS.md — 三言项目维护约定

## 自举状态（2026-05）

**完全自举已达成。** VM 编译产出 `stdlib/bytecode_compiler.bin` 与求值器编译产出逐字节相同（5442 字节，5406 字节码）。

VM 关键修复：
- `DICT_SET` 不 push 返回值（消除主栈泄漏源）
- `CALL` 记录 `stack_base = len(stack) - arg_count`，`RET` 执行 `del stack[base:]`（栈隔离）
- `from_bin` 自动运行模块初始化代码
- `_exec_frame` 正确隔离外层 vars
- 新增 `DICT_KEYS`(0x32) 操作码

编译器关键修复：
- `(等于 (ord (子串 n 0 1)) 34)` 替代 `(str_equals ... "\"")`（tokenizer 不认 `\"` 转义）
- `(set op "set")` 对非列表节点
- `编译做体` 函数（DO 体循环编译）
- OP映射 补全了中英文双语别名

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

每次代码修改后必须运行全部测试（10 套）：

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
python -X utf8 tests/run_all.py           # 集成测试 41 项
```

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
- test_llvm_native.py（需 C 编译器，否则 skip）
- run_all.py 41/41

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