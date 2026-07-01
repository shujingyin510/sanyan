# 三言 LLVM 代码生成器 v3.50.0

> 将三言 AST 编译为 LLVM IR，链接 C 运行时生成可执行文件

---

## 目录

1. [概述](#1-概述)
2. [编译管线](#2-编译管线)
3. [运行时库 (runtime.c)](#3-运行时库-runtimec)
4. [代码生成器 (codegen.py)](#4-代码生成器-codegenpy)
5. [支持的 AST 节点](#5-支持的-ast-节点)
6. [Tagged Value 机制](#6-tagged-value-机制)
7. [编译与链接](#7-编译与链接)
8. [dp.c 测试套件](#8-dpc-测试套件)
9. [已知限制](#9-已知限制)

---

## 1. 概述

LLVM 代码生成器将三言 AST 编译为平台原生机器码。编译流程：

```
.san 源码 → 糖解析器/AST → LLVM IR → .o → 链接 runtime.c → 可执行文件
```

### 文件结构

```text
llvmgen/
├── __init__.py                 # 模块入口
├── build.py                    # 完整编译管线（.san → 可执行文件）
├── codegen.py                  # AST → LLVM IR 代码生成器（~420 行）
├── compiler.py                 # 编译入口（解析 + 代码生成，~280 行）
├── ops_gen.py                  # 算术/比较/三态操作（~410 行）
├── ops_gen_control.py          # 控制流（~360 行）
├── ops_gen_helpers.py          # 辅助函数（~240 行）
├── ir_builder.py               # IR 构建器抽象（~280 行）
├── ir_fixes.py                 # IR 后处理（~220 行）
├── helpers.py                  # 反射/类型工具（~450 行）
├── type_mapping.py             # 类型映射表（~90 行）
└── runtime.c                   # C 运行时库（~1790 行）
```

### 关键设计

- **统一变量类型 (i8\*)**: 所有变量存储为 `i8*` 指针
- **Tagged Integer**: 整数用 bit0=1 标记，指针 bit0=0（自然对齐）
- **函数调用约定**: 全部参数和返回值均为 `i8*`
- **自举引导**: `parse_sanyan()` 入口函数调用编译后的 `解析(source)` → 返回 AST

---

## 2. 编译管线

### compiler.py — `_parse_source()`

解析 `.san` 源码为 AST，按序尝试：

| 优先级 | 解析器 | 说明 |
|--------|--------|------|
| 1 | `_parse_with_sugar_san` | sugar.san 自举解析器（Python 求值器） |
| 2 | `_parse_c_s_expr` | C 共享库 S 表达式解析器 (`sanyan_parse.dll`) |
| 3 | `lexer.py` → `parser.py` | Python S 表达式解析器 |
| 4 | `SugarConverter.convert` | Python 糖语法转换器 |

### build.py — 完整编译

```bash
python -m llvmgen.build input.san [-o output] [--run]
```

三步流程：
1. `runtime.c` → `runtime.o`（C 编译器）
2. `.san` → LLVM IR → `.o`（python 代码生成 + clang/llc）
3. 链接 → 可执行文件

---

## 3. 运行时库 (runtime.c)

### 字符串系统

```c
typedef struct {
    int32_t len;     // 字符串字节长度
    char data[];     // 柔性数组，null-terminated
} rt_str_t;
```

**两种字符串表示**：
- **全局常量**：LLVM `_make_global_string()` 产生的裸 `const char*`（字节从偏移 0 开始）
- **运行时创建**：`_rt_make()` 产生的 `rt_str_t*`（`len` 字段在偏移 0，`data` 在偏移 4）

**统一访问辅助函数**：

```c
// 自适应提取 C 字符串（兼容两种格式）
static const char *_cstr(const void *p);

// 自适应获取长度
static int32_t _cstr_len(const void *p);
```

`_cstr()` 通过启发式检测：若 `len` 在 1~100000 范围内且 `data[len]=='\0'`，判定为 `rt_str_t`，返回 `data` 字段；否则当作裸 C 字符串。

### 列表系统

```c
typedef struct {
    int32_t len;
    int32_t cap;
    void **items;
} rt_list_t;

rt_list_t *rt_list_new(void);           // 创建空列表（cap=4）
void rt_list_push_item(void *lst, void *item);  // 追加元素
int32_t rt_list_len(rt_list_t *lst);    // 获取长度
void *rt_list_get(rt_list_t *lst, int32_t idx);  // 按索引取元素
rt_list_t *rt_list_concat(rt_list_t *a, rt_list_t *b);  // 拼接两个列表
rt_list_t *rt_list_slice(void *lst, int32_t start, int32_t end);  // 切片
```

### 字典系统

```c
#define RT_DICT_MAX 64
typedef struct { char *key; void *value; } rt_entry_t;
typedef struct { int32_t count; rt_entry_t entries[RT_DICT_MAX]; } rt_dict_t;

void *rt_dict_new(void);
int32_t rt_dict_contains(void *d, void *key);
void *rt_dict_get(void *d, void *key);
void rt_dict_set(void *d, void *key, void *value);
```

字典 key 通过 `_strdup_key()` 统一复制（兼容 `rt_str_t*` 和裸 `const char*`）。

### 运行时函数清单

| 函数 | 签名 | 说明 |
|------|------|------|
| `rt_list_new` | `() → i8*` | 创建空列表 |
| `rt_list_push_item` | `(i8*, i8*) → void` | 追加元素 |
| `rt_list_len` | `(i8*) → i32` | 列表长度 |
| `rt_list_get` | `(i8*, i32) → i8*` | 按索引取元素 |
| `rt_list_concat` | `(i8*, i8*) → i8*` | 拼接列表 |
| `rt_list_slice` | `(i8*, i32, i32) → i8*` | 列表切片 |
| `rt_str_concat` | `(void*, void*) → i8*` | 字符串拼接 |
| `rt_str_len` | `(void*) → i32` | 字符串长度 |
| `rt_str_substr` | `(void*, i32, i32) → i8*` | 子串提取 |
| `rt_str_equals` | `(void*, void*) → i32` | 字符串相等比较 |
| `rt_str_contains` | `(void*, void*) → i32` | 字符串包含检查 |
| `rt_str_find` | `(void*, void*) → i32` | 子串查找 |
| `rt_str_to_list` | `(const char*) → i8*` | 字符串转字符列表 |
| `rt_int_to_str` | `(uintptr_t) → i8*` | 整数转字符串 |
| `rt_dict_new` | `() → i8*` | 创建空字典 |
| `rt_dict_contains` | `(i8*, i8*) → i32` | 字典键检查 |
| `rt_dict_get` | `(i8*, i8*) → i8*` | 字典取值 |
| `rt_dict_set` | `(i8*, i8*, i8*) → void` | 字典设值 |
| `rt_random_int` | `(i32, i32) → i32` | 随机整数 |
| `rt_random_trit` | `() → i32` | 随机三态 |

---

## 4. 代码生成器 (codegen.py)

### 核心类型

```python
_INT = ir.IntType(32)      # i32
_PTR = ir.PointerType(ir.IntType(8))  # i8*
_ZERO = ir.Constant(_INT, 0)
_NULL = ir.Constant(_PTR, None)
```

### Tagged Value 装箱/拆箱

```python
def _box_int(self, int_val: ir.Value) -> ir.Value:
    # val ← (int_val << 1) | 1, bit0=1 标记为整数
    shifted = self.builder.shl(int_val, _ONE)
    tagged = self.builder.or_(shifted, _ONE)
    return self.builder.inttoptr(tagged, _PTR)

def _unbox_int(self, ptr_val: ir.Value) -> ir.Value:
    # val ← (ptrtoint(ptr_val) >> 1), 去除 tag 位
    raw = self.builder.ptrtoint(ptr_val, _INT)
    return self.builder.lshr(raw, _ONE)
```

### 作用域与变量

```python
class CodegenContext:
    _scope: dict[str, ir.Value]   # 当前函数栈帧 (alloca slots)
    _globals: dict[str, ir.GlobalVariable]  # 模块级全局变量
    _funcs: dict[str, ir.Function]  # 已编译函数

    def get_var(self, name):  # 加载变量值 (load from alloca)
    def set_var(self, name, value):  # 存储变量值 (store to alloca)
```

### 编译 Pass 顺序

`compile_top_level()` 三遍编译：

1. **Pass 0** — 预创建全局变量（top-level `设` 语句）
2. **Pass 1** — 预声明所有函数名（解决前向引用）
3. **Pass 2** — 编译函数体
4. **Harness** — 生成 `parse_sanyan()` 入口（初始化全局变量 + 调用 `解析`）

---

## 5. 支持的 AST 节点

### 字面量
- `int` / `float` → tagged `i8*`
- `"string"` → `_make_global_string()` → 全局常量 GEP
- 变量名 → `get_var()` → load from alloca
- 内置常量 (`真`/`假`/`可能`/`开`/`关`/`守`/etc.) → tagged int

### 算术 (i8* → unbox → LLVM op → rebox)
`加`/`减`/`乘`/`除`/`余`/`幂`/`取位` — 编译为 LLVM `add`/`sub`/`mul`/`sdiv`/`srem`

### 比较 (i8* → unbox → icmp → zext → rebox)
`等于`/`不等于`/`大于`/`小于`/`大于等于`/`小于等于`/`不大于`/`不小于`

### 逻辑
`且`/`或`/`非` — 编译为 `icmp + and/or` 或 `icmp + not`

### 控制流
- `若` — `_compile_if()`: cond → icmp → cbranch then/else blocks
- `循环` — loop header → cond check → body → branch back
- `遍历` — range for 或 container for
- `判` — switch on trit value (真/可能/假)
- `跳出`/`继续` — branch to loop_exit/loop_header

### 变量与函数
- `设` — `compile_node(value)` + `set_var(name)`
- `定义`/`fn` — `compile_fn_body(name, params, body)`
- `返回` — `builder.ret(value)`
- 函数调用 — `builder.call(cg._funcs[name], compiled_args)`
- 隐式返回 — 函数最后表达式若非 `返回`，自动 `ret result`

### 运行时函数调用
`列表`/`list` → `_compile_list_create()` → `rt_list_new` + `rt_list_push_item`
`字典`/`dict` → `_compile_dict_create()` → `rt_dict_new` + `rt_dict_set`
`列表合`/`list_concat` → `_dispatch_runtime()` → `rt_list_concat`
`连接`/`concat` (变参) → `_compile_fold()` → 两两折叠调用
`输出`/`print` → tagged int/str 分支 → `printf`

### 特殊形式
- `做`/`do` → 顺序编译所有语句，返回最后一个值
- `尝试`/`try` → `_compile_try_catch()`
- `导入`/`import` → `_resolve_imports()` 编译时内联
- `导出`/`export` → 忽略（编译时无意义）

---

## 6. Tagged Value 机制

```
内存布局 (i8*):

  整数:  PPP...PPP1    (bit0 = 1, 值 = ptr >> 1)
  指针:  PPP...PPP0    (bit0 = 0, 自然对齐保证)
  NULL:  0x00000000

示例:
  42   →  (42 << 1) | 1 = 85 = 0x55
  0    →  (0 << 1) | 1 = 1  = 0x01
  假(0) →  tagged 为 0x01（非空指针）
```

--- 

## 7. 编译与链接

### 前置条件
- Python 3.12+
- `llvmlite` Python 包
- C 编译器 (gcc/clang) 或 llc (LLVM 工具链)

### 编译命令

```bash
# 编译 .san → 可执行文件
python -m llvmgen.build stdlib/_bootstrap.san -o parser.exe

# 只生成 LLVM IR（不链接）
python -m llvmgen.compiler stdlib/_bootstrap.san -o bootstrap.ll

# 测试：运行 dp.c 配套
gcc -c llvmgen/runtime.c -o runtime.o -std=c99 -O2
python -m llvmgen.build stdlib/_bootstrap.san        # 生成 sanyan_parse.o
gcc dp.c runtime.o sanyan_parse.o -o dp.exe
./dp.exe
```

### Python 测试

```bash
python tests/test_llvmgen.py -v    # 53 项 LLVM IR 正确性测试
```

---

## 8. dp.c 测试套件

`dp.c` 是一个 7 项 S 表达式解析测试：

```c
test("42");                          // 数字
test("\"hello\"");                   // 字符串
test("x");                           // 标识符
test("(add 1 2)");                   // S 表达式函数调用
test("(if 1 2 3)");                  // S 表达式条件
test("(set x 42)");                  // S 表达式赋值
test("(fn (f x) (return x))");       // S 表达式函数定义
```

测试通过标准：`parse_sanyan(code)` 返回非 NULL 指针（即 `解析` 成功返回 AST）。

---

## 9. 已知限制

- **无 JIT 执行**：当前只生成 LLVM IR，通过外部 C 编译器链接执行
- **无异常处理 (LLVM)**：`尝试`/`捕获` 在 LLVM 路径未实现
- **IoT 设备桩**：LLVM 路径 IoT 操作为桩实现
- **递归深度**：LLVM 编译的函数无 tail-call 优化
- **C 编译器依赖**：需要 gcc/clang 或 llc 完成最终编译
- **`rt_str_split` 未实现**：声明但无实现体
- **`_bootstrap.san` 编译**：需通过 Python S 表达式解析器回退（`lexer.py` → `parser.py`）
