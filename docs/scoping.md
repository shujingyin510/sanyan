# 作用域与求值器

> 三言的运行时核心：作用域栈管理、断点调试、性能剖析、操作分派。

## SanyanRuntime

**文件**：`core/runtime.py` (363行)

组合模式管理四个子系统：

```
SanyanRuntime
├── ScopeManager    — 作用域栈
├── IoTManager      — 传感器/执行器设备管理
├── DebugManager    — 交互式断点调试
└── ProfileManager  — 性能剖析器
```

## 作用域栈

**核心改进** (v3.6)：替代旧版全量拷贝方案。

```python
push_scope()      # 进入新作用域（函数调用）
pop_scope()       # 退出作用域（函数返回）
get_var(name)     # 从栈顶向下递归搜索
all_scoped_vars() # 合并所有作用域（调试用）
```

零拷贝 push/pop，支持嵌套函数和闭包捕获。

## SanyanEvaluator

**文件**：`core/evaluator.py` (649行)

主求值器，继承自 `SanyanRuntime`。

### eval() 分派

```
eval(node)
  ├── int/float  → TritValue (小整数缓存 -100~100)
  ├── str        → _eval_str()
  │   ├── 引号字符串 → 字面量
  │   ├── 纯数字     → TritValue
  │   └── 标识符     → 皮肤解析 → 操作查找
  ├── list       → _eval_list() → _apply(op, args)
  └── TritValue/FunctionValue → 原样返回
```

### 操作分派链

```
apply(evaluator, op, args)
  ├── resolve_op_name     # 皮肤映射 (中文→内部名)
  ├── dispatch_op         # 注册表查找
  ├── handle_dot_access   # module.func / dict.key
  ├── handle_variable_call # FunctionValue 调用
  └── Commands.call       # 用户自定义命令
```

两条路径：
- **快速路径**：无调试/无性能/无类型检查，直接 dispatcher.apply()
- **慢速路径**：静态类型检查 → 不确定性检查 → 断点 → 性能

## 调试与性能

### 断点调试 (v3.10)

```sanyan
:step          # 单步执行
:break LINE    # 设置断点
:watch VAR     # 监视变量
:continue      # 继续执行
```

### 性能剖析

```sanyan
:profile           # 开启剖析
:profile report    # 查看报告
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `core/evaluator.py` | 求值器 |
| `core/runtime.py` | 运行时 |
| `core/commands.py` | 自定义命令 |
| `core/param_matcher.py` | 参数匹配 |
| `core/tail_call.py` | 尾递归 |
| `ops/dispatcher.py` | 操作分派 |
| `ops/registry.py` | 操作注册表 |
