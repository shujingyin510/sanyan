# 三言 Sanyan v3.8.0

[![VS Code Marketplace](https://img.shields.io/badge/VS%20Code-Marketplace-%23007ACC?logo=visualstudiocode)](https://marketplace.visualstudio.com/items?itemName=sanyan-lang.sanyan-language)
[![CI](https://github.com/shujingyin510/sanyan/actions/workflows/ci.yml/badge.svg)](https://github.com/shujingyin510/sanyan/actions)

> **面向不确定决策的三值编程语言。** 不确定不是 bug，是合法的计算状态。

---

## 一句话定位

三言是第一个把"可能"当作一等计算状态的编程语言。
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
├── main.py                # 入口
├── pyproject.toml         # 项目配置（Ruff 规则、打包）
├── CHANGELOG.md           # 版本历史
├── AGENTS.md              # 维护约定
├── CONTRIBUTING.md        # 贡献指南
├── ternary_core.py        # 平衡三进制核心（含定点数学库）
├── runtime.py             # 运行环境（作用域栈式链）
├── commands.py            # 自定义命令调用（重构拆分版）
├── preprocess.py          # #include 预处理器
├── evaluator.py           # 求值器（操作分发表→_OP_DISPATCH）
├── lexer.py               # S 表达式词法
├── parser.py              # S 表达式语法
├── sugar/                 # 糖语法转换器（Pratt 解析器）
│   ├── __init__.py        # 入口
│   ├── lexer.py           # 词法分析器
│   ├── parser.py          # Pratt 语法分析器
│   └── errors.py          # 错误收集与报告
├── skin.py                # 皮肤管理器
├── values.py              # 值类型与语言异常（Sanyan* 系列）
├── repl.py                # REPL 交互环境
├── ops/                   # 内置操作实现模块
│   ├── __init__.py        # 模块文档
│   ├── registry.py        # 统一操作注册表
│   ├── control_ops.py
│   ├── math_ops.py
│   ├── string_ops.py
│   ├── container_ops.py
│   ├── io_ops.py
│   ├── file_ops.py
│   ├── type_ops.py
│   ├── json_ops.py
│   ├── iot_ops.py
│   ├── package_ops.py     # 包管理器
│   └── device_registry.py # 设备注册表
├── sanyan-vscode/         # VS Code 扩展
│   ├── package.json
│   ├── extension.js
│   ├── language-configuration.json
│   └── syntaxes/
│       └── sanyan.tmLanguage.json
├── language/              # 皮肤文件（chinese.json / english.json）
├── examples/              # 示例（糖语法 + S 表达式双版本）
│   ├── greenhouse.san / greenhouse_se.san
│   ├── voting.san / voting_se.san
│   ├── data_clean.san / data_clean_se.san
│   └── sensor_pipeline_simple.san / sensor_pipeline_simple_se.san
├── stdlib/                # 标准库
│   ├── eval.san           # 纯 Sanyan 元循环求值器
│   ├── math.san / string.san / list.san
│   ├── iot.san / logic.san / io.san
│   └── test.san           # 测试框架
├── tests/                 # 自动测试（双版本）
│   ├── run_all.py         # 测试运行器
│   ├── test_core.py       # Python 单测 44 项
│   ├── test_ops.py        # ops 模块单测 66 项
│   ├── test_lsp.py        # LSP 协议测试 6 项
│   ├── test_package.py    # 包管理器测试 6 项
│   ├── test_eval.san      # 元循环求值器测试
│   ├── test_parser.py     # 解析器 AST 校验 22 项
│   ├── test_*.san         # 糖语法测试
│   └── test_*_se.san      # S 表达式对照测试
├── docs/                  # 语言手册
└── .vscode/               # VS Code 工作区配置
    └── settings.json

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

不是万能钥匙，但恰好能打开最重要的门：

- **传感器冲突（智能家居）**：不确定时不动作，而非强行判定
- **用户犹豫（智能穿戴 / VR）**：`可能` 是自然交互状态
- **AI 推理加速（NPU/GPU）**：乘法变加减，零值跳过
- **脑机接口**：大脑信号永远不确定
- **游戏 NPC**：NPC 天然需要犹豫

不适用：火灾报警、加密、网络协议等需要绝对确定性的场合。

## 已知限制

- **性能**：基于 Python 的树遍历解释器，高频循环场景性能有限。可使用 PyPy 运行获得 5-10 倍加速。
- **无标准输入流**：`输入()` 仅支持交互式输入，不支持管道重定向。
- **模块路径**：`导入("test")` 会自动查找 `stdlib/test.san`，但不支持嵌套包或包管理器。

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

MIT (c) 2025
