# 三言 v3.45 规划：聚焦语言与编译器

> 目标：将精力集中在三进制语言核心和编译器上，提升性能、完善类型系统、增强编译能力。

---

## 一、现状分析

### 核心优势（已验证）
- ✅ 自举链完整：Level 0-4 全部通过
- ✅ C VM 可用：52 指令、61 项测试、STM32 验证
- ✅ LLVM 后端：AOT 编译、浮点支持、import 静态链接
- ✅ 双语法：糖语法 + S 表达式共享求值器
- ✅ 三态逻辑：Kleene 强逻辑 + 置信度传播

### 待改进
- ⚠️ Python 求值器性能（fib(25) ≈ 9s）
- ⚠️ 类型系统基础（渐进类型，无泛型）
- ⚠️ LLVM 后端功能不完整（无 GC、异常处理简陋）
- ⚠️ 错误信息质量（缺少源码上下文）

---

## 二、v3.45 目标

### P0：性能优化（1周）

| 任务 | 文件 | 目标 |
|------|------|------|
| VM 分派优化 | `vm.py` | list[opcode] O(1) 索引 |
| 求值器热路径 | `evaluator.py` | 缓存函数引用 |
| 常量折叠 | `compile_bytecode.py` | 编译期计算常量表达式 |
| 尾调用优化 | `tail_call.py` | 完善尾递归消除 |

### P1：类型系统增强（2周）

| 任务 | 文件 | 目标 |
|------|------|------|
| 类型推断 | `type_inference.py` | 从赋值自动推断变量类型 |
| 泛型容器 | `type_checker.py` | 列表<T>、字典<K,V> |
| 接口/协议 | `protocols.py` | 可序列化、可迭代等 |
| 类型标注增强 | `evaluator.py` | 函数参数/返回值类型检查 |

### P2：编译器增强（2周）

| 任务 | 文件 | 目标 |
|------|------|------|
| LLVM GC 支持 | `llvmgen/` | 引用计数或轻量 GC |
| LLVM 异常处理 | `llvmgen/` | try/catch 编译为 LLVM IR |
| 字节码优化 | `compile_bytecode.py` | 死代码消除、常量折叠 |
| 编译错误信息 | `compile_bytecode.py` | 源码位置映射 |

### P3：标准库完善（1周）

| 任务 | 文件 | 目标 |
|------|------|------|
| 数学库增强 | `stdlib/math.san` | 矩阵运算、向量操作 |
| 字符串增强 | `stdlib/string.san` | 正则表达式、模板 |
| 文件系统 | `stdlib/file.san` | 目录操作、路径处理 |
| 测试框架 | `stdlib/test.san` | 断言、测试套件 |

---

## 三、技术细节

### 3.1 VM 分派优化

当前：`dict.get(op)` 查找
目标：`list[opcode]` O(1) 索引

```python
# 当前
dispatch = _DISPATCH
handler = dispatch.get(op)

# 优化后
dispatch_list = [None] * 0x49
for op, fn in _DISPATCH.items():
    dispatch_list[op] = fn
handler = dispatch_list[op]
```

### 3.2 类型推断

```python
class TypeEnv:
    def infer(self, name: str, value: Any) -> str:
        """从值推断类型并记录"""
        type_name = self._infer_value(value)
        self._scopes[-1][name] = type_name
        return type_name

    def _infer_value(self, value: Any) -> str:
        if isinstance(value, TritValue):
            return 'trit'
        if isinstance(value, int):
            return 'int'
        if isinstance(value, float):
            return 'float'
        if isinstance(value, str):
            return 'str'
        if isinstance(value, list):
            return 'list'
        if isinstance(value, dict):
            return 'dict'
        return 'any'
```

### 3.3 泛型容器

```python
# 类型签名
_TYPE_SIGS = {
    'list_get': (['列表<T>', 'int'], 'T'),
    'dict_get': (['字典<K,V>', 'K'], 'V'),
}

# 类型匹配
def _matches(actual: str, expected: str) -> bool:
    if expected.startswith('列表<') and expected.endswith('>'):
        inner = expected[3:-1]
        return actual == 'list' or actual == f'列表<{inner}>'
    ...
```

### 3.4 LLVM GC

```c
// arena 分配器（已有）
typedef struct {
    char *base;
    size_t size;
    size_t used;
} Arena;

// 引用计数（新增）
typedef struct {
    int ref_count;
    void (*destructor)(void*);
} RefCounted;
```

---

## 四、里程碑

| 周次 | 目标 | 验证方式 |
|------|------|----------|
| Week 1 | VM 优化 + 求值器缓存 | fib(25) < 6s |
| Week 2 | 类型推断 + 泛型 | 类型检查测试通过 |
| Week 3 | 接口/协议 | 协议检查测试通过 |
| Week 4 | LLVM GC + 异常 | LLVM 编译测试通过 |
| Week 5 | 字节码优化 | 编译后 .bin 更小 |
| Week 6 | 标准库完善 | 新增 100 项测试 |

---

## 五、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLVM GC 复杂度高 | 延期 1-2 周 | 先实现引用计数，再考虑更复杂的 GC |
| 类型推断可能破坏现有代码 | 测试失败 | 渐进式启用，先在新代码中使用 |
| 性能优化可能引入 bug | 回归 | 每次优化后运行完整测试套件 |

---

## 六、与 v3.44 的关系

v3.44 已完成：
- ✅ VM 分派优化（list[opcode]）
- ✅ 求值器热路径缓存
- ✅ 错误信息增强
- ✅ 类型推断基础
- ✅ 泛型容器支持
- ✅ 接口/协议支持

v3.45 将继续：
- 🔄 LLVM GC 支持
- 🔄 LLVM 异常处理
- 🔄 字节码优化
- 🔄 标准库完善

---

*文档版本：2026-06-26*
*维护者：三言团队*
