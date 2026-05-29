# 三言架构文档

## 系统概览

三言（Sanyan）是基于**平衡三值逻辑**的中文编程语言。核心设计：

```
源代码 (.san) → 词法分析 → 语法解析 → AST → 求值/编译
                                            ↓
                                    ┌───────┼───────┐
                                    ↓       ↓       ↓
                               Python   LLVM IR   字节码
                               求值器   原生编译   VM执行
```

## 核心模块

### 求值器 (`evaluator.py`)
- `SanyanEvaluator` 继承 `SanyanRuntime`，是运行时的核心
- `eval(node)` → 根据节点类型分派：字符串→符号解析，列表→函数调用
- `_apply(op, args)` → 操作分派链：内置操作 → 点号访问 → 变量调用 → 用户命令
- 作用域：`scope_stack` 栈式管理，`push_scope()`/`pop_scope()` 控制生命周期

### 值系统 (`values.py`)
- `TritValue` — 平衡三值：`1`(真), `-1`(假), `0`(可能)
- `FunctionValue` — 用户定义函数，捕获闭包环境
- `ModuleValue` — 模块对象，支持 `.属性` 访问和函数调用
- `ArrayValue` — 定长数组（VM 专用）

### 操作分派 (`ops/dispatcher.py`)
- `apply(evaluator, op, args)` — 统一入口
- 分派链：`dispatch_op` → `handle_dot_access` → `handle_variable_call` → `Commands.call`
- 每个 `ops/*.py` 模块通过 `register()` 注册操作到 `_OP_DISPATCH` 表

### 词法分析 (`lexer.py` + `sugar/lexer.py`)
- `lexer.py` — S 表达式词法分析器，识别 token 类型
- `sugar/lexer.py` — 糖语法词法分析器，全角映射、关键字识别

### 语法解析 (`parser.py` + `sugar/parser.py`)
- `parser.py` — S 表达式解析器
- `sugar/parser.py` — 中文糖语法解析器，支持 `设`/`若`/`循环`/`定义` 等

### 字节码编译器 (`compile_bytecode.py` + `stdlib/bytecode_compiler.san`)
- Python 端：`compile_source()` 生成 `.bin` 文件
- Sanyan 端：`stdlib/bytecode_compiler.san` 自举编译器
- 52 个操作码，32 位代码大小，支持函数/闭包/模块

### C VM (`csrc/runtime.c`)
- 1461 行 C 语言字节码解释器
- 标记指针值系统（LSB=1 整数，LSB=0 堆对象）
- 支持全部 52 个操作码

### LLVM 后端 (`llvmgen/`)
- `compiler.py` — 将 Sanyan AST 编译为 LLVM IR
- `codegen.py` — LLVM IR 代码生成（1822 行，最大文件）
- `build.py` — LLVM → 目标文件编译

### LSP 服务器 (`lsp/`)
- `server.py` — LSP 协议实现
- `analysis.py` — 代码分析（补全、悬停、定义跳转）

### 词法映射 (`language/`)
- `chinese.json` — 中文关键字 → 英文内部名映射
- `english.json` — 英文关键字映射
- `operators.json` — 运算符映射

## 数据流

### 求值流程
```
源代码 → tokenize → parse → AST (嵌套列表)
  ↓
eval(AST) →
  数字字面量 → TritValue
  字符串字面量 → str
  符号 → 变量查找 → 值
  列表 → _apply(操作名, 参数列表)
    → dispatch_op → 内置操作 / 用户命令 / 点号访问
```

### 编译流程
```
源代码 → SugarConverter.convert() → 标准 AST
  ↓
compile_source() → 字节码 + 导出表
  ↓
.bin 文件: SAN0(4) + ver(1) + var_count(1) + code_size(4) + bytecode + exports
```

## 设计决策

### 为什么用平衡三值逻辑？
- 三态（真/假/可能）比二值逻辑更适合 IoT/传感器场景
- `可能` 状态可用于不确定性建模
- 与量子计算概念自然对接

### 为什么用中文关键字？
- 降低中文使用者的认知负担
- 全角符号支持让中文开发者有「母语编程」体验
- 通过语言映射文件（`language/*.json`）实现中英文双语

### 为什么用 S 表达式 + 糖语法双语法？
- S 表达式：适合元编程、代码生成
- 糖语法：适合日常编程，可读性更好
- 两者共享同一求值器，无语义差异

### 为什么自举编译器用 Sanyan 编写？
- 验证语言表达能力
- 字节码编译器本身可被 VM 执行（`.bin` 文件）
- 实现「用三言编译三言」的自举目标
