# 三态认知框架 Sanyan v3.58.0

[![VS Code Extension](https://img.shields.io/badge/VS%20Code-%E8%AF%AD%E6%B3%95%E9%AB%98%E4%BA%AE-%23007ACC?logo=visualstudiocode)](sanyan-vscode/README.md)
[![CI](https://github.com/shujingyin510/sanyan/actions/workflows/test.yml/badge.svg)](https://github.com/shujingyin510/sanyan/actions)
[![PyPI](https://img.shields.io/pypi/v/ternary-engine?label=ternary-engine)](https://pypi.org/project/ternary-engine/)
[![Playground](https://img.shields.io/badge/%E2%96%B6%20%E5%9C%A8%E7%BA%BF%E8%AF%95%E7%8E%A9-Playground-c0392b)](https://shujingyin510.github.io/sanyan/playground/)

> **三态认知框架** — 平衡三进制中文语言 + 引擎（求值器 / 字节码 VM / C 种子 / LLVM）+ 能力约束系统。核心定位：让不可信代码（agent / 插件 / 生成码 / 用户脚本）变成可以安全运行的代码。Agent 自更新子系统已独立至 [sanyan-agent](https://github.com/shujingyin510/sanyan-agent)。

**[▶ 在线试玩 Playground](https://shujingyin510.github.io/sanyan/playground/)** — 浏览器直接跑三言核心子集，零安装（离线可双击仓库内 [`playground/index.html`](playground/index.html)）

[English](docs/README_EN_archive.md)

---

## 更新摘要

### Unreleased（2026-09-10，不铸版本号）
- **Agent 拆仓 + 扫尾**：子系统迁 [sanyan-agent](https://github.com/shujingyin510/sanyan-agent)；本仓文档/配置去 Agent 正文，历史计划入 `docs/archive/`
- **`允许` 抑制语义**：`允许(x)` 挂 tolerated 元通道；`若(可能)` D8 关卡豁免；帧级 `允许 可能`——约束四关键字+限时闭环
- **糖解析 AST 契约**：修 `字列` 错映射；生产路径返回 AST 不是字符串
- **Windows Level 3 C 种子**：CRT 模拟层，差分电池 28/28 全平台

详见 [CHANGELOG](CHANGELOG.md) Unreleased。

### v3.58.0 (2026-07-12)
- **约束系统 MVP**：能力层约束 `任务 { 约束 { 许 网 } 体 }`——默认拒绝的实例级能力栈 + dispatch 咽喉强制；四关键字 `许`/`只许`/`禁`/`允许`，违规是值（判假·因=约束）走控制流不抛异常
- **规划关键字落地**：`置信度`/`信度传播`/`清空`/`克隆`/`掩码`/`压入`/`弹出`/`竞速`/`休眠` 等 15+ 新关键字注册；26 项测试全绿
- **S2 演示跑通**：带外传企图的代码在 `任务{默认拒绝}` 内 `http请求` → 判假·因=约束，程序全程无异常走缓存分支

### v3.57.0 (2026-07-12)
- **网络接口收口**：`http请求` 三态信封（超时=可能）+ `SANYAN_NET` 门控 + SSRF 豁免 + 杀两处假货
- **三态路由接线修复**：处理器以请求字典为实参，路径参数可达

详见 [CHANGELOG](CHANGELOG.md)

---

## 一句话定位

三态认知框架 = **三态语言（DSL）** + **三态引擎（TernaryEngine）** + **Knowledge Runtime**。

语言只是接口层——真正的核心是 **Knowledge + Confidence + Selection** 的可验证自改进系统。

---

## 五层架构

```
Layer 5: Knowledge Validation（知识验证层）
  Confidence / Cluster / Consistency
        ↓
Layer 4: Knowledge Layer（知识层）
  MetaLearningDB / TaskEmbedding / ClusterLearning
        ↓
Layer 3: Evolution Layer（进化层）
  Ranking / Cost / Budget / UCB
        ↓
Layer 2: Policy Layer（策略层）
  Config / Strategy / Hypothesis
        ↓
Layer 1: Frozen Core（冰冻核心）
  Reviewer / Replay / History / Ternary
```

### 三态逻辑贯穿整个系统

| 层 | 三态表现 | 说明 |
|---|---|---|
| 语言层 | TRUE / FALSE / UNKNOWN | Kleene三值逻辑 |
| Agent层 | 高置信度 / 低置信度 / 未知 | 决策门控（**已迁 sanyan-agent**） |
| Knowledge Layer | 可信知识 / 弱知识 / 未知知识 | 知识可靠性评估（**已迁 sanyan-agent**） |
| Evolution Layer | 接受 / 拒绝 / 收集更多数据 | 三态裁决（**已迁 sanyan-agent**） |

---

## 核心实验

> ⚠️ **说明：以下实验 1–4 为合成模拟（synthetic simulation），用于展示机制设计，非真实任务 / 真实 LLM 实测。**
> 其数值由模拟器的「策略-任务匹配度」公式与随机采样产生，结论受模拟器设计决定，不能作为「成功率」「因果链」「+43.6%」这类实证主张引用。
> 真实任务实证为加固计划阶段 1 的目标，详见 [`docs/CLAIMS.md`](docs/CLAIMS.md)。

### 实验1: 因果链闭环（合成模拟·机制演示）

```
机制链路: Knowledge → Better Prediction → Better Selection → Higher Success Rate

Baseline:       40.9% 模拟成功率
Knowledge:      82.5% 模拟成功率 (+41.6%)
Knowledge+Conf: 84.5% 模拟成功率 (+2.0%)
模拟提升:       +43.6%（由模拟器设计决定，非实证）
```

### 实验2: 知识迁移（合成模拟·机制演示）

```
直接迁移配置 → 负收益 (-4.6%)  ✗
迁移任务规律 → 正收益 (+27.9%) ✓

结论: 迁移的是规律，不是配置。战略比战术更容易迁移。
```

### 实验3: 知识置信度（合成模拟·机制演示）

```
documentation:  151样本  置信度0.92 (高)
analysis:       111样本  置信度0.87 (中)
feature:        172样本  置信度0.84 (中)
bug_fix:        183样本  置信度0.79 (中)
refactor:        87样本  置信度0.69 (低，需更多数据)
```

### 实验4: Task Taxonomy（合成模拟·机制演示）

```
test:           72.2% → thorough
feature:        66.8% → standard
documentation:  49.5% → direct
performance:    48.4% → multi_candidate
bug_fix:        45.8% → multi_fix
refactor:       45.0% → careful
analysis:       42.5% → direct
```

---

## 为什么是三进制

三言原生三态逻辑（真 / 可能 / 假）不是噱头——它能解决二进制无法表达的真正问题。四个量化对比案例：

- **电路模拟** — 9 种输入组合的全量真值表，三言正确性是数学保证的
- **数据清洗** — `可能` 阻止 NULL 传播；二态 None 静默输出误导性 0
- **API 健康检测** — 超时 ≠ 宕机；二态聚合会触发误告警
- **游戏 NPC** — 犹豫是合法行为；二态需要额外状态变量

详见 [为什么是三进制](docs/ternary-logic.md)。

---

## 快速开始

```bash
git clone https://github.com/shujingyin510/sanyan.git
cd sanyan
python repl/main.py
```

> **性能提示**：实测数据（`python benchmark/run_benchmark.py --quick`）：
> - Python 求值器：fib(25) ≈ 9.0 秒，fizzbuzz(100) ≈ 0.06 秒
> - 字节码 VM：`python -X utf8 repl/main.py --vm examples/fizzbuzz.san`
> - [PyPy](https://pypy.org)：`pypy repl/main.py` — 即时 5-10 倍加速
> - **LLVM 原生编译**：[安装 llvmlite](https://pypi.org/project/llvmlite/) 后 `python compiler/compile_llvmgen.py`
> - **C VM**：`gcc csrc/runtime.c -o vm && ./vm program.bin` — 无 Python 依赖

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
python repl/main.py examples/greenhouse.san
python repl/main.py examples/sensor_pipeline_simple.san
```

### 模块化安装

三言支持按需安装，避免拉取不需要的依赖：

```bash
pip install sanyan           # 完整版（所有功能）
pip install sanyan[core]     # 核心语言（解释器 + 标准库）
pip install sanyan[sugar]    # 糖语法解析器
pip install sanyan[vm]       # 字节码 VM
pip install sanyan[llvmgen]  # LLVM 编译器（需要 llvmlite）
pip install sanyan[lsp]      # IDE 支持（LSP + DAP）
pip install sanyan[tools]    # 独立工具（格式化器/交叉编译器）
pip install sanyan[dev]      # 开发依赖（pytest/ruff/mypy）
```

| 用户场景 | 推荐安装 |
|----------|----------|
| 仅运行 .bin 字节码 | `pip install sanyan-vm` |
| 交互式编程 | `pip install sanyan-core` |
| 完整 IDE 体验 | `pip install sanyan` |
| 嵌入式开发 | `pip install sanyan-core sanyan-llvmgen` |
| 仅代码格式化 | `pip install sanyan-tools` |

## 杀手级示例：智能温室控制系统

光线/人体传感器返回三态信号（充足/不足/不稳、有人/无人/不确定），温度返回连续值。系统按三态决策控制灯光、窗帘、风扇、加热，冲突时按优先级处理——**不确定态 `守` 作为一等公民直接参与决策**，无需"阈值+默认值"的二进制技巧来模拟。

```c
// 三态传感器直接驱动决策（节选自 examples/greenhouse.san）
若 (光线值 == 真) { 置 窗帘 = 开; 记录("光照充足，窗帘拉开。") }
再若 (光线值 == 假) { 置 灯 = 亮; 记录("光照不足，补光灯开启。") }
否则 { 置 灯 = 守; 置 窗帘 = 守; 记录("光照不稳，设备保持原状。") }   // ← 守：不动作
```

某次运行输出（传感器状态随机）：

```text
【检测 1/10】光线: 充足，温度: 22（适宜），人体: 不确定
光照充足，补光灯关闭，窗帘拉开。
人体检测：不确定，灯光维持现状。      ← 不确定 → 维持现状，不瞎动
...
  灯: 关 (-)   窗帘: 开 (+)   风扇: 守 (0)   加热: 守 (0)
```

> 完整可运行代码见 **[`examples/greenhouse.san`](examples/greenhouse.san)**（自包含，无需外部模块）；等效 S 表达式版 `examples/greenhouse_se.san` 输出一致、100% 稳定。

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

## 功能特性

### 语言核心

| 特性 | 说明 |
|---|---|
| **三态逻辑** | 原生 `真`/`可能`/`假`（Kleene 强逻辑），`可能 且 可能` = `可能` |
| **三进制算术** | 平衡三进制加/减/乘/除/余/幂/取位，`TernaryALU` 从位运算层三值 |
| **双语法** | 糖语法（类 C）+ S 表达式，共享求值器，可混用 |
| **母语编程** | 关键字可切换为任何自然语言（中/英皮肤），全角符号兼容 |
| **三态分支 `判`** | `判 (表达式) { 真 → ..., 可能 → ..., 假 → ... }` |
| **三态模式匹配** | `匹配3(值) { 真→..., 可能→..., 假→... }` — 显式三态分支（**仅 S-表达式 AST**；糖语法未实现） |
| **置信度区间匹配** | `匹配信度(值, 阈值) { 高→..., 中→..., 低→... }` |
| **链式信度传播** | `链(步骤1, 步骤2, ...)` — 置信度逐级传播 |
| **三态解包** | `解包(值)` / `或解(值, 默认值)` — 三态值解包 |
| **渐进类型** | 返回类型标注 `-> 类型`，可选类型 `?类型`，运行期自动校验 |
| **异常处理** | `尝试 { } 捕获 (e) { }`，窄异常捕获 |
| **高阶函数** | `映射`/`过滤`/`归并`/`排序`/`反转`/`去重`/`求和`/`合并` |
| **Lambda** | `λ(x) { x * 2 }` 或 `函数(x) { x * 2 }` |
| **模块系统** | `导入("path")`、`导出 name1 name2`、嵌套包导入 |
| **外语互操作 ⚗️** | Python 进程内桥（`py导入`/`py调` 六算子），外调统一**三态信封**（判/值/错分离）；`SANYAN_FFI=1` 显式开启，仅解释器路径——见手册 §20 与 `docs/ffi_plan.md` |
| **网络** | 客户端 `http读`/`http写`/`http请求`（三态信封：**超时=可能**、真实状态码）+ `三态Web服务器` 路由/中间件；SSRF 防护 + `SANYAN_NET` 门控；中文 URL/中文路由自动编解码——使用册子 `docs/network.md` |
| **能力约束 ⚗️** | `任务 名 { 约束 { 许 网; 禁 进程 } 体 }`——**默认拒绝**能力块（网/盘读/盘写/进程/外链五类），四关键字 `许`/`只许`/`禁`/`允许`；**违规是值**（判假·因=约束，走控制流不抛异常）+ `能否("网")` 探询；嵌套单调 + 并发继承；仅解释器路径——使用册子 `docs/constraint.md` |
| **行注释** | `//`（半角）、`／／`（全角）、`#` 三种注释语法 |

### 字节码 VM

| 特性 | 说明 |
|---|---|
| **65 操作码** | ISA v2 完整指令集：算术/比较/逻辑/容器/字符串/字典/控制流/IO |
| **自举** | `bytecode_compiler.san` 编译自身，VM 产出与 Python 求值器逐字节一致 |
| **32 位代码大小** | 支持 >64KB 字节码（旧版 16 位限制 64KB） |
| **独立 .bin** | sugar.bin（~10KB）和 llvmgen.bin（~72KB）可在 VM 上独立运行 |
| **C VM** | `csrc/runtime.c` 纯 C 实现，65 指令，不依赖 Python |
| **C VM 测试** | `csrc/test_runtime.c` 61 项单元测试，覆盖全部指令集 |
| **STM32 固件** | `compiler/sanyancc.py` 交叉编译 → `runtime_stm32.c`，Blue Pill 硬件验证 |

### LLVM 代码生成

| 特性 | 说明 |
|---|---|
| **AST → LLVM IR** | `llvmgen/codegen.py` + `llvmgen/compiler.py`，~1500 行 codegen |
| **63 位整数** | tagged pointer 升 i64，值域 ±4.6×10^18 |
| **浮点支持** | IEEE 754 double，`fadd`/`fmul`/`fdiv` 内联，整数自动提升 |
| **import 静态链接** | 编译期递归编译依赖，`san_{mod}__{fn}` 名字修饰 |
| **try/catch** | `@g_error` LLVM 可见全局 + 手动栈展开 |
| **Arena 分配器** | 64KB 初始化，auto-grow，搬指针替代 malloc |
| **自举 LLVM 编译器** | `llvmgen.san`（V5）辅助函数已内联，`compiler/compile_llvmgen.py` 无注入直接编译 |

### 并发与分布式

| 特性 | 说明 |
|---|---|
| **并发融合** | `并发融合(任务1, 任务2, ...)` — 并发执行+Kleene结果融合 |
| **并发竞速** | `并发竞速(超时ms, 任务1, ...)` — 取最先完成的结果 |
| **并发全部** | `并发全部(任务1, ...)` — 全部成功才返回真 |
| **共识** | `共识(a, b, ...)` — 多传感器共识，全部真时信度上升 |
| **三态锁** | `锁`/`锁住`/`开锁` — 信度感知互斥 |

### 泛型容器

| 特性 | 说明 |
|---|---|
| **三态集** | `三态集` / `三态集加` / `三态集删` / `三态集含` / `三态集并` / `三态集交` / `三态集差` |
| **三态图** | `三态图` / `三态图加节点` / `三态图加边` / `三态图最短路` / `三态图连通` |
| **三态队列** | `三态队列` / `三态入队` / `三态出队` |
| **三态栈** | `三态栈` / `三态压栈` / `三态弹栈` |

### Web 框架

| 特性 | 说明 |
|---|---|
| **三态Web服务器** | `三态Web服务器(端口)` — 创建Web服务器 |
| **三态路由** | `三态路由(server, 方法, 路径, 处理器)` — 添加路由 |
| **置信度降级** | 低置信度请求自动降级返回503 |
| **中间件** | CORS/日志/速率限制/置信度守卫 |

### 数据管线

| 特性 | 说明 |
|---|---|
| **三态管线** | `三态管线` / `三态管线加阶段` / `三态管线处理` / `三态管线统计` |
| **三态数据** | `三态数据(值, 置信度, 来源)` — 带置信度的数据单元 |
| **三态清洗** | `三态清洗(数据, 规则)` — 去空/填充/归一化 |
| **三态聚合** | `三态聚合(数据列表, 方式)` — 平均/求和/计数/融合 |
| **三态验证** | `三态验证(数据, 规则)` — 模式验证 |

### 标准库与工具

| 特性 | 说明 |
|---|---|
| **标准库** | `json.san` `http.san` `regex.san` `csv.san` `string.san` `list.san` `math.san` `network.san` `hardware.san` 等 |
| **LSP 语言服务器** | 格式化/引用查找/重命名/文档符号/折叠/语义补全/hover |
| **DAP 调试适配器** | VS Code 断点调试协议支持 |
| **源码格式化器** | `sanfmt.py` — 类 black/prettier |
| **性能剖析** | `--profile` 标志 + `:profile` REPL 命令 |
| **AST JSON 导出** | `--ast-json` 导出解析后的 AST |
| **包管理器** | `安装`/`卸载`/`搜索`/`包信息`/`包列表`/`包索引`/`加载包`（6 个示例包） |
| **IoT 抽象** | `注册设备`/`置`/`读`/`查`/`对` 传感器/执行器操作 |
| **三值 IoT 案例** | 传感器融合、容错控制、状态机（含 Python/C 对比） |

### Agent 子系统（已迁出）

> Agent 运行时 / 自更新闭环 / 可读决策 DSL **不在本仓维护**。
> 独立仓：<https://github.com/shujingyin510/sanyan-agent> · 入口见 [`docs/AGENT_MOVED.md`](docs/AGENT_MOVED.md)。
> 本仓 CLI：`sanyan agent` / `sanyan bench` 仅输出指路提示（退出码 2）。

## 三进制算术（模拟实现）

当前版本的三进制基于 Python 整数模拟。`core/ternary_core.py` 使用 `TritValue` 类包装整数值（+1 / 0 / -1）：

- **BT 类**: `from_int(n)` → 三进制 trits 列表，`to_int(trits)` → Python 整数
- **算术运算**: 三态值 → `BT.to_int()` → Python 整数计算 → `BT.from_int()` → 三态值
- **逻辑运算**: 真值表匹配（Kleene 强三值逻辑），不依赖整数转换
- **展示层**: `symbol` 属性输出 `+` / `0` / `-` 表示法

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
├── core/          # 求值器 / 词法 / 语法 / 运行时 / 平衡三进制 / 值与异常
├── ops/           # 内置算子（30+ 模块：算术/逻辑/IO/网络/并发/沙箱/能力约束…）
├── sugar/         # 糖语法转换器（类 C → S 表达式）
├── vm/            # 字节码 VM（自举）
├── compiler/      # .san → .bin 编译器 + 包管理
├── llvmgen/       # LLVM 代码生成器（AST → 原生机器码）
├── stdlib/        # 标准库（.san）+ 自举 .bin（sugar.bin / llvmgen.bin）
├── repl/ · lsp/   # 交互环境 / LSP·DAP 语言服务
├── language/      # 中英文皮肤（关键字映射）
├── packages/      # 包管理器与示例包
├── examples/      # 示例程序（温室/传感器融合/IoT/STM32…）
├── tests/         # 自动测试
├── docs/          # 文档（手册 / 约束 / 网络 / LLVM…）
├── agent_system/  # （已迁出）→ https://github.com/shujingyin510/sanyan-agent
├── sanyan/        # 包命名空间与统一 CLI（sanyan.cli）
└── csrc/          # C 语言 VM（65 指令）
```

> 完整逐文件结构见 **[`docs/project_structure.md`](docs/project_structure.md)**。

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
- [x] LLVM 原生编译（AOT，LLVM → 汇编 → 可执行文件）
- [x] C 字节码 VM（65 指令完整版，ISA v2）
- [x] C VM 单元测试（61 项，覆盖全部指令集）
- [x] 浮点支持 + 整数自动提升
- [x] import 静态链接
- [x] BUILTIN_OPS 自动生成（从 language/*.json 同步）
- [x] 核心模块 docstring 注释
- [x] 架构文档 ARCHITECTURE.md + 贡献指南 CONTRIBUTING.md
- [x] llvmgen.san 自举完成 V5（辅助函数内联）
- [x] 包管理器增强（卸载/搜索/包信息）
- [x] 标准库扩充（network/hardware/math 矩阵统计）
- [x] 三值逻辑 IoT 案例（传感器融合/容错控制/状态机）
- [x] 三值 vs 二值对比文档
- [x] 文档整合：22→10 个 md
- [x] Agent 子系统已拆仓（测试随迁 sanyan-agent）
- [x] #include 预处理全链路支持（Python + C VM）
- [ ] GPIO 真实硬件控制
- [ ] Web IDE
- [ ] 社区生态建设

## 三态逻辑贯穿整个系统

三态逻辑不是语言特色，是整个系统的认知哲学：

| 层 | 三态表现 | 说明 |
|---|---|---|
| 语言层 | TRUE / FALSE / UNKNOWN | Kleene三值逻辑 |
| Agent层 | 高置信度 / 低置信度 / 未知 | 决策门控（**已迁 sanyan-agent**） |
| Knowledge Layer | 可信知识 / 弱知识 / 未知知识 | 知识可靠性评估（**已迁 sanyan-agent**） |
| Evolution Layer | 接受 / 拒绝 / 收集更多数据 | 三态裁决（**已迁 sanyan-agent**） |

```
语言时代：TRUE / FALSE / UNKNOWN
    ↓
Agent时代：高置信度 / 低置信度 / 未知
    ↓
Knowledge Layer：可信知识 / 弱知识 / 未知知识
    ↓
进化系统：接受 / 拒绝 / 收集更多数据
```

**核心洞察：**
- 没有Confidence时：经验 = 真理
- 有Confidence时：经验 = 待验证知识
- 这是科学方法：观察→假设→置信度→实验→更新置信度

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

- **性能**：Python 求值器在高频循环下性能有限，推荐使用 `--vm` 模式（字节码 VM）或 PyPy 获得加速。LLVM 后端将算术直接编译为原生整数指令（`add i64`），不经过三进制表示层，性能接近 C。
- **无标准输入流**：`输入()` 仅支持交互式输入，不支持管道重定向。
- **模块路径**：`导入("a.b.c")` 自动查找 `stdlib/a/b/c.san` → `stdlib/a/b/c/package.san`，支持嵌套包导入。

## 三进制实现说明

实现细节见[三进制算术](#三进制算术模拟实现)一节。LLVM 后端的实际路径：`llvmgen/codegen.py` 在编译时直接将算术操作（`加`/`减`/`乘`/`除`）生成原生 LLVM IR（`add i64`/`sub i64`/`mul i64`/`sdiv i64`），不经过三进制表示转换。只有在需要装箱时才通过 `shl+or+inttoptr` 编码为标记指针，算术热路径上性能接近原生 C。

这不是硬件三进制。真正的三进制计算机（如 Setun）在硬件层每个比特就是三态。本项目的三进制逻辑语义是正确的（Kleene 强逻辑），但底层存储和运算是二进制的。

未来方向：如果出现三进制硬件（如三态忆阻器或量子三态），三言的语义层可以直接映射到真实三进制硬件，无需修改语言规范。

## 进化子系统（已迁出）

> Knowledge / Evolution / Policy 等五层架构中的 Agent 侧实现已随 Agent 拆仓迁至
> [sanyan-agent](https://github.com/shujingyin510/sanyan-agent)。本仓不再维护进化闭环代码与相关合成模拟数字
> （历史机制演示数字见 [`docs/CLAIMS.md`](docs/CLAIMS.md)，实证以 UR 仓为准）。

## AI 声明

本项目由 1 位工程师 + AI 协作完成。架构设计、核心算法、调试方向均由人主导，AI 负责具体代码实现。

> 📖 [三言 —— 一个人的编程语言](docs/愿景故事.md) — 项目愿景故事

## License

GNU General Public License v3.0 (GPL-3.0)
