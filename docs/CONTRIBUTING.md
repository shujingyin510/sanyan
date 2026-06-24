# 贡献指南

## 开发环境

```bash
# 安装开发依赖
pip install -e .[dev]

# 运行全部测试
python -X utf8 preflight.py --quick     # 一键全量检查
# 或单独运行：
python tests/test_core.py          # 138 项
python tests/test_commands.py      # 18 项
python tests/test_parser.py        # 28 项
python tests/test_ops.py           # 92 项
python tests/test_ops_ext.py       # 64 项
python tests/test_vm.py            # 91 项
python tests/test_self_host.py     # 8 项（含 Level 2+3）
python tests/test_sugar_self_host.py # 3 项
python tests/test_sugar_san.py     # 45 项
python tests/test_agent.py         # 31 项
python tests/test_diff_fuzz.py     # 12 项
python tests/test_effect_types.py  # 30 项
python tests/test_disasm.py        # 6 项

# 集成测试
python tests/run_all.py

# Lint 检查
ruff check .
ruff format --check .
mypy .
```

## 代码规范

### Python
- 遵循 PEP 8（ruff 自动检查）
- 类型注解：所有公共 API 需要类型注解（mypy 检查）
- 异常：运行时只使用 `values.py` 中的 `Sanyan*` 异常类
- 全角符号：**禁止**将全角符号转为半角（母语编程核心特性）

### Sanyan (.san)
- 关键字使用中文：`设`/`若`/`循环`/`定义`/`返回`
- 运算符使用中文：`加`/`减`/`乘`/`除`/`等于`/`大于`
- 字符串使用全角引号或半角引号均可

### Git
- 提交信息使用中文
- 每次推送前检查 `.md` 文件差异
- CI 必须全部通过才能合并

## 项目结构

```
sanyan/
├── evaluator.py          # 求值器（核心）
├── values.py             # 值系统（TritValue 等）
├── runtime.py            # 运行环境 + BUILTIN_OPS
├── lexer.py              # S 表达式词法分析
├── parser.py             # S 表达式语法解析
├── commands.py           # 用户定义命令
├── param_matcher.py      # 参数匹配
├── tail_call.py          # 尾调用优化
├── eval_utils.py          # 求值工具函数（类型转换/边界检查）
├── ternary_core.py       # 平衡三值逻辑核心
├── ops/                  # 操作模块
│   ├── registry.py       # 操作注册表
│   ├── dispatcher.py     # 操作分派
│   ├── arithmetic_ops.py # 算术运算
│   ├── comparison_ops.py # 比较运算
│   ├── control_ops.py    # 控制流
│   ├── list_ops.py       # 列表/数组操作
│   ├── dict_ops.py       # 字典操作
│   ├── iter_ops.py       # Lambda/map/filter/reduce
│   ├── string_ops.py     # 字符串操作
│   └── ...               # 其他操作模块
├── sugar/                # 糖语法
│   ├── lexer.py          # 糖语法词法分析
│   └── parser.py         # 糖语法解析
├── stdlib/               # 标准库 (.san)
├── llvmgen/              # LLVM 后端
├── lsp/                  # LSP 服务器
├── csrc/                 # C VM
├── language/             # 语言映射 (JSON)
├── tests/                # 测试
└── docs/                 # 文档
```

## 添加新操作

1. 在 `ops/` 目录创建或编辑模块
2. 实现操作函数：`def op_xxx(evaluator, args) -> Any`
3. 注册：`register('操作名', op_xxx)`
4. 添加中文别名：`register_alias('中文名', '操作名')`
5. 在 `language/chinese.json` 添加映射
6. 编写测试

## 报告问题

- 使用 GitHub Issues
- 包含：复现步骤、期望行为、实际行为、错误信息
- 附上 `.san` 测试文件（如适用）
