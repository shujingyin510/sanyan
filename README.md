# 三言 Sanyan v3.14.0

[![VS Code Marketplace](https://img.shields.io/badge/VS%20Code-Marketplace-%23007ACC?logo=visualstudiocode)](https://marketplace.visualstudio.com/items?itemName=sanyan-lang.sanyan-language)
[![CI](https://github.com/shujingyin510/sanyan/actions/workflows/ci.yml/badge.svg)](https://github.com/shujingyin510/sanyan/actions)

> **处理真实世界的三值编程语言。** 传感器会失灵，用户会犹豫，网络会波动——真实世界从来不是非黑即白的。

---

## 一句话定位

三言是一门内置三态逻辑的编程语言。真实世界充满不确定性，三言用"可能"来表达它，而不是强行归为对错。
关键字可切换为任何自然语言——不只是中文编程，而是母语编程。

---

## 起源

1958 年，莫斯科国立大学造了一台三进制计算机，叫 **Setun**。每个比特不是 0 或 1，而是**正、零、负**。它稳定运行了三十年，功耗只有同期二进制计算机的三分之一。然后被停产了——不是因为技术不行，而是苏联的工业标准全面转向了二进制。

2024 年，我在用 STM32 做智能家居时，发现所有传感器都在对我说三种状态：有人、没人、信号不稳。但我的代码只能写 `if` 和 `else`。"信号不稳"被强行归类为 0 或 1，然后我加了一堆阈值、状态机和注释来弥补丢失的信息。

**如果编程语言原生支持第三种状态呢？**
于是就有了三言。

---

## 快速开始

```bash
git clone https://github.com/shujingyin510/sanyan.git
cd sanyan
python main.py
```

> **性能提示**：使用 [PyPy](https://pypy.org) 运行可获得 5-10 倍加速：`pypy main.py`

进入 REPL 后尝试：

```text
三言> 设 a = 10
三言> 输出(a ^ 2)
  => 100  (三进制: ++-0+)

三言> 设 状态 = 可能
三言> 输出(状态)
  => 0  (三进制: 0)
```

运行示例文件：

```bash
python main.py examples/greenhouse.san
python main.py examples/sensor_pipeline_simple.san
```

## 杀手级示例：智能温室控制系统

以下代码模拟了一个温室环境，光线和人体传感器返回三态信号（充足/不足/不稳，有人/无人/不确定），温度传感器返回连续值。系统根据三态决策控制灯光、窗帘、风扇和加热器，并在传感器冲突时执行优先级处理。

### 糖语法版（examples/greenhouse.san，自包含，无需外部模块）

```c
// 智能温室控制系统 greenhouse.san（最终展示版）
// 演示三言核心特性：三态传感器、多传感器融合、文件日志、异常处理

定义 记录 (消息) {
    设 当前日志 = ""
    尝试 {
        当前日志 = 读文件("greenhouse.log")
    } 捕获 (错误) {
        当前日志 = ""
    }
    设 新日志 = 连接(当前日志, "\n", 消息)
    写文件("greenhouse.log", 新日志)
    输出(消息)
}

定义 转光线描述 (值) {
    若 (值 == 真) { 返回("充足") }
    再若 (值 == 假) { 返回("不足") }
    否则 { 返回("不稳") }
}

定义 转人体描述 (值) {
    若 (值 == 真) { 返回("有人") }
    再若 (值 == 假) { 返回("无人") }
    否则 { 返回("不确定") }
}

定义 转温度描述 (温度) {
    若 (温度 >= 29) { 返回("炎热") }
    再若 (温度 >= 28) { 返回("温暖") }
    再若 (温度 >= 15) { 返回("适宜") }
    再若 (温度 >= 10) { 返回("偏冷") }
    否则 { 返回("寒冷") }
}

定义 温室控制 () {
    记录("温室系统启动（随机传感器模拟，共检测10次）。")

    设 运行次数 = 0
    设 总次数 = 10

    循环 (运行次数 < 总次数) {
        设 光线值 = 随机态()
        设 温度值 = 随机数(10, 35)
        置 人体 = 随机态()

        设 光线描述 = 转光线描述(光线值)
        设 温度描述 = 转温度描述(温度值)
        设 人体值 = 读(人体)
        设 人体描述 = 转人体描述(人体值)

        记录("----------------------------------------")
        记录(连接("【检测 ", 运行次数 + 1, "/", 总次数, "】光线: ", 光线描述, "，温度: ", 温度值, "（", 温度描述, "），人体: ", 人体描述))

        // 光线控制窗帘和补光灯
        若 (光线值 == 真) {
            置 灯 = 灭
            置 窗帘 = 开
            记录("光照充足，补光灯关闭，窗帘拉开。")
        } 再若 (光线值 == 假) {
            置 灯 = 亮
            置 窗帘 = 关
            记录("光照不足，补光灯开启，窗帘关闭。")
        } 否则 {
            置 灯 = 守
            置 窗帘 = 守
            记录("光照不稳，设备保持原状。")
        }

        设 常温上限 = 28
        设 常温下限 = 15

        // 温度控制风扇和加热
        若 (温度值 > 常温上限) {
            置 风扇 = 开
            置 加热 = 关
            记录("环境高温，风扇启动，加热关闭。")
        } 再若 (温度值 < 常温下限) {
            置 风扇 = 关
            置 加热 = 开
            记录("环境低温，加热启动，风扇关闭。")
        } 否则 {
            置 风扇 = 守
            置 加热 = 守
            记录("温度适宜，设备待机。")
        }

        // 人体传感器独立控制灯（覆盖光线决策，体现优先级）
        若 (人体值 == 真) {
            置 灯 = 亮
            记录("人体检测：有人，灯光开启（覆盖光线决策）。")
        } 再若 (人体值 == 假) {
            置 灯 = 灭
            记录("人体检测：无人，灯光关闭（覆盖光线决策）。")
        } 否则 {
            // 不确定时，保持灯当前状态，不动作
            记录("人体检测：不确定，灯光维持现状。")
        }

        运行次数 = 运行次数 + 1
        等待(1)   // 1秒间隔，节奏紧凑
    }

    记录("========== 温室监控结束 ==========")
    记录(连接("共执行 ", 总次数, " 次检测。"))
    查 灯
    查 窗帘
    查 风扇
    查 加热
    0
}

温室控制()
```

等效 S 表达式版（examples/greenhouse_se.san）提供相同输出，保证 100% 稳定运行。

某次运行输出片段（所有传感器状态均为随机）：

```text
温室系统启动（随机传感器模拟，共检测10次）。
----------------------------------------
【检测 1/10】光线: 充足，温度: 22（适宜），人体: 不确定
光照充足，补光灯关闭，窗帘拉开。
温度适宜，设备待机。
人体检测：不确定，灯光维持现状。
----------------------------------------
【检测 2/10】光线: 不稳，温度: 30（炎热），人体: 有人
光照不稳，设备保持原状。
环境高温，风扇启动，加热关闭。
人体检测：有人，灯光开启（覆盖光线决策）。
----------------------------------------
...
========== 温室监控结束 ==========
共执行 10 次检测。
  灯 当前状态: 关 (三进制: -)
  窗帘 当前状态: 开 (三进制: +)
  风扇 当前状态: 守 (三进制: 0)
  加热 当前状态: 守 (三进制: 0)
```

这个示例直观展示了三言的核心价值：不确定状态 `守` 作为一等公民参与决策，无需用"阈值+默认值"的二进制技巧来模拟。

## 三言长什么样

### 糖语法（类 C，日常使用）

```c
// 智能家居：晚安模式
定义 晚安 () {
    置 灯 = 灭;
    置 窗帘 = 关;
    置 风扇 = 守;    // 风扇保持当前状态，不强制关闭
    输出("晚安");
}

// 遍历传感器，只在确定时动作
遍历 i 从 1 到 5 {
    若 (读(人体) == 真) {
        置 灯 = 亮;
    } 再若 (读(人体) == 可能) {
        置 灯 = 守;   // 不确定有没有人，保持待机
    } 否则 {
        置 灯 = 灭;
    }
}
```

### 原生 S 表达式（底层等价形式，适合元编程）

```lisp
（定义 晚安 （）
  （做
    （置 灯.灭）
    （置 窗帘.关）
    （置 风扇.守）
    （输出 "晚安"）））

（遍历 i 1 5
  （若 （读 人体）
      （置 灯.亮）
      （若 （可能） （置 灯.守） （置 灯.灭））））
```

两种语法共享同一个求值器，可以混用。

### 双语法对照学习

所有示例和测试均提供 **糖语法** 和 **S 表达式** 两种版本，文件名以 `_se` 后缀区分：

```text
examples/
├── greenhouse.san          # 糖语法版
├── greenhouse_se.san       # S 表达式版（对照学习）
├── voting.san              # 糖语法版
├── voting_se.san           # S 表达式版
...

tests/
├── test_math.san           # 糖语法版
├── test_math_se.san        # S 表达式版
...
```

对照速查：

| 糖语法 | S 表达式 |
|--------|----------|
| `输出("hello")` | `（输出 "hello"）` |
| `设 x = 10` | `（设 x 10）` |
| `{ expr1; expr2 }` | `（做 expr1 expr2）` |
| `定义 f (x) { 返回(x+1) }` | `（定义 f （x） （返回 （+ x 1）））` |
| `若 (x > 0) { … } 否则 { … }` | `（若 （大于 x 0） … …）` |

## 新增特性速览（v3.14.0）

| 特性 | 说明 |
|---|---|
| 🔄 **字节码 VM 完全自举** | VM 编译 `stdlib/bytecode_compiler.bin` 与求值器产出逐字节相同（5442 字节，5406 字节码） |
| 🛡️ **CALL/RET 栈隔离** | `stack_base` 记录 + `del stack[base:]` 清理，消除递归 CALL + JMP 循环的栈污染 |
| 🔧 **DICT_SET 副作用优化** | 不再推回修改后的 dict，消除 fn handler 作用域复制循环的栈泄漏 |
| 📝 **行注释支持** | `//`（半角）和 `／／`（全角）行注释，tokenizer 自动跳过 |
| 🆕 **DICT_KEYS 操作码** | 新增 0x32 操作码，`字列` 正确返回字典键列表 |
| 🐛 **字符串引号检测修复** | 用 `(ord (子串 n 0 1))` 替代转义不可靠的 `str_equals "\""` |
| 🐛 **发射i32 溢出修复** | 直接拆 4 字节，不用 `(mod v 2^32)` 防止有符号溢出 |
| 📝 **编译器注释化** | `bytecode_compiler.san` 73 行可读格式，`//` 注释覆盖全函数 |

## 新增特性速览（v3.13.0）

| 特性 | 说明 |
|---|---|
| 🧩 **求值器模块拆分** | `evaluator.py` 从 315 行降至 176 行，拆出 `eval_helpers.py`、`debug_eval.py` |
| 🧩 **命令模块重构** | `commands.py` 从 200 行降至 105 行，拆出 `tail_call.py`、`param_matcher.py` |
| 🧩 **统一错误处理** | `ops/_error_handler.py` — `handle_op_errors` 装饰器，参数验证工具函数 |
| 📝 **类型标注增强** | `evaluator.py`/`runtime.py`/`values.py` 核心模块补充完整 TypeHint |
| 📚 **标准库扩充** | 新增 `stdlib/algorithm.san`（排序/质数/算法）、`stdlib/collection.san`（栈/队列/集合）、`stdlib/validate.san`（邮箱/IP/身份证验证） |
| 📝 **实用示例** | 新增 `examples/student_grade.san`（成绩管理）、`examples/sales_analysis.san`（销售分析）、`examples/file_batch_process.san`（批量文件处理） |

## 新增特性速览（v3.12.0）

| 特性 | 说明 |
|---|---|
| 🧠 **LLVM 代码生成器** | AST → LLVM IR 编译（~1393 行 codegen），链接 C 运行时生成原生可执行文件 |
| 🔧 **运行时库完善** | `runtime.c` 新增统一字符串访问层 (`_cstr()`)，修复 `rt_str_t*` / `const char*` 格式不兼容 |
| 📡 **自举解析管线** | `_parse_source()` 新增 Python S 表达式解析器回退，支持 `_bootstrap.san` 完整编译 |
| 📝 **LLVM 功能文档** | `docs/llvm.md` — 编译管线、运行时库 API、Tagged Value 机制、dp.c 测试套件 |

## 新增特性速览（v3.11.0）

| 特性 | 说明 |
|---|---|
| 🔨 **交叉编译工具链** | `sanyancc.py` 将 `.san` 源码编译为平坦字节码，`runtime.c` / `runtime_stm32.c` 解释执行 |
| 🖥️ **STM32 固件** | `examples/stm32-blinky/` — 完整 VM + GPIO(LED) + SysTick + UART，已在 Blue Pill 硬件运行 |
| 🧮 **纯三进制算术** | 全部 7 种运算（加/减/乘/除/余/幂/取位）统一走 `TernaryALU`，无 Python `math` 后备 |
| 📦 **嵌套包导入** | `导入("a.b.c")` 自动查找 `stdlib/a/b/c.san` → `stdlib/a/b/c/package.san` |
| 🔧 **Runtime 组合模式重构** | `ScopeManager`/`IoTManager`/`DebugManager`/`ProfileManager` 提取到 `runtime_components.py` |

## 新增特性速览（v3.10.0）

| 特性 | 说明 |
|---|---|
| 🧩 **类型标注** | `定义 f(x: 数字, y: 字符串) { ... }` — 参数类型标注，运行时自动校验 |
| 🔍 **LSP 语言服务器增强** | 新增格式化、引用查找、重命名、文档符号、折叠范围、语义补全、hover 文档注释 |
| 🎨 **源码格式化器** | `sanfmt.py` — 类 black/prettier 的 `.san` 格式化器，保留注释 |
| 🐛 **表达式断点调试** | `:step` / `:break` / `:watch` / `:continue` — REPL 交互式调试 |
| ⏱ **性能剖析** | `--profile` 标志 + `:profile` — 追踪每个操作的调用次数和耗时 |
| 📝 **AST JSON 导出** | `--ast-json` — 将解析后的 AST 导出为 JSON |
| 📌 **源码位置追踪** | 错误消息携带行号列号：`第3行第5列: 未定义的符号: x` |
| 🎯 **DAP 调试适配器** | `dap_server.py` — VS Code 断点调试协议支持 |

## 新增特性速览（v3.8.0）

| 特性 | 说明 |
|---|---|
| 🧩 **语法解析器拆分为包** | `sugar.py` → `sugar/` 包（lexer + Pratt parser + error reporter） |
| 🚪 **模块导出** | `导出 name1 name2` 控制模块对外可见的符号 |
| 📟 **设备注册表** | `注册设备 名称 为 mock` / `注册设备 名称 为 file("path")` |
| 📦 **包管理器** | `安装("包名")` / `包列表()` / `加载包("包名")` |
| 🔢 **三进制定点数** | `BT.from_float()` 将浮点转为平衡三进制定点表示 |
| 🌐 **全角引号** | 支持 `「」`、`『』`、`""` 等六种字符串定界符 |
| 💬 **`#` 行注释** | 新增 `#` 注释语法，与 `//` 等价 |
| 🔗 **S 表达式中文别名** | `(读取 人体)`、`(写入 灯 亮)`、`(查询 灯)` |
| λ **希腊字母 Lambda** | `λ(x) { x * 2 }` 等价于 `函数(x) { x * 2 }` |

## 三进制不是模拟

三言的三进制不是"用二进制模拟三进制"。`ternary_core.py` 从位运算层开始就是三值的：

```text
平衡三进制加法：
   +-  (十进制 2)
+  +0  (十进制 3)
------
  +--  (十进制 5) ✓
```

三值逻辑（Kleene 强逻辑）：

| A | B | A 且 B | A 或 B |
|---|---|---|---|
| 真 | 可能 | 可能 | 真 |
| 假 | 可能 | 假 | 可能 |
| 可能 | 可能 | 可能 | 可能 |

`可能 且 可能` 还是`可能`。不确定的事情叠加不确定的事情，结果仍然不确定。

## 项目结构

```text
sanyan/
├── AGENTS.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── README.md
├── VERSION.py
├── ast_json.py              # AST JSON 导出
├── commands.py              # 自定义命令调用
├── dap_server.py            # DAP 调试适配器
├── debug_eval.py            # 调试辅助模块
├── doc_sync.py              # 文档同步检查
├── eval_helpers.py          # 求值辅助模块
├── evaluator.py             # 求值器
├── lexer.py                 # S 表达式词法
├── lsp_server.py            # LSP 服务器
├── main.py                  # 入口
├── parser.py                # S 表达式语法
├── param_matcher.py         # 参数匹配与类型检查
├── preprocess.py            # #include 预处理器
├── pyproject.toml           # 项目配置
├── repl.py                  # REPL 交互环境
├── runtime.py               # 运行环境
├── runtime_components.py    # 运行组件（作用域/IoT/调试/性能）
├── sandbox.py               # 沙箱安全机制
├── sanfmt.py                # 源码格式化器
├── sanyancc.py              # 交叉编译器
├── skin.py                  # 皮肤管理器
├── tail_call.py             # 尾递归优化
├── ternary_core.py          # 平衡三进制核心
├── values.py                # 值类型与语言异常
├── vm.py                    # 字节码虚拟机
├── runtime.c                # C 语言字节码解释器（主机端）
├── dp.c                     # S 表达式解析回归测试（C）
├── sanyan_parse.dll         # S 表达式 C 共享库解析器
├── sugar/                   # 糖语法转换器
│   ├── __init__.py
│   ├── errors.py
│   ├── lexer.py
│   └── parser.py
├── llvmgen/                 # LLVM 代码生成器
│   ├── __init__.py
│   ├── build.py             # 完整编译管线
│   ├── codegen.py           # AST → LLVM IR
│   ├── compiler.py          # 编译入口
│   └── runtime.c            # C 运行时库
├── ops/                     # 内置操作实现（28 模块）
│   ├── __init__.py
│   ├── _error_handler.py    # 统一错误处理装饰器
│   ├── _util.py
│   ├── arithmetic_ops.py    # 算术运算
│   ├── comparison_ops.py    # 比较运算
│   ├── concurrent_ops.py    # 并发与锁
│   ├── container_ops.py     # 列表/数组/字典/高阶函数
│   ├── control_ops.py       # 控制流
│   ├── crypto_ops.py        # 哈希与编解码
│   ├── device_registry.py   # IoT 设备注册表
│   ├── dispatcher.py        # 操作分派器
│   ├── file_ops.py          # 文件读写
│   ├── io_ops.py            # 输入输出/调试
│   ├── iot_ops.py           # 传感器/执行器
│   ├── json_ops.py          # JSON 序列化
│   ├── logic_ops.py         # 三态逻辑
│   ├── math_extra_ops.py    # 统计函数
│   ├── math_funcs_ops.py    # 数学函数
│   ├── net_ops.py           # HTTP 请求
│   ├── package_ops.py       # 包管理器
│   ├── random_ops.py        # 随机操作
│   ├── regex_ops.py         # 正则表达式
│   ├── registry.py          # 操作注册表
│   ├── sandbox_ops.py       # 沙箱操作
│   ├── string_ops.py        # 字符串操作
│   ├── system_ops.py        # 系统命令
│   ├── time_ops.py          # 时间戳/计时
│   ├── type_ops.py          # 类型判断
│   └── unicode_ops.py       # URL/Unicode 编码
├── sanyan-vscode/           # VS Code 扩展
│   ├── package.json
│   ├── extension.js
│   ├── language-configuration.json
│   └── syntaxes/
│       └── sanyan.tmLanguage.json
├── language/                # 皮肤文件
│   ├── chinese.json
│   └── english.json
├── lsp/                     # LSP 语言服务器组件
│   ├── __init__.py
│   ├── analysis.py
│   ├── handler.py
│   ├── keywords.py
│   └── protocol.py
├── examples/                # 示例
│   └── stm32-blinky/        # STM32 固件示例
│       ├── blinky.san
│       ├── firmware_data.h
│       ├── gen_header.py
│       ├── Makefile
│       ├── runtime_stm32.c
│       └── stm32_flash.ld
├── stdlib/                  # 标准库
├── tests/                   # 自动测试
├── docs/                    # 语言手册 + LLVM 文档
├── benchmark/               # 性能基准测试
└── packages/                # 包管理器缓存
```

## 三态词表

三言内置了一组中文语义词，直接映射三进制值：

| 语义 | 三进制值 | 整数值 | 含义 |
|---|---|---|---|
| 开 / 真 / 亮 / 有 / 是 / 高 / 启 / 通 | + | 1 | 确定的正向状态 |
| 守 / 可能 / 待 / 未知 / 中 | 0 | 0 | 不确定或保持当前状态 |
| 关 / 假 / 灭 / 无 / 否 / 低 / 停 / 断 | - | -1 | 确定的负向状态 |

> **语义区分**：`守` 常用于 IoT 保持状态；`可能` 常用于逻辑/投票/数据清洗。

这些不是关键字别名，是语言的语义层。`守` 表示"保持当前状态"（常用于 IoT），`可能` 表示"尚未确定"，`待` 表示"等待输入"。在 IoT 场景下，这些区别有实际意义。

## 路线图

- [x] 平衡三进制算术与三值逻辑
- [x] 自定义命令与匿名函数
- [x] 高阶函数（映射/过滤/归并）
- [x] 列表、数组、字典容器
- [x] IoT 传感器/执行器抽象
- [x] 类 C 糖语法 + S 表达式双语法
- [x] `返回` 关键字，函数提前退出
- [x] 异常处理 `尝试` / `捕获`
- [x] 文件读写原语
- [x] 国际化皮肤（母语可定制）
- [x] 全角符号兼容（含注释、引号、运算符）
- [x] 字符串插值 `模板{...}`
- [x] 三态分支 `判`
- [x] `跳出` / `继续` 关键字
- [x] 窄异常捕获
- [x] 列表字面量与生成式
- [x] 遍历-在
- [x] 模块导入（命名空间隔离）
- [x] 测试框架（断言相等/不相等/真/假/包含/大于/小于/大于等于/小于等于）
- [x] 双语法对照测试与示例
- [x] 类型标注与运行时校验（v3.10.0）
- [x] LSP 增强：格式化/引用/重命名/文档符号/折叠（v3.10.0）
- [x] 源码格式化器 sanfmt.py（v3.10.0）
- [x] 表达式断点调试（v3.10.0）
- [x] 性能剖析 --profile（v3.10.0）
- [x] AST JSON 导出（v3.10.0）
- [x] DAP 调试适配器（v3.10.0）
- [x] LLVM 代码生成器 + C 运行时库（v3.12.0）
- [ ] GPIO 真实硬件控制
- [ ] Web IDE
- [ ] 标准库扩展（更多自举模块）

## 为什么是中文

中文天然适合表达三进制。

英文只有 "on / off"，中文有 "开 / 关 / 守"。
英文只有 "true / false"，中文有 "真 / 假 / 可能"。

"可能"由"可"和"能"两个独立语素组成——"可不可以"和"能不能"是两个维度，它们的张力产生了第三态。这是中文造词法特有的能力。

三言没有"翻译"任何语言。它的中文关键字直接生长在三值逻辑之上。

## 三进制最有价值的地方

三言内置三态逻辑（真 / 可能 / 假），用中文词汇（开 / 关 / 守）直接表达三态决策，不需要用阈值和状态机来强行模拟不确定性。

不是万能钥匙，但恰好能打开最重要的门：

- **传感器冲突（IoT / 智能家居）**：信号不稳时保持当前状态，而非强行开关
- **用户犹豫（UI / 可穿戴 / VR）**：`可能` 是自然的交互状态
- **网络状态（后端 / 移动端）**：断网、超时、重试不需要额外状态机
- **数据质量（数据分析 / ETL）**：存疑数据保留"可能"标记，不清洗为 0 或 1
- **AI 置信度（机器学习 / 推理）**：推理结果为"不确定"本身就是有效输出
- **游戏 NPC（游戏开发）**：NPC 天然需要犹豫，不是所有行为都是二选一
- **脑机接口（前沿研究）**：大脑信号永远不确定

不适用：火灾报警、加密、网络协议等需要绝对确定性的场合。

## 已知限制

- **性能**：基于 Python 的树遍历解释器，高频循环场景性能有限。可使用 PyPy 运行获得 5-10 倍加速。
- **无标准输入流**：`输入()` 仅支持交互式输入，不支持管道重定向。
- **模块路径**：`导入("a.b.c")` 自动查找 `stdlib/a/b/c.san` → `stdlib/a/b/c/package.san`，支持嵌套包导入。

## For English Readers (TL;DR)

Sanyan is a Chinese programming language based on balanced ternary logic (+, 0, -).

Unlike most Chinese programming languages that merely translate English keywords, Sanyan leverages the fact that Chinese semantics naturally support ternary thinking: words like 守 (hold/keep), 可能 (maybe/uncertain), and 待 (await) carry nuanced third-state meanings that have no direct equivalent in English.

It runs on Python. It has:

- Native ternary arithmetic (not simulated)
- Kleene strong logic (true AND maybe = maybe)
- C-like sugar syntax + Lisp-style S-expressions
- Higher-order functions (map, filter, reduce)
- Built-in IoT sensor/actuator abstraction
- Skin system for keywords in any natural language
- Full-width symbol compatibility
- String interpolation, ternary switch judge, break/continue, narrow exception catching
- List comprehensions and container iteration

Quick start:

```bash
git clone https://github.com/shujingyin510/sanyan.git
cd sanyan
python main.py
```

Philosophy: uncertainty is not a bug — it's a legitimate computational state.

## AI 声明

本项目由 AI 辅助编程完成。代码的架构设计、实现与调试均在 AI 协作下完成。

## License

GNU General Public License v3.0 (GPL-3.0)
