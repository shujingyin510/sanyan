# AGENTS.md — 三言项目维护约定

## 环境

- **Python**: `python`（≥3.8，`pyproject.toml` 要求）
- **Git**: `"D:\Program Files\Git\cmd\git.exe"`（必须用完整路径，cmd.exe PATH 不含 Git）
- **UTF-8**: 运行 `.san` 文件时始终用 `python -X utf8 main.py ...`

## Git 操作

提交和推送统一使用完整路径（bash 工具中是 cmd.exe，PATH 不含 Git）：

```bash
"D:\Program Files\Git\cmd\git.exe" -C D:\Test\sanyan add -A
"D:\Program Files\Git\cmd\git.exe" -C D:\Test\sanyan commit -m "..."
"D:\Program Files\Git\cmd\git.exe" -C D:\Test\sanyan push origin main
```

或在 cd 到项目目录后使用 `git`（仅限 PowerShell 终端）。

## 测试

每次代码修改后必须运行全部测试（9 套）：

```bash
python -X utf8 tests/test_core.py -v      # 运行时核心单测 52 项
python -X utf8 tests/test_commands.py -v  # 命令模块单测
python -X utf8 tests/test_parser.py       # 解析器 AST 校验 28 项
python -X utf8 tests/test_ops.py -v       # ops 模块单测 78 项
python -X utf8 tests/test_lsp.py -v       # LSP 测试 6 项
python -X utf8 tests/test_package.py -v   # 包管理器测试 6 项
python -X utf8 tests/test_iot.py -v       # IoT 测试 25 项
python -X utf8 tests/test_sugar_san.py -v # sugar.san 测试 37 项
python -X utf8 tests/run_all.py           # 集成测试
```

全部通过才算成功：
- test_core.py 52/52
- test_commands.py 全部通过
- test_parser.py 28/28
- test_ops.py 78/78
- test_lsp.py 6/6
- test_package.py 6/6
- test_iot.py 全部通过
- test_sugar_san.py 全部通过
- run_all.py 全部通过

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

仅 `parser.py` 和 `sugar.py` 的解析阶段可用 Python 原生 `SyntaxError`。

### 作用域

- 变量查找：`evaluator.has_var(name)` / `evaluator.get_var(name)` （跨作用域）
- 变量设置：`evaluator.set_var(name, value)` 或 `evaluator.vars[name] = value`（当前作用域）
- 遍历所有变量：`evaluator.all_scoped_vars()`（调试/补全用）
- 函数调用：`evaluator.push_scope()` / `evaluator.pop_scope()`

### 预处理

`#include` 展开统一使用 `preprocess.py` 中的 `preprocess_includes(code)` 函数。