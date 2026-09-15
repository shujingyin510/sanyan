# 三言能力约束使用册子（`任务` / `约束`）

> **一句话**：三言是一门以「约束」为中心设计的语言——让不可信代码变成可以安全运行的代码。同一份约束声明，同时驱动运行时能力控制与三态失败语义。
> 状态：能力层已落地（v3.58.0），**仅解释器路径**（`--eval`）。设计全文见知识库 `约束-方向研究`。
> 本册所有示例均先实测（scratchpad 冒烟 19/19，2026-07-12）。

---

## 0 一分钟上手

```
任务 导出数据 {
    约束 { 许 网 }
    能否("网")          // → 真
}
```
把代码放进 `任务{}`，头一句 `约束{}` 声明它**能做什么**。默认**什么都不能**——只有纯计算恒通，五类效果（网/盘读/盘写/进程/外链）不 `许` 就一律判假：

```
任务 导 { 约束 { } 能否("网") }   // → 假（默认拒绝地板）
```

---

## 1 心智模型：约束是对三态值域的操作

`约束{}` 里默认拒绝一切效果。四关键字对能力集做运算——它们既是值层的三值模态算子（裸用），又是能力声明（在 `约束{}` 里）。**一个能力就是一个三值问句「我能做 X 吗 → 真/假/可能」。**

| 关键词 | 语义 | 对能力集 |
|---|---|---|
| `许 X` | 加法授权（主动真） | 从默认拒绝地板开一道门 |
| `只许 X` | 封印域（唯一真） | 能力宇宙 = 枚举集，域外「不在场」 |
| `禁 X` | 绝对拒绝（绝对假，不可逆，`禁`>`许`） | 挖一个任何 `许` 都掀不动的洞 |
| `允许 可能` | 容忍（被动可能，正交轴） | 块内 `若(可能)` 关卡豁免（帧级）；不改能力域 |

---

## 1.5 形式语义（规范条款 · 3.59）

> 陈述式、可判定；**只写实现已支撑的**。设计全文见知识库 `约束-方向研究`。

### §F.0 记号与域

- 能力类集合 `CAP = {网, 盘读, 盘写, 进程, 外链}`（封闭集）。
- 真值域 `{真, 假, 可能}`；权限判定**永不**产出 `可能`（分层律）。
- 帧记法：`F = ⟨A, D, δ, τ⟩`；无帧记 `⊤`。

### §F.1 状态定义

- **运行时帧**（四元组，`CapFrame`）：
  - `A ⊆ CAP`：许可集（`许` 下界，或 `只许` 封印后的闭集）
  - `D ⊆ CAP`：禁止集（`禁`，不可逆）
  - `δ ∈ ℝ⁺ ∪ {None}`：墙钟绝对死线；`None` = 无限
  - `τ ∈ {⊥, ⊤}`：容忍轴（`允许 可能`）；影响 D8 诊断，**不**改 `permits`
- **无帧 `⊤`**：零检查，一切效果类算子放行（`R-S4`）。
- **判定**：`permits(c) ≜ c ∉ D ∧ c ∈ A`（空 `约束{}` ⇒ `A = D = ∅`，五类全假，`R-S2`）。
- **纯计算**：`cap_of(op) = None` 的算子不参与判定，恒通（`R-S3`）。
- **`sealed` 是解析期构造量，不进运行时帧**：`只许` 在解析阶段形成闭集并拦截域外 `许`（`R-P4`）。

### §F.2 五关键字推理规则（声明 → 状态）

| 规则 | 声明 | 时机 | 转换 / 效果 |
|------|------|------|-------------|
| **R-P1** | `许 X`（无封印） | parse | `A := A ∪ X`（加法下界） |
| **R-P2** | `只许 X`（可多条） | parse | `sealed := sealed ∪ X`；最终 `A := sealed`（封死上界） |
| **R-P3** | `禁 X` | parse | `D := D ∪ X`（`禁` > `许`，不可逆） |
| **R-P4** | 封印后 `许 X` 且 `X ⊄ sealed` | parse | **违规** `SanyanValueError`（可判定，不进运行时） |
| **R-P5** | `限时 n` | parse | `δ₀ := min(已有, n)`；`n > 0` 为数字，否则 parse 报错 |
| **R-P6** | `允许 可能` | parse | `τ := ⊤`；宾语 ≠ `可能` 则 parse 报错 |
| **R-Q1** | `能否(c)` | eval | 恒 `真/假`：`真 ⟺ permits(c)`；无帧 `⊤` ⇒ `真` |
| **R-T1** | `限时` 挂点 | eval | 看门狗挂在**循环/遍历/尾递归**迭代点；**直线代码不拦** |
| **R-T2** | 超 `δ` | eval | 抛 `SanyanConstraintDenied`，`因=超时`，判=假，退帧 |
| **R-D1** | 直取式效果算子被禁 | eval | 抛 `SanyanConstraintDenied`（如 `约束禁止: 盘读(存在)`） |
| **R-D2** | 信封式效果算子被禁 | eval | **不抛**；返回信封 `判=假, 因=约束` |
| **R-D3** | `因` 枚举 | eval | `约束\|门控\|超时\|远端\|传输`（封闭）；约束/门控/超预算失败恒为假 |

### §F.3 嵌套继承公式（只紧不松）

设父帧 `F_p = ⟨A_p, D_p, δ_p, τ_p⟩`，子声明导出 `⟨A_c⁰, D_c⁰, δ_c⁰, τ_c⁰⟩`，压入子帧：

- **R-N1** `A := A_c⁰ ∩ A_p`（allowed 求交）
- **R-N2** `D := D_c⁰ ∪ D_p`（禁累加，不可回授）
- **R-N3** `δ := min(δ_c⁰, δ_p)`（无则取有；皆有取更早）
- **R-N4** `τ := τ_c⁰ ∨ τ_p`（父容忍则子继承；子可自开）
- **R-N5** **退出必弹帧**（`finally`；含约束拒绝与任意异常路径）
- **R-N6** **spawn 快照继承**：`并发`/`异步`/`并行块` 在 spawn 时 `capture_stack` → 子 `install_stack`；线程不是逃逸口

### §F.4 冲突判定表

| 编号 | 子句组合 | 时机 | 判定 | 结果 | 测试 |
|------|----------|------|------|------|------|
| X1 | `许 X` 且 X ⊄ sealed（有 `只许`） | parse | 违规 | `SanyanValueError` | `test_seal_rejects_widening` |
| X2 | `许 X` 且 X ⊆ sealed（冗余） | parse | 合法 | 无额外效果 | `test_seal_allows_redundant_grant` |
| X3 | 多个 `只许` | parse | 合法 | `sealed` 取并 | `test_seal_multiple_caps` |
| X4 | `许 X; 禁 X` | eval | 合法 | `permits=假`（禁胜） | `test_deny_overrides_grant` |
| X5 | `只许 X; 禁 X` | eval | 合法 | `permits=假` | `test_deny_overrides_seal` |
| X6 | `只许 X; 禁 Y`(Y∉X) | eval | 合法 | 禁对域外无额外效果 | `test_seal_deny_outside_seal_no_extra_effect` |
| X7 | 重复 `许 X` | parse | 合法 | 幂等（并集） | `test_duplicate_grant_idempotent` |
| X8 | 重复 `限时 n` | parse | 合法 | 取 `min` | `test_duplicate_timebox_takes_min` |
| X9 | `允许 可能` + 能力子句 | eval | 合法 | 正交，互不影响 `permits` | `test_constraint_allow_maybe_frame_skips_diagnostic` |
| X10 | `允许 X`（X ≠ `可能`） | parse | 违规 | 报错 | `test_constraint_allow_rejects_non_maybe` |
| X11 | 未知能力类 / 未知关键字 | parse | 违规 | 报错 | `test_unknown_cap_class_rejected` |
| X12 | 空 `约束{}` | eval | 合法 | `A=D=∅`，五类假、纯计算通 | `test_empty_constraint_denies_effects` |

### §F.5 违规值表示

- 直取式：抛 `SanyanConstraintDenied`（`R-D1`），可 `尝试/捕获`。
- 信封式：`(判=假, 因=约束)`，程序走否则/缓存分支（`R-D2`）。
- 超时：`(判=假, 因=超时)` 或抛（`R-T2`）；与「世界没回答→可能·因=超时」正交（见 §3）。
- 门控：`(判=假, 因=门控)`，区别于约束（`R-D3`）。

### §F.6 分层律与容忍轴

- **R-G1** 值层裸 `许/禁/只许/允许` **不改**能力集；唯一入口是 `约束{}`（`R-G1` → `test_bare_value_ops_dont_touch_capset`）。
- **R-G2** 表达式 `允许(x)`：透传真假 + `tolerated` 元通道；消费方为 D8 `若(可能)`。
- **R-G3** 块内 `允许 可能`：`τ=⊤`，块内 `若(可能)` **不收集诊断**；运行时仍假 fall-through。

### §F.7 规则 ↔ 测试对照

| 规则 | 测试 |
|------|------|
| R-S2 | `test_empty_constraint_denies_effects` |
| R-S3 | `test_pure_compute_always_allowed_in_block` |
| R-S4 | `test_no_frame_everything_permitted` |
| R-P1 | `test_grant_stays_additive_without_seal` / `test_grant_allows_named_class` |
| R-P3 | `test_deny_overrides_grant` |
| R-P4 | `test_seal_rejects_widening` / `test_seal_allows_redundant_grant` |
| R-P5 | `test_timebox_parse_missing_arg` / `_non_positive` / `_non_number` |
| R-P6 | `test_constraint_allow_rejects_non_maybe` |
| R-Q1 | `test_grant_allows_named_class`（能否真）/ `test_grant_leaves_others_denied`（能否假） |
| R-T1–T2 | `test_timebox_not_exceeded_completes` / `test_timebox_exceeded_raises_timeout` / `test_timebox_pops_frame_on_timeout` |
| R-N1–N3 | `test_nested_monotonic_intersect` / `test_nested_cannot_regrant_parent_denied` / `test_timebox_nested_inner_tighter` |
| R-N4 | `test_nested_frame_inherits_tolerate` / `test_child_can_open_tolerate_without_parent` |
| R-N5 | `test_frame_popped_after_task` / `_after_denial` |
| R-N6 | `test_e7_concurrent_worker_inherits_deny` / `test_e7_async_inherits_deny_at_spawn` / `test_e7_no_frame_concurrent_unaffected` |
| R-D1–D3 | `test_denied_effect_op_raises` / `test_envelope_op_denied_returns_envelope_not_raise` / `test_reason_distinguishes_constraint_from_gate` / `test_ffi_*` |
| R-G1 | `test_bare_value_ops_dont_touch_capset` |
| R-G2–G3 | `test_allow_expression_*` / `test_constraint_allow_maybe_frame_skips_diagnostic` |
| R-B1 | `test_bytecode_rejects_constraint_ops` / `test_sugar_ast_matches_sexpr` |
| S1–S4 成功判据 | 见 §成功判据 |

**Step2 已补（2026-09-10）**：X6/X7/X8 与 `R-N5` 非约束异常弹帧（`test_frame_popped_after_non_constraint_exception`）。

---

## 2 四关键字

```
任务 t { 约束 { 许 网 }     能否("盘写") }   // → 假：只开了网，盘写仍在地板
任务 t { 约束 { 只许 网 }   能否("盘读") }   // → 假：封印到只有网，盘读不在场
任务 t { 约束 { 许 网; 禁 网 } 能否("网") }  // → 假：禁 > 许，不可逆
```

`禁` 与「不授权」的区别：不授权可被更宽的 `许` 覆盖；`禁` 不可覆盖——**红线该用 `禁`**。

`只许` 与 `许` 的区别：`许` 是**加法下界**（「至少这些，之后可再加」）；`只许` 是**封死上界**（「能力宇宙恰是这些」）。封印后再 `许` 一个域外能力 = **可判定违规，解析期直接报错**：
```
任务 t { 约束 { 只许 网; 许 盘读 } … }   // ✗ 报错：许 盘读 越出 只许 封印域
```
安全审查时，`只许` 给的是**闭集保证**（「就这么多，解释器替你把关」），`许` 只保证下限——不可信代码的白名单该用 `只许`。

一条子句写「一个关键字 + 一个能力类」。多条用 `;` 或换行分隔（都行）：
```
约束 {
    许 网
    许 盘读
    禁 进程
}
```

---

## 3 违规是值，不是异常（核心特色）

传统 `open()` 无权限 → 抛 `PermissionDenied` → 异常。三言把它降维成**控制流**：

```
任务 导出 {
    约束 { }                                       // 默认拒绝，网未许
    设 信封 = http请求("GET", "http://外部/数据")
    若 (信封判(信封) == 真) {
        取键(信封, "值")
    } 否则 {
        "走本地缓存"                                // ← 判假 → 走这里，全程无异常
    }
}
```

**双面契约**（按算子风格）：
- **信封式**（`http请求` / `py调` / `c调`）被禁 → 返回 **判=假、因=约束**，永不抛。
- **直取式**（`http读` / `读文件` / `存在`）被禁 → 抛 `约束禁止: 盘读(存在)`，可 `尝试` 接：
  ```
  任务 t { 约束 { } 尝试 { 存在("x.txt") } 捕获 e { "被约束拦" } }   // → "被约束拦"
  ```

**`因` 字段**（封闭枚举 `约束|门控|超时|远端|传输`）——给程序看，`错` 给人看。程序凭 `因` 分辨「管理员禁止」与「网络故障」，不必解析错误文本：

| 情形 | 判 | 因 |
|---|---|---|
| 约束块未 `许` | 假 | `约束` |
| 全局门控关（`SANYAN_NET=0`） | 假 | `门控` |
| 世界拒绝（404 / 连接拒） | 假 | `远端` / `传输` |
| 世界没回答（单次调用超时） | **可能** | `超时` |
| 任务超 `限时` 预算 | **假** | `超时` |

> **`判` 与 `因` 正交**：`因=超时` 既可配 **可能**（单次调用世界没回答，不确定）、也可配 **假**（任务超 `限时` 预算 = 约束失败，你没资格再跑）。约束/门控/超预算失败恒为**假**——解释器确定知道「没资格」，不是「不知道」。

**探询**：`能否("网")` → 真/假（恒不返回可能，权限是可判定事实）。
```
任务 t { 约束 { 许 网 } 若 (能否("网") == 真) { "联网" } 否则 { "缓存" } }   // → "联网"
```

---

## 4 能力类清单（五类，粗粒度）

| 类 | 覆盖算子（举要） |
|---|---|
| `网` | http读/http写/http请求、三态Web服务器/路由/监听、安装/更新/加载包 |
| `盘读` | 读文件/load/import、列出目录/存在/是文件/是目录/当前路径 |
| `盘写` | 写文件/写二进制、sqlite 增删改与开库 |
| `进程` | 执行（shell）、设环境变量、沙箱/沙箱开（元能力，块内自动锁死） |
| `外链` | py导入/py取/py调/py项、c载入/c调 |

约束只认这**五个类名**，不认算子名——写算子名会报错（可判定性法则）：
```
任务 t { 约束 { 许 http读 } … }   // ✗ 报错：未知能力类 `http读`
任务 t { 约束 { 许 网 } … }        // ✓
```
清理类算子（py释/c释）无门、恒允许。纯计算（约 230 个）永不需要列。

---

## 5 嵌套单调 · 并发继承

**嵌套只能收紧**（子块是父块的子集，`禁` 累加）：
```
任务 外 { 约束 { 许 网; 许 盘读 }
    任务 内 { 约束 { 许 网 } 能否("盘读") } }   // → 假：内层交集掉了盘读
```

**并发/异步不是逃逸口**——块内起的 `并发`/`异步定义`/`并行块` 子任务，**继承 spawn 时的约束**：
```
任务 t { 约束 { }
    设 r = 并发(http请求("GET", "http://外部"))
    r[0] }                                       // → 信封 判假·因=约束（worker 也被拦）
```

---

## 6 分层律：共享词汇，不共享状态

四关键字**裸用**是值层三值算子，**只有在 `约束{}` 里**才动能力集：

```
许(1)          // → 真（值层构造子，返回真）
能否("盘写")   // → 真（上一句没建约束帧！裸 许 绝不碰能力集）
```

- **表达式层只描述「事实」**：`允许(网络())` 只是容忍那次调用的可能返回，**绝不打开网权限**。
- **改能力集的唯一入口是 `约束{}`**。

FFI 同样吃这套（`py调` 与 `http请求` 同为信封式自守卫）：
```
// 需 SANYAN_FFI=1
任务 t { 约束 { } py导入("os") }          // → 判假·因=约束（不抛）
任务 t { 约束 { 许 外链 } py导入("os") }  // → 判真（放行）
```

---

## 7 边界与威胁模型（诚实声明）

| 层 | 场景 | 本机制够不够 |
|---|---|---|
| L0 | LLM/脚本手滑（误删、误联、死循环） | **够**（块级默认拒绝，90% 场景） |
| L1 | 非恶意越界（依赖摸到 FFI） | 够（外链类整体禁） |
| L2 | 对抗代码 | **不够**——需子进程 + OS 隔离（**不承诺进程内防对抗**） |

约束只描述**能力边界**，不描述**业务规则**（可判定性法则）：`周一才能联网`、`VIP 才能调用` 一律违宪——业务条件用 `若` 包 `任务`，别塞进 `约束{}`。

---

## 8 常见坑

1. **`限时(n)` 与 `允许` 均已生效**：`限时(n)` 给任务套墙钟死线，循环/递归跑飞超预算 → 抛 `SanyanConstraintDenied·因=超时`（判假），退帧干净；直线代码不拦。`允许(x)` 透传真假并挂 `tolerated` 元通道；约束子句 `允许 可能` 为帧级容忍——块内 `若(可能)` **不再收集诊断**（运行时仍按假 fall-through，collect-only 关卡行为不变）。
2. **能力类是五个粗类，不是算子名**：`禁 删文件` 不支持（`删文件` 不是类），用 `禁 盘写`。细粒度（带路径域的 `限写("输出/")`）是 v2。
3. **糖 `任务名{约束{…}}` 仅解释器路径**：字节码/种子 VM 无能力栈运行时，`sanyanc` 编译期显式报错「仅解释器路径支持」，repl 自动回退求值器。
4. **`约束{}` 里 `许 网` 不能有括号**：它是声明不是调用（`许(x)` 带括号是值层算子，两回事——分层律）。
5. **默认拒绝是地板，不是开关**：空 `约束{}` = 全禁而非全开。要用某类效果必须显式 `许`。
6. **对抗代码别只靠它**：L2 威胁请叠子进程隔离（见 §7）。

---

## 8 成功判据 S1–S4（2026-09-10 收尾验收）

| 判据 | 含义 | 证据 |
|------|------|------|
| **S1 默认拒绝** | 空 `约束{}` 内效果类判假，纯计算恒通 | `test_empty_constraint_denies_effects` / `test_pure_compute_always_allowed_in_block` |
| **S2 信封走缓存** | 外传企图在默认拒绝内**全程无异常**，判假→缓存分支 | `test_s2_demo_denied_net_falls_to_cache_no_exception` / 糖语法版 `test_sugar_s2_demo_no_exception` |
| **S3 封印不可扩** | `只许` 域外再 `许` = 解析期可判定报错 | `test_seal_rejects_widening` |
| **S4 并发继承** | 子求值器/spawn 继承约束，线程不是逃逸口 | `test_e7_concurrent_worker_inherits_deny` / `test_e7_async_inherits_deny_at_spawn` |

配套：E7 capture/install、字节码拒约束算子、糖语法 `任务名{约束{…}}`、`限时` 看门狗——`tests/test_capability_stack.py` + `test_capability_gates.py` **54 项全绿**。

---

## 9 速查

**关键词**：`任务 名 { 约束 { 许/只许/禁 类; 允许 可能; 限时(n) } 体… }`
**能力类**：`网` `盘读` `盘写` `进程` `外链`
**探询**：`能否("类")` → 真/假
**因枚举**：`约束` `门控` `超时` `远端` `传输`（成功为空）
**优先级**：`禁` > `只许`域 > `许` > 默认拒绝；`允许` 正交（表达式 `允许(x)` 打标 / 块内 `允许 可能` 帧级豁免 D8）
**S-式等价**：`任务 t { 约束 { 许 网 } 体 }` ≡ `(任务 "t" (约束 (许 网)) 体)`

---

*示例路径见 `tests/test_capability_stack.py` + `test_capability_gates.py` + `test_maybe_gate.py`。设计与推翻条件见知识库 `约束-方向研究`。*
