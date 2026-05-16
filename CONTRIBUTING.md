# Contributing to 三言 (Sanyan)

## 环境搭建

```bash
git clone <repo>
cd sanyan
pip install -e ".[dev]"
```

要求 Python >= 3.8。

## 运行测试

```bash
# 运行时核心单测（52 项）
python tests/test_core.py -v

# 命令模块单测
python tests/test_commands.py -v

# 糖语法解析器 AST 校验（28 项）
python tests/test_parser.py

# ops 模块单测（78 项）
python tests/test_ops.py -v

# LSP 测试（6 项）
python tests/test_lsp.py -v

# 包管理器测试（6 项）
python tests/test_package.py -v

# IoT 测试（25 项）
python tests/test_iot.py -v

# sugar.san 测试（37 项）
python tests/test_sugar_san.py -v

# 三言集成测试（动态发现）
python tests/run_all.py
```

所有测试通过才算成功。

## 代码风格

- 遵循 `pyproject.toml` 中配置的 Ruff 规则
- 行宽上限 120 字符
- 单引号字符串

```bash
ruff check .     # 静态检查
ruff format .    # 自动格式化
```

## 异常体系

运行阶段必须使用 `values.py` 中定义的异常：

| 异常类 | 用途 |
|---|---|
| `SanyanSyntaxError` | 参数格式/个数错误 |
| `SanyanTypeError` | 类型错误 |
| `SanyanValueError` | 值错误（除零、无效输入等） |
| `SanyanRuntimeError` | 运行时错误（递归过深等） |
| `SanyanNameError` | 未定义符号 |
| `SanyanKeyError` | 字典键访问错误 |
| `SanyanAttributeError` | 属性/方法不存在错误 |

仅 `parser.py` 和 `sugar/` 包（解析阶段）可用 Python 原生 `SyntaxError`。

## 作用域

```python
evaluator.has_var(name)       # 跨作用域查找
evaluator.get_var(name)       # 取值
evaluator.set_var(name, val)  # 当前作用域设置
evaluator.push_scope()        # 进入新作用域
evaluator.pop_scope()         # 退出当前作用域
evaluator.all_scoped_vars()   # 调试/补全用
```

## 架构

```
源码 (.san) → [preprocess.py] → [sugar.py | lexer.py → parser.py] → [evaluator.py] → [ops/*.py] → [ternary_core.py]
```

## 文档维护

修改代码后需同步更新：
- `CHANGELOG.md`（按日期倒序，分 新增/变更/修复/文档）
- `README.md`（项目文件树）
- `docs/manual.md`（内置命令表、错误信息表、新语法）