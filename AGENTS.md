# AGENTS.md — 三言项目维护约定

## 测试

每次代码修改后必须运行：

```bash
# Python 单测
python tests/test_core.py -v
# 糖语法解析器回归测试
python tests/test_parser.py
# 三言集成测试
python tests/run_all.py
```

test_core.py 33/33 + test_parser.py 23/23 + run_all.py 33/33 全部通过才算成功。

## 文档自动维护

以下文档必须在每次代码改动后同步更新：

### CHANGELOG.md

- 新增版本条目时按日期倒序排列
- 每个条目分 **新增** / **变更** / **修复** / **文档** 四个类别
- 引用具体的文件路径和关键改动说明

### README.md

- **项目结构** 中的文件树需与实际文件列表一致
- 新增模块时在结构树中补入

### docs/manual.md

- **内置命令速查表**（第 17 节）需与 `runtime.py:BUILTIN_OPS` 一致（注：纯运算符如 `且`/、`加`/、`大于` 等已在手册 2.3-2.5 节独立说明，不需在第 17 节重复列出）
- **错误信息说明**（第 18 节）需与 `values.py` 中 `Sanyan*` 异常类一致
- 新增语法特性时补入对应章节
- 顶部版本号和底部文档版本号需同步更新

## 代码约定

### 全角符号

**绝对不能** 为了通过测试而将全角符号转换为半角符号。全角符号（`（` `）` `，` `；` `＂` `＂` 等）是母语编程的核心特性，必须在一层保留并正确识别。

### 异常体系

运行阶段所有 `raise` 必须使用 `values.py` 中的 `Sanyan*` 系列异常：
- `SanyanSyntaxError` — 参数格式/个数错误
- `SanyanTypeError` — 类型错误
- `SanyanValueError` — 值错误（除零、无效输入等）
- `SanyanRuntimeError` — 运行时错误（递归过深等）
- `SanyanNameError` — 未定义符号
- `SanyanKeyError` — 字典键访问错误
- `SanyanAttributeError` — 属性/方法不存在错误

仅 `parser.py` 和 `sugar.py` 的解析阶段可用 Python 原生 `SyntaxError`。

### 作用域

- 变量查找：`evaluator.has_var(name)` / `evaluator.get_var(name)` （跨作用域）
- 变量设置：`evaluator.set_var(name, value)` 或 `evaluator.vars[name] = value`（当前作用域）
- 遍历所有变量：`evaluator.all_scoped_vars()`（调试/补全用）
- 函数调用：`evaluator.push_scope()` / `evaluator.pop_scope()`（替代 `saved_vars = dict(...)` 全量拷贝）

### 预处理

`#include` 展开统一使用 `preprocess.py` 中的 `preprocess_includes(code)` 函数。