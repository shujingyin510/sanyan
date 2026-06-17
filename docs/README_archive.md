> ⚠️ Archived — see [README.md](../README.md) for current version.

# 三态认知框架 Sanyan v3.29.0

[![VS Code Extension](https://img.shields.io/badge/VS%20Code-%E8%AF%AD%E6%B3%95%E9%AB%98%E4%BA%AE-%23007ACC?logo=visualstudiocode)](sanyan-vscode/README.md)
[![CI](https://github.com/shujingyin510/sanyan/actions/workflows/test.yml/badge.svg)](https://github.com/shujingyin510/sanyan/actions)

> **三态认知框架** — 从三进制语言到 Knowledge Runtime 的演进。核心贡献：构建了一个可验证的自改进 Agent 知识系统，证明了 Knowledge → Calibration → Selection → Success 的因果链。

[English](README_EN.md)

---

## v3.37 更新摘要

- **统一 CLI**：`sanyan` 命令入口，替换散落式 `--flag`（agent run/chat/evolve/dashboard/bench）
- **Agent 安全基准**：49 种 bug 注入，五层检测管道，检出率 98%，逻辑类 100%
- **Agent 诚实度基准**：100 题 × 5 类，三维评分（正确率+校准ECE+认知越界），Truth Calibration 越界率 -15.2%
- **五层检测下放规则层**：语义 diff + 逻辑审计 + Truth Calibration 接入 Agent 运行时
- **全量 CI 绿**：1650+ 测试，mypy 零错误，ruff 零错误，preflight 一键检查

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
| Agent层 | 高置信度 / 低置信度 / 未知 | 决策门控 |
| Knowledge Layer | 可信知识 / 弱知识 / 未知知识 | 知识可靠性评估 |
| Evolution Layer | 接受 / 拒绝 / 收集更多数据 | 三态裁决 |

---

## 核心实验

### 实验1: 因果链闭环

```
Knowledge → Better Prediction → Better Selection → Higher Success Rate

Baseline:       40.9% 成功率
Knowledge:      82.5% 成功率 (+41.6%)
Knowledge+Conf: 84.5% 成功率 (+2.0%)
总体提升:       +43.6%
```

### 实验2: 知识迁移

```
直接迁移配置 → 负收益 (-4.6%)  ✗
迁移任务规律 → 正收益 (+27.9%) ✓

结论: 迁移的是规律，不是配置。战略比战术更容易迁移。
```

### 实验3: 知识置信度

```
documentation:  151样本  置信度0.92 (高)
analysis:       111样本  置信度0.87 (中)
feature:        172样本  置信度0.84 (中)
bug_fix:        183样本  置信度0.79 (中)
refactor:        87样本  置信度0.69 (低，需更多数据)
```

### 实验4: Task Taxonomy

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
python main.py
```

> **性能提示**：实测数据（`python benchmark/run_benchmark.py --quick`）：
> - Python 求值器：fib(25) ≈ 9.0 秒，fizzbuzz(100) ≈ 0.06 秒
> - 字节码 VM：`python -X utf8 main.py --vm examples/fizzbuzz.san`
> - [PyPy](https://pypy.org)：`pypy main.py` — 即时 5-10 倍加速
> - **LLVM 原生编译**：[安装 llvmlite](https://pypi.org/project/llvmlite/) 后 `python compile_llvmgen.py`
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
python main.py examples/greenhouse.san
python main.py examples/sensor_pipeline_simple.san
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

## 功能特性

### 语言核心

| 特性 | 说明 |
|---|---|
| **三态逻辑** | 原生 `真`/`可能`/`假`（Kleene 强逻辑），`可能 且 可能` = `可能` |
| **三进制算术** | 平衡三进制加/减/乘/除/余/幂/取位，`TernaryALU` 从位运算层三值 |
| **双语法** | 糖语法（类 C）+ S 表达式，共享求值器，可混用 |
| **母语编程** | 关键字可切换为任何自然语言（中/英皮肤），全角符号兼容 |
| **三态分支 `判`** | `判 (表达式) { 真 → ..., 可能 → ..., 假 → ... }` |
| **三态模式匹配** | `匹配3(值) { 真→..., 可能→..., 假→... }` — 显式三态分支 |
| **置信度区间匹配** | `匹配信度(值, 阈值) { 高→..., 中→..., 低→... }` |
| **链式信度传播** | `链(步骤1, 步骤2, ...)` — 置信度逐级传播 |
| **三态解包** | `解包(值)` / `或解(值, 默认值)` — 三态值解包 |
| **渐进类型** | 返回类型标注 `-> 类型`，可选类型 `?类型`，运行期自动校验 |
| **异常处理** | `尝试 { } 捕获 (e) { }`，窄异常捕获 |
| **高阶函数** | `映射`/`过滤`/`归并`/`排序`/`反转`/`去重`/`求和`/`合并` |
| **Lambda** | `λ(x) { x * 2 }` 或 `函数(x) { x * 2 }` |
| **模块系统** | `导入("path")`、`导出 name1 name2`、嵌套包导入 |
| **行注释** | `//`（半角）、`／／`（全角）、`#` 三种注释语法 |

### 字节码 VM

| 特性 | 说明 |
|---|---|
| **52 操作码** | 完整指令集：算术/比较/逻辑/容器/字符串/字典/控制流/IO |
| **自举** | `bytecode_compiler.san` 编译自身，VM 产出与 Python 求值器逐字节一致 |
| **32 位代码大小** | 支持 >64KB 字节码（旧版 16 位限制 64KB） |
| **独立 .bin** | sugar.bin（~10KB）和 llvmgen.bin（~72KB）可在 VM 上独立运行 |
| **C VM** | `csrc/runtime.c` 纯 C 实现，52 指令，不依赖 Python |
| **C VM 测试** | `csrc/test_runtime.c` 61 项单元测试，覆盖全部指令集 |
| **STM32 固件** | `sanyancc.py` 交叉编译 → `runtime_stm32.c`，Blue Pill 硬件验证 |

### LLVM 代码生成

| 特性 | 说明 |
|---|---|
| **AST → LLVM IR** | `llvmgen/codegen.py` + `llvmgen/compiler.py`，~1500 行 codegen |
| **63 位整数** | tagged pointer 升 i64，值域 ±4.6×10^18 |
| **浮点支持** | IEEE 754 double，`fadd`/`fmul`/`fdiv` 内联，整数自动提升 |
| **import 静态链接** | 编译期递归编译依赖，`san_{mod}__{fn}` 名字修饰 |
| **try/catch** | `@g_error` LLVM 可见全局 + 手动栈展开 |
| **Arena 分配器** | 64KB 初始化，auto-grow，搬指针替代 malloc |
| **自举 LLVM 编译器** | `llvmgen.san`（V5）辅助函数已内联，`compile_llvmgen.py` 无注入直接编译 |

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

### Agent 可读决策 DSL

> 详见 [ternary_agent/README.md](ternary_agent/README.md) — v5 架构、四阶段设计、补丁目录。

| 特性 | 说明 |
|---|---|
| **三态推理** | LLM 认知态 → 三态映射 → Kleene 传播 → 贝叶斯置信度 → 保护门控 |
| **多假设并行** | Top-3 候选方案同时探索，锦标赛选优，早停淘汰死假设 |
| **任务分解** | 大任务自动递归拆解，每层有界上下文（4000 token 硬限） |
| **工具依赖图** | P1: 工具链合法性预校验，过滤无效组合 |
| **能力注册表** | P9: 任务需求 vs 工具能力匹配，误选率 -50% |
| **多样性控制** | P8: 关键词聚类去重，避免 5≈1 假多样化 |
| **失败分类** | P3: 6 类 FailureMode（空/缺/格式/超时/逻辑/循环），精准重试 |
| **自适应阈值** | P4: 50 轮后从历史自动调参，消除硬编码 |
| **语义缓存** | P5: 相似任务直接复用，命中率 ~15% |
| **可观测性** | P7: 全链路指标（早停率/缓存命中/LLM 比较次数/成本预测） |
| **成本预测** | P10: 历史数据模型替代 LLM 猜测，准确率 +20% |
| **执行回放** | P11: 完整运行记录 + diff 对比，Debug 效率 +300% |
| **经验学习** | 工具成功率统计 + 遗忘衰减 + 模块风险评估 |
| **多提供商** | DeepSeek / OpenAI / 千问 / Gemini / 小米MIMO / Token Plan / Ollama 七家 |
| **声明式策略** | `agent_policy.san` 纯数据 + 场景规则，热重载 |
| **并行执行** | P14: 独立工具并行执行，工具链自动并行化，预计加速 2-4x |
| **智能压缩** | P22: 多策略上下文压缩（分层摘要+滑动窗口+重要性评分） |
| **跨会话学习** | P19: SQLite 持久化工具成功率、失败模式库、任务类型映射 |
| **安全沙箱** | P16: 命令黑名单/白名单、文件系统守卫、只读模式、审计日志 |
| **流式响应** | P28: LLM 边生成边显示，支持可中断、渐进式输出 |
| **高阶工具组合** | P31: Unix 风格管道、复合工具、条件工具链 |
| **工具自发现** | P13: 自动扫描 ops/*.py 注册工具，提取元数据（参数/副作用/成本） |
| **多Agent共享** | P34: 共享上下文空间、共享符号表、Agent协调器（任务分发+结果聚合） |
| **Token追踪** | 实时统计 LLM Token 用量，支持 DeepSeek/Gemini API |
| **策略自优化** | Layer 1: Prompt自进化 + Tool Selection学习 + 策略切换 + A/B Rollout |
| **自主循环** | Layer 2: 文件监控 + 自动验证 + Agent修复 + 日志持久化 + 健康监控 |
| **约束进化** | Layer 3: 接口不变只改内部 + 多后端差分验证 + 多目标评估 + 自举验证（框架完成，闭环开发中） |

使用方式：

```bash
# 交互模式（多轮对话，支持热重载）
python -X utf8 run_agent.py

# 单次编程（LLM 自动生成代码→执行→返回结果）
python -X utf8 run_agent.py "写程序：1加到1000"

# 直接执行三言代码（不走 LLM）
python -X utf8 run_agent.py "(设 x 10)(输出(加 x 5))"

# 文件操作
python -X utf8 run_agent.py "把AGENTS.md里的v0.3改成v0.4"

# 安全沙箱（只读模式，禁止文件修改）
python -X utf8 run_agent.py "分析代码结构" --sandbox

# 性能报告（显示Token用量、工具耗时）
python -X utf8 run_agent.py "任务" --report

# 实时仪表盘
python -X utf8 run_agent.py "任务" --dashboard

# 决策追踪
python -X utf8 run_agent.py "任务" --trace

# 流式输出
python -X utf8 run_agent.py "任务" --stream

# 执行工具管道
python -X utf8 run_agent.py "任务" --pipeline read_and_analyze

# 自举验证（第3层）
python -X utf8 run_agent.py --self-host

# 约束进化验证（第3层）
python -X utf8 run_agent.py --evolve

# 自动化进化闭环（第3层）
python -X utf8 run_agent.py --auto-evolve --max-cycles 3

# Agent自主改代码闭环（第3层）
python -X utf8 run_agent.py --code-evolve --max-cycles 3

# 带审查的进化闭环（第3层）
python -X utf8 run_agent.py --review-evolve
```

自主循环（第2层）：

```bash
# 文件监控模式
python -X utf8 agent_loop.py --watch

# 连续循环模式
python -X utf8 agent_loop.py --continuous

# 查看统计和健康状态
python -X utf8 agent_loop.py --status
```

交互模式命令：

```
/状态    — 三态决策摘要
/记忆    — 任务记忆
/仪表盘  — 实时仪表盘
/追踪    — 决策链可视化
/性能    — 性能报告（Token用量、工具耗时）
/经验    — 跨会话经验（工具可靠性、失败模式）
/安全    — 安全沙箱状态（审计日志）
/共享    — 共享上下文空间
/管道    — 工具管道列表
```

## 三进制算术（模拟实现）

当前版本的三进制基于 Python 整数模拟。`ternary_core.py` 使用 `TritValue` 类包装整数值（+1 / 0 / -1）：

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
├── ARCHITECTURE.md            # 架构文档
├── AGENTS.md                  # AI 协作约定（自举状态、测试、代码规范）
├── CHANGELOG.md               # 变更日志
├── CONTRIBUTING.md            # 贡献指南
├── 愿景故事.md                 # 项目愿景故事（从Setun到三言）
├── README.md                  # 项目说明（中文）
├── README_EN.md               # 项目说明（英文）
├── build_combined.py          # 构建脚本：展开 #include 生成合并 .san
├── build_exe.py               # PyInstaller 打包脚本
├── sanyan/                    # 包命名空间（模块化入口）
│   └── __init__.py
├── commands.py                # 自定义命令调用
├── compile_bytecode.py        # .san → .bin 编译器（支持 #include）
├── compile_llvmgen.py         # llvmgen.san → llvmgen.bin 编译（V5 自举，无注入）
├── dap_server.py              # DAP 调试适配器
├── doc_sync.py                # 文档同步检查
├── eval_utils.py              # 求值工具函数（类型转换/边界检查）
├── evaluator.py               # 求值器
├── gui.py                     # 可视化编译器 GUI
├── lexer.py                   # S 表达式词法
├── lsp_server.py              # LSP 服务器
├── main.py                    # 入口（支持 --vm 字节码缓存）
├── parser.py                  # S 表达式语法
├── param_matcher.py           # 参数匹配与类型检查
├── preprocess.py              # #include 预处理器
├── pyproject.toml             # 项目配置
├── repl.py                    # REPL 交互环境
├── ternary_engine.py           # 三态认知引擎（Kleene×贝叶斯×门控）
├── disasm.py                   # 字节码反汇编器
├── verify.py                   # 字节码验证器
├── preflight.py                # 发版前预检（lint+test+自举）
├── run_agent.py               # Agent 启动器
├── run_v2.py                  # v2 演示启动器
├── run_v2_demo.py             # v2 演示脚本
├── run_village_demo.py        # 村庄演示脚本
├── run_village_observe.py     # 村庄观察器（NPC 自主生活模拟）
├── runtime.py                 # 运行环境（作用域/IoT/调试/性能）
├── sandbox.py                 # 沙箱安全机制
├── sanfmt.py                  # 源码格式化器
├── sanyanc.py                # 编译器（S表达式 + sugar） + 包管理器
├── setup.py                   # 安装脚本
├── skin.py                    # 皮肤管理器
├── tail_call.py               # 尾递归优化
├── ternary_core.py            # 平衡三进制算术（模拟）
├── values.py                  # 值类型 + 异常体系
├── vm.py                      # 字节码 VM（自举能力）
├── agent_system/              # Agent 系统（Python 运行时 + Sanyan DSL）
│   ├── __init__.py
│   ├── README.md              # Agent 文档
│   ├── agent_runtime.py       # Agent V5 引擎
│   ├── agent_tools.py         # Agent V5 工具层
│   ├── agent_tool_graph.py    # 工具依赖图 + 能力注册 + 工具元数据 + 自发现
│   ├── agent_decompose.py     # Phase 0: 任务分解
│   ├── agent_hypothesis.py    # Phase 1: 多假设 + 锦标赛
│   ├── agent_resource.py      # Phase 2: 资源管控
│   ├── agent_project.py       # 项目引擎: 分解→执行→验证→重试
│   ├── agent_context.py       # 智能上下文压缩（分层摘要+滑动窗口+重要性评分）
│   ├── agent_experience.py    # 经验库: 跨任务 pattern 匹配 + AVOID 提示
│   ├── agent_parallel.py      # 并行执行引擎（工具链并行+假设并行验证）
│   ├── agent_sandbox.py       # 安全沙箱（命令过滤+文件系统守卫+审计日志）
│   ├── agent_learning.py      # 跨会话学习（SQLite持久化+失败模式库+自适应选择）
│   ├── agent_obs.py           # 可观测性（决策追踪+性能分析+仪表盘）
│   ├── agent_streaming.py     # 流式响应（LLM边生成边显示+可中断）
│   ├── agent_composition.py   # 高阶工具组合（管道+复合工具+条件链）
│   ├── agent_shared.py        # 多Agent共享上下文（共享空间+符号表+协调器）
│   ├── agent_strategy.py      # Layer 1: 策略自优化（Prompt进化+Tool学习+策略切换+A/B）
│   ├── agent_loop.py          # Layer 2: 自主循环（文件监控+连续循环+健康监控）
│   ├── agent_loop_monitor.py  # Layer 2: 循环监控（日志+统计+健康+回滚验证）
│   ├── agent_evolution.py     # Layer 3: 约束进化（接口不变+差分验证+多目标评估）
│   ├── agent_evolution_v2.py  # Layer 3: Patch DSL + Mutation Budget + 三态评分 + Tournament
│   ├── agent_review.py        # Layer 4: Reviewer Agent（独立代码审查+对抗补丁检测）
│   ├── agent_benchmark.py     # Layer 4: Real Benchmark（真实基准测试）
│   ├── agent_dashboard.py     # Layer 4: Evolution Dashboard（进化仪表盘）
│   ├── agent_test_gen.py      # Layer 4: Test Generator（测试用例生成）
│   ├── agent_history.py       # Layer 4: PatchHistory（Patch历史数据库+可信度权重）
│   ├── agent_validation.py    # Layer 4: Evolution Validation（100次随机+收敛+Reviewer）
│   ├── agent_stress.py        # Layer 4: Evolution Stress Test（长期稳定性+退化测试）
│   ├── agent_knowledge.py     # Layer 5: Knowledge Layer（TaskClassifier+TaskEmbedding+ClusterLearning）
│   ├── agent_knowledge_confidence.py # Layer 5: Knowledge Confidence（知识置信度计算）
│   ├── agent_generalization.py # Layer 5: Knowledge Generalization（知识泛化验证）
│   ├── agent_causal_chain.py  # Layer 5: Causal Chain（因果链闭环验证）
│   ├── agent_meta_knowledge.py # Layer 5: Meta-Knowledge Transfer（元知识迁移）
│   ├── agent_param_importance.py # Layer 5: Parameter Importance Ranking + StrategySchema
│   ├── agent_cost_aware.py    # Layer 5: Cost-Aware Evolution（收益/成本感知+UCB）
│   ├── agent_task_taxonomy.py # Layer 5: Task Taxonomy（任务分类+MetaLearningDB）
│   ├── agent_knowledge_validation.py # Layer 5: Knowledge Validation（知识分化验证）
│   └── sanyan/                 # Sanyan 语言实现（Agent DSL）
│       ├── agent.san           # Agent 核心逻辑（决策函数、记忆、追踪）
│       ├── agent_policy.san    # 纯数据策略（配置、阈值、映射规则）
│       ├── decision.san        # 决策核心（信任感知规则匹配）
│       ├── memory.json         # Agent 记忆持久化
│       └── runtime_v2/         # V2 运行时
│           ├── village_game.san
│           ├── npc_game.san
│           └── ...
├── sugar/                     # 糖语法转换器
│   ├── __init__.py
│   ├── errors.py
│   ├── lexer.py
│   └── parser.py
├── llvmgen/                   # LLVM 代码生成器（已拆分）
│   ├── __init__.py
│   ├── build.py               # 完整编译管线
│   ├── codegen.py             # AST → LLVM IR（419 行）
│   ├── compiler.py            # 编译入口 + 解析器（424 行）
│   ├── helpers.py             # Python 辅助函数（377 行）
│   ├── ir_builder.py          # CodegenContext 构建器
│   ├── ir_fixes.py            # IR 后处理工具（220 行，从 compiler.py 拆出）
│   ├── ops_gen.py             # 主编译入口（410 行）
│   ├── ops_gen_control.py     # 控制流编译（341 行，从 ops_gen.py 拆出）
│   ├── ops_gen_helpers.py     # 算术/容器辅助（240 行，从 ops_gen.py 拆出）
│   ├── runtime.c              # C 运行时库（arena 分配器 + 52 操作码）
│   └── type_mapping.py        # 类型映射与运行时函数规范
├── ops/                       # 内置操作实现（30 模块）
│   ├── __init__.py
│   ├── arithmetic_ops.py      # 算术运算
│   ├── comparison_ops.py      # 比较运算
│   ├── concurrent_ops.py      # 并发与锁
│   ├── list_ops.py            # 列表/数组/通用容器操作
│   ├── dict_ops.py            # 字典操作
│   ├── control_ops.py         # 控制流
│   ├── crypto_ops.py          # 哈希与编解码
│   ├── device_registry.py     # IoT 设备注册表
│   ├── dispatcher.py          # 操作分派器
│   ├── file_ops.py            # 文件读写（支持 #include）
│   ├── io_ops.py              # 输入输出/调试
│   ├── iot_ops.py             # 传感器/执行器
│   ├── json_ops.py            # JSON 序列化
│   ├── logic_ops.py           # 三态逻辑
│   ├── math_extra_ops.py      # 统计函数
│   ├── math_funcs_ops.py      # 数学函数
│   ├── net_ops.py             # HTTP 请求
│   ├── package_ops.py         # 包管理器（安装/卸载/搜索/信息）
│   ├── random_ops.py          # 随机操作
│   ├── regex_ops.py           # 正则表达式
│   ├── registry.py            # 操作注册表
│   ├── sandbox_ops.py         # 沙箱操作
│   ├── string_ops.py          # 字符串操作
│   ├── system_ops.py          # 系统命令
│   ├── time_ops.py            # 时间戳/计时
│   ├── type_ops.py            # 类型判断
│   └── unicode_ops.py         # URL/Unicode 编码
├── sanyan-vscode/             # VS Code 扩展
│   ├── package.json
│   ├── extension.js
│   ├── language-configuration.json
│   └── syntaxes/
│       └── sanyan.tmLanguage.json
├── language/                  # 皮肤文件
│   ├── chinese.json
│   └── english.json
├── lsp/                       # LSP 语言服务器组件
│   ├── __init__.py
│   ├── analysis.py
│   ├── handler.py
│   ├── keywords.py
│   └── protocol.py
├── csrc/                      # C 语言 VM（52 指令完整版）
│   ├── runtime.c              # VM 实现（支持 #include 预处理）
│   ├── test_runtime.c         # VM 单元测试（61 项）
│   └── dp.c                   # parse_sanyan 原生编译测试
├── stdlib/                    # 标准库
│   ├── _bootstrap.san         # S 表达式引导解析器（自举起点）
│   ├── bytecode_compiler.san  # 自举字节码编译器（76 行）
│   ├── bytecode_compiler.bin  # 编译器 .bin（VM 可直接加载）
│   ├── sugar.san              # 糖语法解析器（合并版，由 build_combined.py 生成）
│   ├── sugar.bin              # 解析器 .bin（VM 独立运行）
│   ├── sugar_src.san          # （可选）糖语法拆分源码入口
│   ├── llvmgen.san            # LLVM 代码生成器（合并版，由 build_combined.py 生成）
│   ├── llvmgen.bin            # LLVM 编译器 .bin（V5 自举，无注入）
│   ├── llvmgen_src.san        # llvmgen 拆分源码入口（#include 子模块）
│   ├── llvmgen/               # llvmgen 拆分子模块
│   │   ├── preamble.san       # 全局变量 + 辅助函数
│   │   ├── utils.san          # 工具函数（生成模块头/尾、字符串常量）
│   │   ├── compiler.san       # 主编译函数
│   │   ├── runtime_ir.san     # 运行时 IR 生成
│   │   └── entry.san          # 编译顶层入口 + 导出
│   ├── combined.san           # sugar + llvmgen 合并版
│   ├── network.san            # 网络库（TCP/UDP/连接池/健康检查）
│   ├── hardware.san           # 硬件抽象层（GPIO/I2C/SPI/传感器）
│   ├── math.san               # 数学库（矩阵/向量/统计/概率分布）
│   ├── json.san               # JSON 解析/序列化
│   ├── http.san               # HTTP 客户端
│   ├── regex.san              # 正则表达式
│   ├── csv.san                # CSV 解析/生成
│   ├── string.san             # 字符串工具
│   ├── list.san               # 列表操作
│   ├── algorithm.san          # 算法库（排序/搜索/素数/斐波那契）
│   ├── collection.san         # 数据结构（栈/队列/集合）
│   ├── validate.san           # 数据验证
│   ├── iot.san                # IoT 便捷函数
│   ├── logic.san              # 三态逻辑
│   ├── stat.san               # 三态统计
│   ├── datetime.san           # 日期时间
│   ├── file.san               # 文件工具
│   ├── io.san                 # IO 工具
│   ├── test.san               # 测试框架
│   ├── eval.san               # 元循环求值器
│   ├── parse.san              # S 表达式解析器
│   ├── tokenize.san           # 词法分析器
│   ├── repl.san               # REPL
│   └── pipeline.san           # 编译管线
├── packages/                  # 包管理器
│   ├── index.json             # 包索引（6 个包）
│   ├── sample/                # 示例包（问候工具）
│   ├── math_extended/         # 扩展数学库（复数/向量）
│   ├── logging/               # 结构化日志库
│   ├── web_utils/             # Web 工具（URL/HTML/Cookie）
│   ├── data_pipeline/         # 数据管道（映射/过滤/聚合）
│   └── config/                # 配置管理库
├── examples/                  # 示例
│   ├── sensor_fusion.san      # 三值逻辑传感器融合（三言版）
│   ├── sensor_fusion.py       # 传感器融合（Python 对比版）
│   ├── sensor_fusion.c        # 传感器融合（C 对比版）
│   ├── fault_tolerant_control.san # 容错控制系统
│   ├── iot_state_machine.san  # IoT 设备状态机（三言版）
│   ├── iot_state_machine.py   # IoT 状态机（Python 对比版）
│   ├── circuit_sim.san        # Kleene 三值电路模拟
│   ├── data_cleaning.san      # 三态数据清洗管道
│   ├── health_check.san       # API 健康检测
│   ├── npc_decision.san       # NPC 犹豫决策
│   ├── greenhouse.san         # 温室监控
│   ├── voting.san             # 三态投票
│   └── stm32-blinky/          # STM32 嵌入式示例
│       ├── blinky.san         # LED 闪烁程序
│       ├── runtime_stm32.c    # STM32 VM + 外设驱动
│       ├── Makefile           # 构建系统
│       └── stm32_flash.ld     # 链接脚本
├── tests/                     # 自动测试（629+ 项）
│   ├── test_core.py           # 核心单测（138 项）
│   ├── test_ops.py            # ops 模块单测（92 项）
│   ├── test_ops_ext.py        # 扩展 ops 单测（64 项）
│   ├── test_parser.py         # 解析器 AST 校验（28 项）
│   ├── test_commands.py       # 命令模块单测（18 项）
│   ├── test_sugar_san.py      # sugar.san 测试（45 项）
│   ├── test_llvmgen.py        # LLVM 代码生成测试（53 项）
│   ├── test_self_host.py      # 字节码编译器自举验证（8 项，含 Level 2 + Level 3）
│   ├── test_sugar_self_host.py # sugar.bin 自举验证（3 项）
│   ├── test_effect_types.py    # 效应类型测试（30 项，确定/不确定）
│   ├── test_diff_fuzz.py       # 差分模糊测试（12 项，四后端一致）
│   ├── test_disasm.py          # 反汇编器测试（6 项）
│   ├── test_vm.py             # VM 字节码测试（91 项）
│   ├── test_c_vm.py           # C VM 测试（14 项，需 gcc）
│   ├── test_agent.py          # Agent 测试（31 项）
│   ├── test_llvm_native.py    # LLVM 原生编译测试
│   └── run_all.py             # 集成测试（46 项）
├── docs/                      # 文档
│   ├── manual.md              # 用户手册
│   ├── llvm.md                # LLVM 文档
│   ├── ternary-logic.md        # 三值逻辑深度解析
│   └── package_development.md # 包开发指南
├── benchmark/                 # 性能基准测试
├── ternary_agent/             # 三言 Agent（可读决策 DSL）
│   ├── agent.san              # Agent 核心逻辑（决策函数、记忆、追踪）
│   ├── agent_policy.san       # 纯数据策略（配置、阈值、映射规则）
│   └── memory.json            # Agent 记忆持久化
├── run_agent.py               # Agent 启动器（单次/交互/热重载）
└── csrc/dp.c                  # parse_sanyan 原生编译验证
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
- [x] LLVM 原生编译（AOT，LLVM → 汇编 → 可执行文件）
- [x] C 字节码 VM（52 指令完整版）
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
- [x] Agent 子系统测试（17 项）
- [x] #include 预处理全链路支持（Python + C VM）
- [ ] GPIO 真实硬件控制
- [ ] Web IDE
- [ ] 社区生态建设

## 三态逻辑贯穿整个系统

三态逻辑不是语言特色，是整个系统的认知哲学：

| 层 | 三态表现 | 说明 |
|---|---|---|
| 语言层 | TRUE / FALSE / UNKNOWN | Kleene三值逻辑 |
| Agent层 | 高置信度 / 低置信度 / 未知 | 决策门控 |
| Knowledge Layer | 可信知识 / 弱知识 / 未知知识 | 知识可靠性评估 |
| Evolution Layer | 接受 / 拒绝 / 收集更多数据 | 三态裁决 |

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

## 四层进化架构

```
Layer 3: Knowledge Layer（知识层）
  - MetaLearningDB（项目经验数据库）
  - TaskEmbedding（任务向量化）
  - ClusterLearning（自动聚类）
  - 目标：不同任务→不同策略（条件最优）
        ↓
Layer 2: Evolution Layer（进化层）
  - ParameterRanker（参数影响力排名）
  - CostAwareRanker（收益/成本排名）
  - ExplorationBudget（探索预算）
  - UCBExploration（UCB探索策略）
        ↓
Layer 1: Policy Layer（策略层）
  - ConfigSchema（可进化配置参数）
  - StrategySchema（策略参数化）
  - HypothesisSchema（候选参数）
        ↓
Layer 0: Frozen Core（冰冻核心，不可修改）
  - Reviewer（代码审查）
  - TernaryEngine（三态决策）
  - PatchHistory（历史记录）
  - TaskReplay（任务回放）
```

### 三层知识体系

| 层 | 内容 | 共享策略 |
|---|---|---|
| Global Knowledge | 任务模式→策略模式（元知识） | 共享统计规律 |
| Project Memory | 项目专属经验（最优参数/Patch模式） | 项目内共享 |
| Personal Memory | 用户偏好/习惯 | 不共享 |

**LLM知识 vs Agent知识：**
- LLM知识 = Prior（推测）：世界知识，已预训练
- Agent知识 = Evidence（证据）：项目级因果知识，经过验证

> LLM解决"我知道什么"；Agent知识库解决"在这个项目里什么真的有效"

## AI 声明

本项目由 1 位工程师 + AI 协作完成。架构设计、核心算法、调试方向均由人主导，AI 负责具体代码实现。

> 📖 [三言 —— 一个人的编程语言](愿景故事.md) — 项目愿景故事

## License

GNU General Public License v3.0 (GPL-3.0)
