# Changelog

---

## [v3.56.0] — 2026-07-08

> **FFI 全线落地周（⚗️ 实验性）+ 实验策略 v2 转向。外语互操作从 RFC 到能用：Python 进程内桥（六算子+三态信封）、C 声明导入（c_bind_gen 生成器 → manifest+三言桩 → ctypes 运行时 → LLVM extern 双后端），同一 C 库在解释器与原生编译下产出一致——差分角落回纳达成。agent 线按预算指示冻结前完成 25 轮总账：失败数据库结构化 92 条实跑记录并当天产出四条硬规律（含推翻自己前一天的错误排除结论），拆步执行器落地待 A/B。**

### ⭐ Highlights

- **FFI 层 A——Python 进程内桥（M1/M2）**：`py导入/py取/py调/py项/py列/py释` + `信封判`；外调一律返回**三态信封** `{'判','值','错','源'}`（判定通道与载荷通道分离——Python 返回 `False` 封送为 `值=假` 而 `判=真`）；`解包/或解` 识别信封三分支（裸 TritValue 回归钉在册）；句柄注册表上限 4096、`py导入` 幂等、零拷贝管道；`SANYAN_FFI=1` 显式开启（默认关，能力面算子信封报假）；json 三行示例真实解释器双态冒烟
- **FFI 层 B——C 声明导入（M3/M4）**：`scripts/c_bind_gen.py`（pycparser 声明层解析 → `<lib>.ffi.json` manifest + `<lib>.san` 桩；err 惯例不推断默认 null **由人审补注**；变参标注、函数指针/位域/数组进 skipped 清单 fail-closed 可审）→ `ops/c_ffi_ops.py`（c载入/c调/c释，manifest 驱动签名与 **err 四惯例**：null/null_ret/neg_ret/errno；struct 按值 ↔ 三言字典往返；cstr utf-8）→ **`llvmgen/ffi_extern.py`（M4-LLVM）**：同一 manifest 发射 `declare` extern 直呼——**同一 C 库双后端（ctypes 解释器 vs 原生编译）产出一致，FFI 唯一可差分的角落回纳差分口径**（RFC §4.6 验收）
- **后端矩阵诚实化**：编译器对算子位上的 FFI 名显式报错"仅解释器路径支持"（字符串数据不误伤）；repl 默认 VM 模式打印 `[FFI]` 提示后回退求值器执行——不静默；`--eval` 不留错误 .bin 缓存
- **桩经 `导入` 端到端**：`import_module` 记模块目录、`c载入` 相对路径按其解析——桩+manifest+库三件套同目录，从任意处导入即用（终极验收：`(导入 "…/mini.san")` 后裸名 `(add 2 3)` 直调 C）
- **实验策略 v2（预算驱动转向）**：每次实跑必须带假设、每周一个新功能、"一次实验的产出是一条规律不是一个补丁"。**失败数据库**（`su_stats.py`）回填 25 轮 92 条记录，首日四条硬规律：runbook 变体转化率 30%→42%→**0%**→45%（受控对比揪出"首选模块级"文案事故并翻案）、死因类 diff 形状签名（+73/-0 纯插入 / +3/-74 纯替换 / +19/-74 两步语义滑）、零编辑经济学（读额 33%/预算 29%/满轮 22%）、噪音与动手率不负相关（修正旧信念）
- **拆步执行器（`--staged`）**：TODO-DAG 固定计划退化版——Planner=挖掘器模板（零 LLM 成本零幻觉）、Editor 一次一动作（步1只插入→阶段间静态检查→步2只替换）、Reviewer=既有 oracle 栈；假设与对照基线入库，待预算恢复做 A/B

### Agent — 自更新闭环（冻结前收官）

- **十六至二十五轮总账**：25 轮 92 次尝试、真候选 32、0 接受、基建零事故；第十六轮 4/4 全真候选零徘徊（反制栈将徘徊型全部转化）；守恒 v2 首战（整函数改写毫秒点名 46 行消失）；类内裸名调用诊断消歧（点名调用形式与两条出路——候选拿着"没定义它"的旧文案原样重蹈）；第二十三轮史上最接近候选（+8/-1，静态全过打进 pytest，败在 `return TritValue(0)` 被顺手"规整"成 `return None` 一行语义）
- **方法论教训入库**：隔天数据不能当对照组（第十九轮受控对比推翻前日排除结论）；断路归因两写（风暴或顽固徘徊）；CLI breaker 2→3（防误杀晚转化候选）

### Bug Fixes

- **Windows LLVM 链接欠账**：`llvmgen/build.py` 链接步补 `-lwinhttp`（runtime.c 的 WinHTTP 依赖——本机 llc 缺席使链接步从未被走到，FFI native 测试首次暴露）
- **LLVM 调用分派**：零参 FFI 调用 `(ping)` 曾被"单元素列表→变量引用"分支截胡——extern 钩子置于其前；内置算子（add/加 等）遮蔽同名 extern 已显式化并记 RFC 已知限制
- **pycparser 注释剥离**：`--no-preprocess` 路径自剥注释（保行号），pycparser 不吃注释

### Metrics

| 指标 | 值 |
| --- | --- |
| pytest（`tests/`） | 2643 passed / 0 failed / ~5 skipped（passed ±2 / skip 随 gcc 漂移，0 failed 为硬指标）|
| ruff check / format | 0 问题 / 326 文件已格式化 |
| mypy | 0 问题（245 源文件）|
| FFI 守护 | 55 枚（层 A 26 + 生成器 8 + ctypes 14 + LLVM 7），双后端一致性活体验证 |
| 实跑（0704–0708 累计） | 25 轮 92 次尝试；真候选 32，0 接受；失败库 92 条全量入库 |
| preflight --quick | ALL CHECKS PASSED 10/12（2 quick-skip）|

---

## [v3.55.0] — 2026-07-07

> **P3 收官周：单日七轮实跑（第九至十五轮）把死法阶梯从"零编辑徘徊"一路推进到"行为等价"——候选首次打进 pytest 层；S2 候选淘汰赛与 S4 考官域写保护双双落地。工具链自伤三连修（行号坐标缺失 / 散文管道劫持 / UR 累积误杀），守恒检查升级整文件行计数堵住"重复行不在场证明"，done 谎报被单笔顶回闸门接住。15 轮 52 次尝试 16 真候选 0 接受，判定同模型收益平台期——跑道机械面全部就位，换模型成为唯一明确大杠杆。**

### ⭐ Highlights

- **候选首进 pytest 层（第十三轮质变）**：done 闸门 + 补笔顶推逼出模型合理新策略『一笔整段 `replace_lines 308|401`』（一次调用同时完成定义+替换），两步齐做+净变短、静态四连闸全过——oracle#1 按失败用例名拒绝（改写破坏 `匹配3` 行为）。死法阶梯走完静态层，现役瓶颈收敛为**行为等价/只搬不改**
- **S2 候选淘汰赛落地（`run_tournament` + CLI `--candidates N`）**：一任务 N 候选串行赛——教训经 `classify_tip` 跨候选**去重累积**（比带记忆重试的"最多两课"完整，把抽签变爬山）、首个 accepted 即停、全败返回**信息量最大**的拒绝（失败用例 > 守恒/解析 > 粘贴/嵌套 > 未变短 > 无改动）、连续零编辑**断路止损**；两轮实跑赛制机械面全绿
- **S4 考官域写保护 + P5 密钥闸（红线①机械化）**：`PROTECTED_PATHS`（tests/、self_update.py、run_self_update.py、task_mining.py、preflight.py）在 commit 后、**oracle 之前**前缀拒绝——pytest oracle 防不住"把测试改成恒过"（循环论证）；diff **新增行**含 `SANYAN_API_KEY`/sk- 密钥样式即拒（上下文行不误伤）
- **工具链自伤三连修**：read_file 范围读**每行带绝对行号 `N│`**（顶推推荐 replace_lines 按行号而工具不给坐标还禁读——模型两次原话抱怨"没显示行号"，凭记忆猜 old 或散文空转烧光预算；old/new 混入行号前缀自动剥除）；**管道解析护栏**（散文引用旧调用"308|95"曾被 #2 层劈成幻影工具名——首段须像工具名才按管道劈）；**UR 退化检测只喂解析失败的输出**（累积 token 独特率对模板化工具调用单调衰减，第 4 条必破 0.5——首个全零超时窗口 4/4 正常探索被误杀，"行为越规矩死得越快"）
- **守恒检查 v2（整文件行计数）**：集合成员判定下重复行留一份副本即有"不在场证明"（`ternary_match` 内 `matched = False` ×3、conf 阶梯 ×4，压缩改写静态全过烧 pytest 才拒；**行为等价的改写更会被直接接受**）——纯搬运不改变任何一行出现次数，删任何一份重复立即亏空毫秒拒
- **三级递进反制读循环 + done 闸门 v2**：读满 5 次零改动即顶推（不等轮次/时间过半）→ 读额告罄警告写进读结果**头部**（带内——上下文顶推被无视，工具结果才是注意力最高位；零编辑下全部读类调用**共担**，换工具规避限额不再是出路）→ 单笔改动的 done **顶回一次点名缺笔**（模型凭信念 done 不凭状态：插完 done / 替换完幻觉 helper 已定义）

### Agent — 自更新闭环

- **`run_tournament(loop, task_name, edit_fn_factory, n, *, breaker, tip_fn, on_candidate)`**（self_update.py）：串行赛（代理是瓶颈，并行加剧限流）；CLI `--candidates N` 与 `--attempts` 互斥（parse 后立即拦）；CLI 侧 breaker=3（4 候选赛制里 2 连徘徊即断误杀后续候选——第十三轮晚转化候选 r13 才动手），库默认 2；断路归因两写（环境风暴**或**顽固徘徊——第十四轮实证干净窗口徘徊也连出零编辑）
- **考官域写保护先后序**：保护检查必须在 oracle 之前（守护钉"oracle 恒过也拦"）；放 commit 后复用 `_git('show')`，尸检钩子仍拿到完整 diff
- **read_file 行号坐标**（agent_tools.py）：范围读 `N│` 绝对行号；`_strip_lineno_prefixes` 剥除 old/new 中的抄入前缀（原文直接命中绝不剥，文件真实含 `N│` 内容不误伤）；replace_lines 的 new 无条件剥；工具输出/上下文注入上限 4000→4500 吸收行号开销
- **第二步顶推（不预设顺序）**：首笔改动落盘的下一轮立即点名两笔（①定义②替换）缺哪补哪——第十二轮实证模型会**先替换后定义**（done 时幻觉 helper 已定义，作用域检查毫秒点名）
- **UR 喂入契约**（loop.py / loop_policy.py）：只喂 `tool=None` 的散文/胡言（其 docstring 自述本职）；真工具调用打转由 `results_degenerate`（3 连同结果）+ 同工具限额守；重复胡言攒满 4 条照杀
- **管道解析护栏**（agent_llm_handler.py #2 层）：首段须为短单 token 无换行才按管道劈——#3/#4 层各有护栏唯独 #2 裸奔且抢在最前

### Bug Fixes

- **UR 累积误杀**：全历史 token 独特率对模板 JSON 单调衰减，干净窗口 + 干净解析 = 输出越整齐死得越早（被噪音/散文的多样性遮蔽九轮，窗口一干净现形）——检测器需要和被护对象一起被尸检
- **守恒"不在场证明"**：`ln not in new_lines` 集合判定 → `Counter` 整文件行计数，重复行删除立即现形
- **读额警告催生工具轮换**：read_file 警告教会模型换 analyze/search_code 继续读（还试了违禁 `run_shell python -c` 读文件）——零编辑下读类调用共担警告
- **断路器归因**："疑似代理风暴"断言改为"风暴或顽固徘徊"两写（第十四轮 6 次超时干净窗口，零编辑是徘徊不是风暴）

### Metrics

| 指标 | 值 |
| --- | --- |
| pytest（`tests/`） | 2578 passed / 0 failed / 6 skipped（passed ±2 / skip 4-6 随 gcc 漂移，0 failed 为硬指标）|
| ruff check / format | 0 问题 / 317 文件已格式化 |
| mypy | 0 问题（240 源文件）|
| 实跑（0704–0707 累计） | 15 轮 52 次尝试；真候选 16，0 接受；基建零事故（52 次回滚零残留、无自动合并、oracle 零误放行）|
| 守护测试净增（本版） | +25（行号/剥除/管道/UR/读循环/done 闸门/守恒 v2/淘汰赛/写保护）|
| preflight --quick | ALL CHECKS PASSED 10/12（2 quick-skip）|

---

## [v3.54.0] — 2026-07-06

> **P3 实跑迭代周：七轮 22 次尝试驱动"每类死因 → 毫秒拦截 + 点名病灶 + 对症纠偏"完整闭环。oracle 栈三重加固（作用域感知引用检查 / 守恒检查 / 病灶诊断），带记忆重试从盲目重跑进化为迭代修正（两课链 + 候选块指名），循环生存性批拆掉全部机械死因（预算/限额可调、哨兵快中止、停机如实、徘徊顶推）；模型逐轮逼近：不改 → 只做第一步 → 两步齐做（位置错），死法排列集齐唯缺"两步齐做+位置正确"。**

### ⭐ Highlights

- **oracle 栈三重加固（全部毫秒级、置组合首位短路）**：`引用可解析`重写为**作用域感知**（LEGB 链——类体绑定对方法内裸名不可见，0705 实跑"类方法裸名调用"盲区当场回敲）；新增**守恒检查**（纯搬运重构下原函数体每一行必须在新文件原样存活，消失行按名列出——0705 真候选"重写而非搬运"死因转毫秒）；未变短拒绝附**病灶诊断**（嵌套 def"须与原函数平级" / 大粘贴"文件净增超函数体量"）
- **带记忆重试**：`--attempts` 从 N 次冷启动进化为迭代修正——`classify_tip` 按拒绝原因分类对症提示（无改动/未定义/重写/嵌套/大粘贴/挂测试/未变短七类），候选块行区间随纠偏指名，**两课链**（最近一课 + 更早一课，防中间尝试换死因丢课）
- **循环生存性批**：总预算 `SANYAN_LOOP_TIME_BUDGET`（自更新 900s）与同工具限额 `SANYAN_TOOL_REPEAT_LIMIT`（自更新 10）环境可调——代理抖动时 420s/读 5 次曾把尝试掐死在编辑前；**LLM 哨兵转异常**（`error|…` 彻底失败串曾伪装成"工具"烧轮、还把 UR 退化检测毒成早夭）；**停机原因如实上报**（旧实现所有 break 谎报"已达N轮"，尸检被误导两回）
- **徘徊顶推**：REQUIRE_EDIT 下轮次或时间过半仍零改动，顶推一次"停止阅读、先定义后替换"——**顶推→编辑因果三次复现**（顶推后 2-3 轮内动手）
- **解析层三修**：整段思维链不再被当工具名（散文→None 走优雅重提示）；关键词启发式关进"短单行"笼子（中文推理必含"函数"，曾整段劫持成写死目标的 analyze）；**列表参数按行拼接**（模型把 `new` 给成 JSON 数组，旧实现 str() 出列表字面量当代码写入——一次完整两步替换编辑曾就此报废）
- **七轮实跑总账（0704–0706，22 次尝试）**：真候选 6 个全部毫秒拒 + 点名病灶；0704 烧整轮 pytest 才暴露的"引用未定义"死法，0706 同型重现时零成本点名；代理风暴五连（29/16/35/31/30 次超时）确立"环境噪音与产出严格负相关"，风暴下暂停实跑

### Agent — 自更新闭环

- **引用可解析作用域化（`_unresolved_calls_in_function` 重写）**：裸名解析链 = 目标函数局部（形参/Store/嵌套 def，含闭包外层）→ 模块层（def/class/import/Store，**不下潜类体**）→ builtins；函数内 `global X` 视同模块层绑定，except-as/match-as 等绑定形态收进 `_bound_names`；`from x import *` 仍放行。0705 第二轮真候选把辅助函数定义成**类方法**又裸名调用（必然 NameError），旧实现把全树 FunctionDef 一律计入可解析恰好放行自己瞄准的 bug 类——靠 pytest 才拒；现在毫秒毙
- **守恒检查（`make_shrink_oracle(baseline_source=)`）**：基线函数体行（跳 def/装饰器/docstring/注释，strip 归一缩进不计，≥8 字符含字母数字）每一行必须在新文件原样存活；消失行进拒绝理由与 `report.missing_lines` 直接喂纠偏。0705 真候选改校验条件（`len(args)%2!=0` 拒奇数参而合法匹配3恰是奇数参）、换异常类型（`SanyanSyntaxError`→`ValueError`），烧整轮 pytest 才被拒——这类"重写而非搬运"现在毫秒判
- **病灶诊断二连**：未变短且基线无嵌套时点名"辅助函数嵌套在目标函数内部——须定义在与原函数平级处"（0706 第五轮尝试 1：两步齐做但嵌套，94→99 反而变长）；未变短且文件净增超目标函数体量时点名"疑似整段重复粘贴"（0706 第七轮尝试 3：+390/-0，风暴下输出质量崩坏的新形态——"两步都做完"的药方对它不对症）
- **带记忆重试（`build_retry_feedback` / `classify_tip`）**：上次拒绝原因 + 分类纠偏塞回下一轮任务书首；`hints` 带挖掘静态标注的候选块行区间；`earlier_tip` 两课链——0706 第五轮实录：尝试 1 教训"两步都做完"被尝试 2"无改动"顶掉、尝试 3 重蹈只做第一步，单课链在中间尝试换死因时丢课
- **徘徊顶推（loop.py）**：轮次过半**或时间过半**（代理风暴下固定轮数常来不及——预算先烧完）仍零改动，一次性顶推；文案点明顺序**先插入辅助函数定义（平级）、后替换原块**（被顶推后模型的自然反应是先替换——引用不存在的名字）
- **runbook 增补**："只搬不改（外部逐行核对）"、"辅助函数与原函数平级、不要嵌套"、"先定义后替换"、"不要用 run_shell/sed 读文件"
- **挖掘去截断（`mine_long_functions` 默认 `limit=None`）**：旧默认 30 只返回最长前 30——新增代码把别的函数喂长，`ternary_match` 跌出榜被 `--pick` 判"未命中"（任务身份随无关改动漂移）；展示层自切
- **哨兵转异常 + 停机如实**：`error|LLM调用失败…` 彻底失败串在 loop 转 RuntimeError 走既有失败路径（计连败、三次快中止、不进 `llm_outputs`/history）——曾变幻影"工具"烧轮、重复错误文案把 UR 退化检测毒成 r5-6 早夭；`run_legacy` 各 break 点落真实停机原因（预算/单步超时/UR 退化/连败/约束/门阻断），不再一律谎报"已达N轮"

### 引擎 — 三态认知

- **hesitation 连续计数（`core/ternary_engine.py`）**：`step()` 里笃定一步（AFFIRM/NEGATE）复位犹豫计数——`agent_execution` 早写着"连续N次不确定，停止执行"，但计数器从不复位实为累计，健康长环被非连续 UNCERT 攒够误停；连续 UNCERT 仍照常触顶

### Bug Fixes

- **列表参数泄漏（`_flat_arg`）**：dict-args 摊平遇列表值按行拼接（`replace_lines` 的 `new` / `write_file` 的 `content`），不再 str() 出 `['def _f(…` 列表字面量——0706 第五轮一次完整的两步替换编辑被它毁掉（守卫按语法错误拦回）
- **思维链漏成工具名**：`parse_tool` 兜底从不返 None 使 loop 的优雅重提示成死代码——多词散文/大段推理现在返 None 走重提示；单 token 仍原样返回（"未知工具"是有效反馈）
- **关键词启发式劫持**：`def/函数/结构→analyze` 原对任意文本生效，超时后的中文思维链被整段劫持成写死目标的 analyze 白烧一轮——只对短单行生效
- **learned_styles 路径**：`agent_learning_handler` 两处 `__file__` 锚定换成 `paths.data_dir()`（认 `AGENT_DATA_DIR`，默认不变）——测试跑不再污染真 tracked 文件

### Metrics

| 指标 | 值 |
| --- | --- |
| pytest（`tests/`） | 2554 passed / 0 failed / 4 skipped（passed ±2 / skip 4-6 随 gcc 漂移，0 failed 为硬指标）|
| ruff check / format | 0 问题 / 317 文件已格式化 |
| mypy | 0 问题（240 源文件）|
| 实跑（0704–0706） | 7 轮 22 次尝试；真候选 6 个，全部毫秒级拒绝 + 点名病灶 |
| preflight --quick | ALL CHECKS PASSED 10/12（2 quick-skip）|

---

## [v3.53.0] — 2026-07-04

> **P3 循环内生存性：新落地的尸检可观测链首战即揪出"零改动伪装成真 diff"的元凶（agent 学习记录污染），据此收紧三道闸门——副产物不进提交、改动记录只认成功、零改动 done 顶回；另修 Kleene 置信度无条件衰减（纯成功链也塌到 0.01）与弱模型三连废的三个根因；preflight 自 v3.50 目录重构后首次全绿。**

### ⭐ Highlights

- **preflight 复活（自 v3.50 目录重构后首次全绿）**：重构把 `preflight.py` 迁进 `scripts/`、`test_self_host.py` 直跑，两处 script-mode `sys.path` 断裂（`ModuleNotFoundError: compiler`），叠加 170 个 `.py` 工作树 CRLF——两处锚定仓库根 + `core.autocrlf input` 归一 → `ALL CHECKS PASSED`
- **尸检可观测链**：拒绝理由带失败用例名（分支随回滚蒸发后仍知挂在哪）+ `reject_hook` 回滚**前**把被拒 diff/stat 落 agent 日志（尸检窗口）+ agent 子进程 `-u` 无缓冲（超时树杀不再吞掉整段日志）
- **尸检首战战果**：首个自动落盘的被拒 diff 当场揭穿——某次"未变短"拒绝的 diff 里只有一条 `learned_styles.md` 学习记录，**根本没改码**；同一污染还混进了昨日被接受的分支
- **循环内生存性批（A/B/⑥）**：副产物排除（学习记录/状态库 `reset` 出暂存区，只剩副产物即判无改动）+ 改动只认成功（`cog=='AFFIRM'` 才记 `modified`，失败替换不再谎报"修改文件"）+ 零改动 `done` 顶回（`SANYAN_REQUIRE_EDIT` 下至多顶两次，逼向真编辑而非 `run_shell` 空转数行）
- **置信度回血（⑦）**：Kleene 传播旧行为无条件乘性衰减——纯成功链也 0.81→0.66→…→0.01、失败毒化只降不升 → 成功用几何均值回血、高置信稳态不再误判"信息增益不足"逼人工介入
- **三连废三根因**：模型顽固发 `{"command":...}`（`run_shell` 收编同义键 + 键名全不认时按序拼值兜底，不再整包 JSON dump 当 shell 命令必败）；`-u` 无缓冲留现场；CLI 直调 `main()` 遗留 `SANYAN_SKIP_RULE_GEN` 污染同进程后续测试（autouse 夹具还原）

### Agent — 自更新闭环

- **尸检可观测链（P3 补件）**：上轮缺口是"某次过了 shrink oracle、只差 1 个测试挂掉，却既不知改成啥样、也不知挂的哪个测试"。三处补齐——`make_pytest_oracle` 从短摘要区提取 `FAILED/ERROR` 用例名（封顶 3 个）进拒绝理由与 `report.failed_names`；`SelfUpdateLoop(reject_hook=)` 每次拒绝在回滚**前**以 `(worktree, 原因)` 调用、异常被吞（观测绝不阻断回滚，红线内只读缝）；`make_reject_diff_dumper` 把被拒提交 `patch+stat` 追加进 agent 日志（patch 在前、stat 收尾，日志尾正好是改动概要）
- **副产物排除（A）**：`SelfUpdateLoop(commit_excludes=)`——`git add -A` 后把 `learned_styles.md` / `agent*.db` 等运行副产物 `reset` 出暂存区。写进提交会伪装零改动、污染产出分支（今晨尸检 + 昨日被接受分支双重实证）；排除后只剩副产物即视同零改动拒绝
- **改动只认成功（B）**：`loop.py` 记 `memory['modified']` 加 `cog=='AFFIRM'` 门。失败替换（未找到/语法错误被守卫还原 → UNCERT）不再伪装成"修改文件"——否则面板谎报、学习器记假风格、⑥ 的零改动顶回也被这条假记录骗过（实录：`r5 replace_in_file` 判 UNCERT 0.10，面板却写"修改文件: ops/control_ops.py"）
- **零改动 done 顶回（⑥）**：`SANYAN_REQUIRE_EDIT` 下零改动 `done` 顶回循环（至多两次），点名"去改文件、别 `run_shell` 数行数"；通用兜底（无此开关，非编辑任务）行为不变。CLI 置此开关并在任务书补"不要数行数/量长度，外部会验证与度量"指引——直击弱模型三连废里"空转数行到超时"的实录
- **三连废根因修复**：三次尝试一致发 `{"command":...}`，映射只认 `cmd` → `args` 整包 JSON dump 当 shell 命令必败 → NEGATE 连锁毒化置信度 → UR 处决/超时。`run_shell` 收编 `command` 同义键；键名全不在序里时按模型给出顺序拼值兜底

### 引擎 — 三态认知

- **置信度回血（⑦，`core/ternary_engine.py`）**：`propagate_confidence` 新增 `current_trit`——本步成功（AFFIRM）用几何均值向当前步收敛，健康长链稳在高位；失败/不确定（默认）仍乘性衰减，偶发成功不勾销既有失败信号（默认参数保持旧两参调用语义 `0.9,0.8→0.72` 不变）。`protect` 的"信息增益不足"阻断加 `confidence<0.6` 守卫：高置信稳态是健康收敛、不该逼人工介入，真停滞是低置信原地打转。旧无条件衰减的两处恶果——晚到的 NEGATE 因低置信落进"可重试"而非"停止"（NEGATE 门形同虚设）、长成功链撞上"信息增益不足"误判——一并消除

### Bug Fixes

- **preflight 两处 script-mode 断裂**：`scripts/preflight.py` 进程内 import 仓库包（`bin_consistency` 等）、`tests/test_self_host.py` 直跑 `python tests/...` 时仓库根不在 `sys.path[0]` → `ModuleNotFoundError: compiler`。两处显式锚定仓库根
- **工作树 CRLF 漂移**：170 个 tracked `.py` 工作树为 CRLF、index 为 LF（`core.autocrlf` 曾为 `true`）→ 编码检查红、幽灵 `M` 状态。归一为 LF + `core.autocrlf input` + `.gitattributes * text=auto`
- **测试污染（预存炸弹）**：CLI 测试直调 `rsu.main()` 遗留 `os.environ['SANYAN_SKIP_RULE_GEN']='1'` 给同进程后续测试，`test_loop` 规则生成用例被静默关闭（全量按字母序侥幸不炸，换序/并行即炸）→ autouse 夹具显式存还
- **agent 日志被超时树杀吞没**：满缓冲 stdout 在进程树被 `taskkill /T` 时整体蒸发（实测 600s 只剩启动头）→ agent 子进程 `-u` 无缓冲，日志随跑随落

### Metrics

| 指标 | 值 |
| --- | --- |
| pytest（`tests/`） | 2514 passed / 0 failed / 6 skipped（gcc 环境性）|
| ruff check / format | 0 问题 / 317 文件已格式化 |
| mypy | 0 问题（240 源文件）|
| 自举字节一致 | B == C 7894 B（SHA256 `f0d17234…`）|
| preflight --quick | ALL CHECKS PASSED 10/12（2 quick-skip）|

---

## [v3.52.0] — 2026-07-03

> **P2 真 LLM 首跑闭环成功：12 轮探针连环挖出 10 个真 bug（每个都藏在上一个后面），产出首个 oracle 全过分支，安全机制全程零事故；P3 开工——任务感知 shrink oracle、--attempts 重试、面向弱模型的底层优化批。**

### ⭐ Highlights

- **P2 真 LLM 首跑闭环**：真实弱模型驱动的自更新全链路跑通，产出首个 oracle 全过分支 `self-update/custom-20260703-183546`（pytest 基线 2469/0 AND 差分 5/5，待人工审查）；探针全程每次失败干净回滚、零残留 worktree/分支、绝无自动合并
- **主 LLM 通路自 Phase 4 合并起就是断的**：LLMHandler/ModelRouter 缺 `complete()`，全假件单测掩盖 seam 断裂——首跑第一锹挖出
- **`环境变量()` 根修（语言 bug，安全根因）**：sugar 解析器保留字符串引号、`op_getenv` 生取带引号名字 → 永取空；当年的密钥注入反模式正是给这个语言 bug 打的补丁，根修后补丁动机彻底消失
- **回滚吊死修复**：agent 的孤儿 pytest 锁住 worktree、git 无超时 → 闭环吊死 30+ 分钟——超时杀整棵进程树（Windows `taskkill /T` / POSIX killpg）+ git 全操作 120s 超时按失败返回
- **P3 任务感知 oracle**：通用 oracle 只判"不退化"、判不了"有改进"（首个全过分支实为半成品重构：辅助函数未被调用、目标函数 94→~125 行反而变长）→ `make_shrink_oracle` 静态判"目标函数必须真变短"，毫秒级、置组合首位短路
- **P3 底层优化批（六项）**：语法守卫自还原 / "未找到"附最接近原文 / `replace_lines` 行区间编辑 / 任务书附静态分解计划 / 三态信封判定收编 / 规则生成前奏跳过——弱模型编辑摩擦系统性降低

### Agent — 自更新闭环

- **P2 首跑里程碑**：`run_self_update.py` 全链路（挖任务 → 真 agent 在 worktree 副本改码 → oracle 门 → 产出分支）在真实 LLM 下首次闭环；产物为"行为不变、测试全绿"的半成品重构 → 诚实判定不合并，暴露的 oracle 缺口当日转化为 P3 第一块
- **P3 第一块 `make_shrink_oracle`**：long_function 任务验收补上"有改进"维度——重构后目标函数 ast span 必须 < 基线；文件不可解析 / 目标函数消失（任务书要求保留原名）一律 fail-closed 拒绝；零成本静态检查置组合首位短路，半成品不再烧 70s 全量 pytest。实战首秀即立功：agent 改出语法错，oracle#0 毫秒级拒绝
- **P3 第二块 CLI 可观测/重试**：`--pick` 按子串挑任务（序号随代码漂移、子串稳定）；`--attempts N` 顺序重试摊薄弱模型单次成功方差（首个过 oracle 即停）；agent 全程输出落临时日志文件（追加写、回滚不灭），每次拒绝自动打印日志尾——P2 排障期"输出只在 rc≠0 可见"逼出一打盲探针的盲区永久封堵
- **P3 底层优化批（六项，面向弱模型的编辑摩擦）**：
  - **语法守卫自还原**：`.py` 写入后 ast.parse 验证，语法错误自动还原原文（新文件则删除）并回带行号错误信息——"改坏文件"从整轮报销降级为循环内可恢复的一步
  - **"未找到"附最接近原文**：`replace_in_file` 的 old 未命中时用 difflib 附上文件中最接近的片段——抄错一个空格不再盲试
  - **新工具 `replace_lines(path|起始行|结束行|新文本)`**：按行号整段替换，绕开"逐字抄写旧文本"的高摩擦动作（模型本来就以行号思考）；`_TOOL_ARG_ORDER` 按工具定义 dict 参数的拍平顺序（通用键序会错排 replace_lines 参数）
  - **任务书附静态分解计划**：挖掘 long_function 时静态列出函数体直接子块（If/For/While/Try/With ≥8 行）为"可优先提取的候选块 L326-399（循环块，74行）"——把"自己找结构"降维成"按方案执行"
  - **三态信封判定收编**：守卫还原/行区间无效/未找到 → UNCERT（可恢复失误不断轮）；`replace_lines` 成功消息 AFFIRM
  - **规则生成前奏跳过**：自更新场景 `SANYAN_SKIP_RULE_GEN=1` 省 2-4 次 LLM 调用与分钟级延迟（其垃圾参数产物本就被零改动闸门丢弃）
- **三连拒实录与瓶颈判定**写入 REFACTOR_PLAN：改坏语法→毫秒拒 / 超时→杀树净回滚 / 读两轮即弃→无改动拒——基建全部按设计工作，瓶颈收敛为**模型能力**（94 行重构任务有效产出率 ~1/5）；曾经过旧 oracle 的半成品现在会被正确拒绝

### Bug Fixes（P2 首跑 12 轮探针连环挖出，各带回归测试逐一提交）

- **run_agent.py 直跑即崩**：目录重构遗留——直接执行时仓库根不在 sys.path，`ModuleNotFoundError`
- **LLM seam 断裂**：LLMHandler/ModelRouter 自 Phase 4 合并起缺 `complete()`，主 LLM 通路死、全假件测试无人察觉 → 补齐 + `@runtime_checkable` LLMProvider 协议一致性测试
- **llm_call 重试吞错**：3 次重试全失败只回"LLM调用失败"不带原因 → 保留末次异常入错误串 + 逐次打印
- **`环境变量()` 永取空**：sugar 带引号字面量被生取 → `环境变量("SANYAN_API_KEY")` 取空 → 占位符 `sk-你的key` 一路走进 Authorization 头（latin-1 UnicodeEncodeError）→ `ops/system_ops.py` 引号字面量走求值器剥引号 + 配置层占位符过滤
- **回滚吊死**：subprocess 超时只杀直接子进程，agent 起的 pytest 沦为孤儿锁住 worktree 文件、`git worktree remove` 无超时吊死 → `_run_reaped` 超时先杀整棵进程树再收管道 + `_git` 120s 超时（fail-closed）
- **生成规则劫持整轮**：LLM 生成的垃圾参数规则（模板占位符原文入库）执行零修改却 done 谎报完成 → 零改动闸门：规则执行无实际修改则回退真 LLM 多轮循环
- **UR 双重误杀**：结果退化判定 2 轮太敏感 → 3 轮；`llm_output_ur` 阈值 0.85 → 0.5——结构化工具调用 JSON 的相似是推进不是退化
- **read_file 范围空切片**：「起始行|行数」被当「结束行」，`308|100` 切出 `[307:100]`＝永远的空——模型每轮读到虚空原地打转 → 双语义（第三段 < 起始行按行数解释）+ 超界给可诊断信息而非静默空串
- **三态全文嗅探禁读**：读回的代码含 error/失败 字样（错误处理代码的常态）被判高置信 NEGATE 断轮——agent 被禁止阅读一切含错误处理的代码 → 读类工具只判错误信封（前缀区），不嗅探内容负载
- **上下文喂养不足**：每轮只喂「上一步结果[:800]」，任务与历史全丢、弱模型必然打转 → 每轮重申任务 + 近 3 步历史 + 阶段推进提示（读满两轮零改动即明示"进入修改阶段"）+ 4000 字符结果窗
- **execute_rule dict 参数崩进程**：LLM 生成步骤的 args 为 dict 时直接 TypeError → 拍平防御
- **编辑动作落地三调参**：max_tokens 4096 截断整函数级 replace 的 JSON → 8192；parse_tool 缺 `cmd` 键致 run_shell 全废 → 补键；内部 300s 预算不够慢代理 → 420s

### Metrics

| 指标 | 数值 |
|------|------|
| Tests | 2489 passed / 0 failed（全量；14 skipped 为 gcc 不在 PATH 的环境性浮动） |
| Self-hosting | B == C, 7894 bytes |
| Ruff | 0 |
| Mypy | 0 |

---

## [v3.51.0] — 2026-07-02

> **自更新闭环 P2 就绪：自造任务 + 真 agent 编辑 + 差分 oracle；差分上线当天抓到真 parser bug 并当日闭环修复；被合并中间快照回退的安全/经验回路修复批量复原。**

### ⭐ Highlights

- **P2 落地**：`task_mining.py` 自造任务 + `make_agent_edit_fn` 真 agent 编辑 + `run_self_update.py` CLI，oracle = pytest 基线 AND 差分一致
- **差分 oracle 首日见效**：DifferentialVerifier 假绿修复当天即抓到多语句 .san 两引擎执行分歧，`core/parser.py` 当日闭环修复
- **安全回归复删**：密钥注入反模式（密钥写入 .san 源码文本）随合并快照复活 → 复删，密钥全程走环境变量
- **seam 修复批量复原**：并库 / LearningHandler / 双计数 / typed config / 路径统一 5 组修复连同 20 个测试守护回归 main

---

### Agent

- **P2 落地**：`task_mining.py` 自造任务（failing_test / TODO / 超长函数，按可验证性排序）+ `make_agent_edit_fn`（真 agent 子进程跑在 worktree 副本里）+ `run_self_update.py` CLI（oracle = pytest 基线 AND 差分一致性）
- **DifferentialVerifier 假绿修复**：真差分（`--eval` 求值器 vs 默认字节码 VM）、fail-closed（全崩=0% 而非 100%）、代码走临时 .san 文件、输出归一化；修好当天即抓到**多语句 .san 两引擎执行分歧**（VM 只编译第一个顶层表达式，eval 行为不稳）→ **当日闭环修复**（见 Bug Fixes 的 `core/parser.py` 条），差分用例增至 5/5 作回归守护

### Project Layout

- 根目录清理：删除孤儿 `agent_state.db`（活库为 `agent_system/agent_state.db`）、`_test_simple.bin`、两份 VM trace 日志、空 `dist/` 及 `publish/` 下遗留构建产物（均验证零引用后删除）

### Bug Fixes

- 重构丢失的未提交模块已恢复：`agent_system/paths.py`（修复 `store.py` 断裂的 import）、`tests/conftest.py`（AGENT_DATA_DIR 测试隔离 + `test_deadloop.py` 退出 pytest 收集）及 `test_paths/test_store`；阶段 5 雏形 `config.py` 起初因 main 上无消费者暂缓，后在下方 seam 复原④中连同接线一并恢复
- `core/runtime.py` BUILTIN_OPS：迁入 `core/` 后按 `core/language/` 找词表、静默得到空集 → 改锚定仓库根，259 词恢复
- `core/skin.py`：皮肤文件路径由 CWD 相对改为锚定仓库根，子目录入口/任意 CWD 均可加载
- `run_agent.py`：import 时 chdir 目标仍是旧的"文件所在目录=根"语义，迁入 `agent_system/` 后劫持整个进程 CWD、自身根相对路径全失效（agent CLI 起不来，亦即 test_deadloop 皮肤报错的直接原因）→ chdir 改锚仓库根
- **多语句 .san 静默丢语句**（差分验证器抓到的引擎分歧）：`core/parser.py` 的 `parse()` 只解析**第一个**顶层形式（REPL 单表达式语义），而 `compile_bytecode.compile_source` 的 S-表达式分支和 `repl/main._parse_file` 的回退分支都误用它——第一条语句之后全部静默丢弃，且 eval 的"时好时坏"实为 sugar 解析器成败决定走哪条路。新增 `parse_program()`（解析全部顶层形式），两个文件级入口改用；探针复核三组多语句用例两引擎归一化后完全一致（VM bin 7→16 字节）
- **密钥注入反模式复活（安全）**：阶段 5 曾删除的 `run_agent.py` 两处 `src.replace('sk-你的key', api_key)`（把真实密钥写进 `.san` 源码文本，另有密钥长度日志）随合并中间快照回退复活 → 复删。密钥全程走环境变量（主/子 Agent 路径均已 `setenv`，`agent_policy.san` 侧 `环境变量("SANYAN_API_KEY")` 优先读取），删注入零行为变化、密钥不再落源码串/日志
- **合并中间快照回退的 seam 修复批量复原**（以 agent-refactor-seams 分支为源、含测试守护）：① 阶段 2 并库——ExperienceStore/DomainKnowledgeLayer 默认库复归单一 `agent.db`（`store.adopt_legacy` 首开非破坏搬入旧独立库数据、旧库保留可回滚），`tests/test_store.py` 复原为 5 测（含两端到端并库）；② LearningHandler 捕获陷阱——构造期捕获的 memory 被 `run()` 每次重绑甩开，收尾 `save_experience` 读到**过期空字典**、经验保存静默失效（`try/except` 吞错不报），且 `learn_from_task` 单参签名对上 runtime 的双参调用是潜伏 TypeError → 三方法改按次收 memory、runtime 构造与调用点对齐；③ 双计数——`record_outcome` 不再记 tool_use（唯一记录源 = `save_experience`），`tests/test_learning_store.py` 复原（7 测）；④ 阶段 5 typed config——`config.py` 复原并真正接线：`load_api_key` 环境读取与 `LLMHandler._get_config` 环境回退统一走 `AgentConfig.from_env()`（新认 `SANYAN_MODEL/SANYAN_PROVIDER/SANYAN_MODEL_URL`，保留 `LLM_*` 兼容、占位符视空），`tests/test_config.py` 复原（8 测）；⑤ 阶段 2 路径统一——其余 10 个模块 14 处硬编码 `DB_PATH` 复归 `paths.db_path()`（`AGENT_DATA_DIR` 对全部持久化一致生效、测试密封完整；根目录/`agent_system/` 目录分裂入口清零）
- **任务挖掘假阳性**：`--list` 首跑发现 TODO 挖掘的 11 条命中**全部**是字符串字面量里的待办标记（测试骨架模板 `'''# TODO: 实现测试'''`、提示词示例、test_task_mining 自身夹具串）→ `.py` 改经 `tokenize` 只认真注释 token（其他扩展名保留逐行正则），加回归测试；修后仓库真 TODO 注释为零，任务源实际以 failing_test / long_function 为主
- **httpbin 外网测试守卫**：`test_http_post_compiles` 未接超时且仅识别 503，非 503 异常响应曾把全量 CI 打红一次 → 与 `test_http_json_roundtrip` 同策略，服务响应异常一律 skip（编译/链接失败不经此路、仍硬失败）

### Metrics

| 指标 | 数值 |
|------|------|
| Tests | 2453 passed / 0 failed（全量） |
| Self-hosting | B == C, 7894 bytes |
| Ruff | 0 |
| Mypy | 0 |

---

## [v3.50.0] — 2026-07-01 🏁 Milestone

> **闭包正式支持、编译器 Fixpoint 达成、Agent Phase 4 完成、项目目录全面重整。**

### ⭐ Highlights

- **Closure 正式支持**：嵌套函数可捕获外部变量，支持计数器闭包和独立实例
- **Bytecode Compiler Fixpoint**：自编译 B == C，7894 bytes
- **Agent Phase 4 完成**：LLM seam 单漏斗 + ToolResult 结构化 + LazyRegistry 懒加载
- **项目目录全面重整**：根目录 49→0 个 .py 文件，全部分类入 `core/` `compiler/` `vm/` `repl/`

---

### Language

- 闭包（Closure）：嵌套函数可访问外部变量，`outer(10)(5) → 15`
- 计数器闭包：闭包可修改捕获变量，多实例互不影响
- 无捕获函数 / lambda 自动推入变量表，支持一等值传递

### Compiler

- **Fixpoint**：`bytecode_compiler.bin` 自编译 B == C，7894 bytes
- 支持多 body 编译和 no-else 分支

### VM

- 新增 `CLOSURE (0x4B)` / `CALL_CLOSURE (0x4C)` 操作码
- `PUSH_STR` 转义简化：仅处理 `\uXXXX`，避免破坏 Windows 文件路径
- `SLICE` 类型启发式、`from_bin` 后显式 `run()`

### Agent

- **Phase 4 完成**：LLM seam 单漏斗 `llm_provider.complete`
- `ToolResult` / `ToolStatus` 结构化工具返回，消灭 string sniff
- `LazyRegistry` 懒加载 13 个子系统，`__getattr__` 路由
- `loop_policy.py`：停止条件纯函数；`contracts.py`：LLMProvider 协议接口
- **自更新闭环 P1** `self_update.py`：git worktree 隔离改副本 + fail-closed pytest 基线 oracle，只产出分支、**绝不自动合并**（7 单测 + 真仓 E2E 验证）
- `loop.py`：176 行主循环从 `agent_runtime.py` 迁出（1115→969 行），假 runtime 即可独立测试
- 北极星路线图 P0–P5（自迭代 agent）写入 `agent_system/REFACTOR_PLAN.md`，含 oracle 防作弊 / worktree 隔离两条红线

### Project Layout

- 所有根级 .py → `core/` `compiler/` `vm/` `repl/` `lsp/` `agent_system/` `examples/`
- 658 处 import 自动更新，入口脚本 `sys.path` 修正
- `pyproject.toml` 同步 packages / mypy exclude / coverage 配置

### Toolchain

- `_parse_with_sugar_san` VM 失败时回退 Python SugarConverter

### Bug Fixes

- 数字字面量优化：单字符 `0` 不再因长度限制被误编为 `PUSH_STR`
- Try/catch 索引：编译器正确跳过 sugar parser 的 `'捕获'` 关键词
- `preprocess_includes` 路径：`_base_dir` 改为 `os.getcwd()`，确保 `#include` 在子目录入口正确解析
- `LLVM` 内置常量：补全 `无`/`null`/`None` → 0 映射
- `LearningHandler` 参数：补 `memory` 参数
- `agent_strategy.py`：补 `import os`
- `test_lsp.py`：更新 `lsp_server.py` 路径

### Metrics

| 指标 | 数值 |
|------|------|
| Tests | 2457 passed / 0 failed |
| Self-hosting | B == C, 7894 bytes |
| Ruff | 0 |
| Mypy | 0 |

---

## [v3.49.0] — 2026-06-29

> **REPL 增强 + Web IDE + 测试覆盖率提升。**

### ⭐ Highlights

- REPL `:help` / `:types` 命令补全
- Web IDE 文件管理，保存/加载 .san/.txt
- 12 项新功能测试覆盖模式匹配、异步语法、宏系统、类型推断

---

### Language

- 宏定义修复

### Toolchain

- Web IDE 增强：更多示例和工具栏完善
- 快速入门指南 `docs/quickstart.md`

### Metrics

| 指标 | 数值 |
|------|------|
| Tests | 397 |

---

## [v3.47.0] — 2026-06-28

> **字节码编译器增强——编译错误信息带源码位置。**

### ⭐ Highlights

- S-表达式解析错误显示 `第X行第Y列`
- 字节码优化：Fibonacci 22 条指令，无明显冗余
- 闭包捕获框架识别（VM 和编译器双层修改待后续版本）

---

### Compiler

- 编译错误信息带源码位置，修复 sugar_error 传递和 parse 源码参数

### Metrics

| 指标 | 数值 |
|------|------|
| Core tests | 230 |

---

## [v3.46.0] — 2026-06-28

> **包管理器生态 + 标准库加固 + 求值器优化。**

### ⭐ Highlights

- 新增 5 个包（template / http_client / json_utils / datetime_utils / string_utils），包总数 6 → 11
- 求值器性能提升 40%（fibonacci 25: 10.8s → 6.46s）
- 数学库/文件系统/测试框架全面加固

---

### Language

- 中文函数名引用、嵌套闭包、递归闭包
- 中文操作别名：`转数字`/`转字符串`

### Build

- 包开发指南 `docs/package_development.md`
- 数学库：矩阵行列式、伴随矩阵、矩阵求逆、向量叉积、向量距离
- 测试框架：setUp/tearDown、跳过测试、异常捕获
- 文件系统：路径处理（目录/文件名/扩展名/合并/绝对化）、文件信息（行数/首行/末行/搜索/替换）

### Evaluator

- TritValue 缓存：常用整数（-100 到 100）
- 数值解析缓存：`parse_numeric_literal` / `_is_numeric_string`
- 类型检查优化：`type()` 替代 `isinstance()`（对原生类型）

### Metrics

| 指标 | 数值 |
|------|------|
| Core tests | 294 |

---

## [v3.45.0] — 2026-06-27

> **VM 内联优化 + 字节码编译器修复 + 求值器性能 + 边界修复。**

### ⭐ Highlights

- VM 热操作码内联，fibonacci(25) 0.9s → 0.78s（+13%）
- 字节码编译器 HALT 修复 + 双遍编译架构
- 求值器性能提升 38%（fibonacci(25) Python: 10.8s → 6.7s）

---

### VM

- 热操作码内联：ADD/SUB/MUL/MOD/DIV/LT/GT/EQ/NE/LTE/GTE/AND/OR/NOT/PRINT/PUSH_STR/CONCAT/LIST_LEN/STRLEN
- 栈操作缓存、代码长度预计算
- fizzbuzz(100) VM: 0.0012s（175x 加速）

### Compiler

- HALT 指令缺失修复——字节码末尾缺少 HALT
- 双遍编译架构：函数定义→HALT→主代码→HALT
- AST 分割：`过滤函数定义`/`过滤非定义`
- LIST_GET 符号修正

### Language

- 中文函数名引用、嵌套闭包、递归闭包、中文操作别名

### Package Manager

- `检查更新`、`更新("包名")`、`发布准备("包名")`

### Metrics

| 指标 | 数值 |
|------|------|
| Tests | Core 294 / VM 91 |
| fibonacci(25) VM | 0.78s |
| fibonacci(25) Python | 6.7s |

---

## [v3.44.0] — 2026-06-26

> **性能优化 + 类型系统 + 包管理 + 异步语法 + 模式匹配 + Web IDE + 宏系统。**

### ⭐ Highlights

- VM 指令分派 `dict.get()` → `list[opcode]` O(1) 索引
- 类型推断引擎 + 泛型容器 + 接口/协议
- 异步操作 + 模式匹配 + 宏系统 + Web IDE
- 955 项测试全部通过

---

### VM

- 指令分派表 `list[opcode]` O(1) 索引，内联 PUSH_I/LOAD/STORE/HALT

### Compiler

- 错误信息增强：`_format_error_with_context` 显示源码行 + 列指针 + 变量名建议（difflib）
- 测试碎片化整理：创建 `tests/test_edge_cases.py` 统一入口

### Language

- 类型推断 `type_inference.py`（int/float/str/list/dict/trit）
- 泛型容器 `列表<T>` `字典<K,V>` 类型匹配，嵌套泛型
- 接口/协议 `protocols.py`（可序列化/可迭代/可调用）
- 异步操作：`concurrent_ops.py` 异步定义/等待/并行块/完成/取消
- 模式匹配：`匹配` 操作，支持字面量/列表解构/字典解构/通配符/变量绑定
- 宏系统 `macro.py` + `ops/macro_ops.py`：5 个内置宏（守护/除非/当/重复/管道）
- Web IDE `web_ide.py`：浏览器内编辑器 + REPL + 深色主题

### Build

- 包管理器版本约束（semver）、日志库/模板库/数据库库
- REPL 添加 `:types` 命令

### Metrics

| 指标 | 数值 |
|------|------|
| Tests | 955（VM 91 + Core 138 + Ops 92 + OpsExt 64 + Edge 570） |

---

## [v3.43.0] — 2026-06-24

> **项目重构：UR 实验独立 + 目录整理 + Tokenizer 研究。**

### ⭐ Highlights

- UR 退化检测实验独立为新仓库 `github.com/shujingyin510/UR`
- Tokenizer-语言对齐实验：4 模型 × 71 关键词，Qwen avg 1.2 tk（GPT-2 的 1/4）
- Agent Token 用量显示 + 动态置信度

---

### Research

- **Tokenizer-DSL 对齐**：GPT-2 avg 4.3 tk vs Qwen avg 1.2 tk（80% 单 token）
- 跨语言对照：Python/Java/中文 DSL 三组关键词 token 开销
- 自然文本验证：34 段真实中文，GPT-2/Qwen = 3.0×
- 结论：语言效率 = 语言 × Tokenizer × 训练分布共同决定

### Project Layout

- 根目录整理：文档 → `docs/`，构建/检查脚本 → `scripts/`
- CRLF → LF（csrc/ 下 4 个文件）
- 版本号同步至 v3.43.0

### Agent

- Token 用量显示（从 API 响应读取实际值）
- 三态状态修复：`done` 工具正确记录为 AFFIRM
- 动态置信度：真 → +3~5%，拒绝 → -10%，不确定 → -2%（会话级缓存）

### CI

- mypy：`sanyan/tui.py:164` method-assign `# type: ignore`
- Agent benchmark：dry_run 快速路径 0.03s（原 21.80s）
- CRLF→LF：`agent_knowledge_confidence.py` / `agent_loop_monitor.py` 等
- ruff：`sanyan/cli_tui.py` 拆分多 import

---

## [v3.42.0] — 2026-06-19

> **三态引擎驱动 Agent + 多语言 QA + 200 条规则 + CI 全绿。**

### ⭐ Highlights

- 三态引擎升级：Kleene 传播 + 五态分类 + 保护门控 + 最终判定
- 200 条规则（72 → 200），15 种错误类型，76 种测试场景
- 多语言通用 QA 框架，13 种编程语言自动识别

---

### Agent

- 五态 classify：NEGATE / UNCERT / AFFIRM / CONFLICTED / PENDING
- 三态门控：高置信拒绝→跳过；连续不确定→停止；低置信→切换策略
- 非代码任务自动 LLM 直答（不限语言）
- 200 条规则库 + 11 个模板（数学/数据结构/算法/工具）
- 超时护杀（总 300s + 单步 60s）、LLM 连续 3 次失败→退出
- 本地模型支持（`LocalProvider` + `HF_HUB_OFFLINE`）

### Research

- UR 自适应闭环控制，avg UR=0.79（vs greedy 0.29）
- 双通道检测器：UR（词法）+ SBERT（语义）
- GPT-2 跨规模验证：124M/355M/774M

### CI

- ruff / mypy 全绿，pytest 1634 通过，preflight 12/12

### Metrics

| 指标 | 数值 |
|------|------|
| Tests | 1634 |
| Preflight | 12/12 |
| Ruff / Mypy | 0 |

---

## [v3.40.0] — 2026-06-18

> **Agent 架构重构 + 规则引擎 + 领域知识层。**

### ⭐ Highlights

- 规则引擎 `agent_rules.py`：5 条预置规则，数学任务 68s → 1.46s（LLM 8→0 次）
- 领域知识层 `agent_domain.py`：LLM 动态生成 + SQLite 缓存
- GitKnowledgeBridge：859 条 git 历史 + agent 执行记录

---

### Agent

- Few-shot 模板 + 阶段工具约束（探索只读 / 修改只写 / 验证只测）
- 计划进度注入 + 动态 system prompt
- `run_shell` / `_generate_code` / `_generate_test_code`

### Bug Fixes

- C VM NOT 操作：`非 0` 返回 1 → 0（`csrc/runtime.c`）
- `_detect_verify_loop`：文件不存在误检测修复
- `_llm_call`：配置加载 try/catch

---

## [v3.39.0] — 2026-06-17 🏁 Milestone

> **UR≈0.30 退化检测阈值 + 跨架构验证 + 文档重构。**

### ⭐ Highlights

- **UR≈0.30 退化检测阈值**：4 个模型、3 种架构、3 个数量级参数跨度上可靠区分退化
- 消融实验：UR-only = 完整轨迹检测，周期/功能词密度完全冗余
- 1000-prompt 基准：三元门控 98-100% 停止率 vs EOS-only 0%

---

### Research

- TinyStories 3.6M: 真阳性 98% / 28M: 100% / GPT-2 124M: 100% / Qwen2.5: FP 0.4%
- 人工盲评（100 prompt, 3 维度）：三元 79.7% vs EOS 8.3%
- 跨语言验证（中文）：Qwen2.5 avg UR=0.718，FP=2%，阈值语言无关
- 采样策略对比：nucleus 防退化 (UR=0.87)，rep_penalty 加剧坍缩 (UR=0.12)
- 人类文本 UR 基线：经典文学 avg UR=0.704（0% 低于 0.30）

### Models

- GPT-2 124M / Medium 355M / Large 774M + Qwen2.5-0.5B + GPT-Neo 125M
- 三言语言验证链路：.san → lexer → parser → evaluator → reg_op → ctypes → C DLL → GPT-2

### Documentation

- README / README_CN / RESULTS / QUICK_START / ROADMAP
- Known Boundaries 双语文档

### CI

- mypy: `csrc.*` ignore_errors + `csrc/__init__.py`
- coverage: `.coveragerc` 添加 `agent_system/*` omit

### Metrics

| 指标 | 数值 |
|------|------|
| Tests | 1650+ |
| Ruff / Mypy | 0 |

---

## [v3.38.0] — 2026-06-17 🏁 Milestone

> **SIMD 推理引擎 + 三态门控 + Transformer 全链路。**

### ⭐ Highlights

- AVX2 GEMM 内核：手写汇编 256×256 矩阵乘法，与 NumPy 逐位一致
- Transformer 全链路：QKV → 多头注意力 → 因果掩码 → FFN → 残差 → 输出 logits
- 真实模型推理：TinyStories-1M (3.6M) 和 TinyStories-28M

---

### VM / Inference

- KV Cache：32 token 从 1s → 0.1s（10x 加速）
- 三态门控推理：AFFIRM / MAYBE / NEGATE 三级决策，每条 NEGATE 带原因+数据

### Toolchain

- C 算子库：Softmax (e-09) / LayerNorm (e-07) / GELU (e-08)
- 三言调度集成：`reg_op` 注册 GEMM/Softmax/LayerNorm 为原生函数

### Metrics

| 指标 | 数值 |
|------|------|
| GEMM 256×256 | AVX2 0.51ms vs NumPy 0.15ms |
| 推理速度 | 3.6M: 4ms/token, 28M: 34ms/token |

---

## [v3.37.0] — 2026-06-16

> **统一 CLI + 安全基准 + 诚实度基准 + 语义逻辑层。**

### ⭐ Highlights

- 统一 CLI `sanyan` 命令入口（git/cargo 风格）
- Agent 安全基准 v2：49 种 bug 注入，检出率 98%（48/49）
- Agent 诚实度基准 v2：100 题 × 5 类，认知越界率 57.7% → 46.2%

---

### Agent

- `sanyan agent run/chat/evolve/dashboard/validate` + TUI 仪表盘
- 五层检测管道：ruff + self-host + logic_audit + semantic_diff + exec_trace
- Truth Calibration Engine（certain/calibrate/uncertain 三级）
- Logic Audit Engine（7 种检测器：反向逻辑/不可达代码/死分支/状态不一致等）
- Myth Shield（50 条误解字典）

### CI

- subprocess 编码统一 UTF-8
- mypy 152 错误清零（18 文件 Optional 批量修复）
- `pyproject.toml` 入口 + mypy 宽松模式

### Metrics

| 指标 | 数值 |
|------|------|
| Safety benchmark | 98% (48/49) |
| Honesty overconfidence | 57.7% → 46.2% |
| Mypy | 152 → 0 |

---

## [v3.36.0] — 2026-06-15

> **Agent 自主改代码闭环——LLM 补丁 + 强验证 + 行号校准。**

### ⭐ Highlights

- LLM 补丁生成：DeepSeek v4 上下文分析生成真实优化
- 行号校准：±20 行搜索匹配，解决 LLM 行号偏移
- 强验证管道：多后端一致性 + 自举验证 + pytest

---

### Agent

- 流式 LLM 调用 SSE + 死循环保护（连续 3 次失败自动跳过）
- 仿真验证：100 随机补丁，Reviewer F1=88%
- 实测闭环：3 轮 × LLM → 强验证 → 自动回滚/接受

| 对比 | v3.35 规则演化 | v3.36 LLM 闭环 |
|------|------|------|
| 补丁生成 | 固定规则 | LLM 上下文分析 |
| 行号定位 | 直接使用 | ±20 行搜索 |
| 验证强度 | `pytest test_agent.py` | 多后端 + 自举 + pytest |

### CI

- 路径修复：8 个文件 ROOT 修正
- mypy 152 错误清零

---

## [v3.35.0] — 2026-06-15

> **Agent 进化系统 + Knowledge Layer + Meta-Knowledge Transfer。**

### ⭐ Highlights

- 四层 Agent 进化架构：策略自优化 → 自主循环 → 约束进化 → 知识层
- 因果链闭环：Knowledge → Calibration → Selection → Success ✓（+43.6%）
- Meta-Knowledge：任务规律可迁移（+27.9%），配置不可迁移（-4.6%）

---

### Agent

- Layer 1：PromptEvolver / ToolSelectionLearner / StrategySwitcher / ABRollout
- Layer 2：自主循环 + 文件监控 + 健康监控 + 回滚验证
- Layer 3：ConstraintEvolver / DifferentialVerifier / SelfHostVerifier / PatchDSL / CandidateTournament
- Layer 4：TaskClassifier / ClusterLearning / KnowledgeConfidence / CausalChainExperiment
- Reviewer Agent（11 条规则，4 条对抗检测）
- CLI：`--evolve` / `--code-evolve` / `--validate` / `--metaconfig`

### CI

- mypy 152 错误清零 / ruff 11 处修复

---

## [v3.33.0] — 2026-06-15

> **Agent Phase 3/4 功能——并行执行 / 智能上下文 / 跨会话学习 / 安全沙箱。**

### ⭐ Highlights

- 并行执行引擎 `agent_parallel.py`（预计加速 2-4x）
- 智能上下文压缩 `agent_context.py`（Token 节省 ~40%）
- 跨会话学习 `agent_learning.py`（SQLite 持久化）

---

### Agent

- 安全沙箱 / 可观测性 / 流式响应 / 高阶工具组合
- 工具自发现 / 多 Agent 共享上下文 / Token 追踪
- CLI：`--sandbox` / `--stream` / `--pipeline` / `--dashboard`

---

## [v3.32.0] — 2026-06-14

> **Agent 自主闭环 + git 工具扩展 + post-commit hook。**

### ⭐ Highlights

- 自主循环脚本（提交 → 全量测试 → 自动 commit 或回退）
- git 工具注册：`git_stash` / `git_reset_hard` / `git_commit_auto`
- post-commit hook 自动触发验证

### Bug Fixes

- 33 个 .md 逐行审阅，修复 8 处过时内容

---

## [v3.31.0] — 2026-06-13

> **LLM 模型升级 + 工具调用 JSON 化 + 任务级经验库。**

### ⭐ Highlights

- 模型升级 `deepseek-chat` → `deepseek-v4-pro`（thinking + budget_tokens 2048）
- 工具调用 JSON 化：`{"tool":"...","args":{...}}`
- 任务级经验库：跨任务关键词匹配，失败 ≥2 次自动 AVOID

---

### Agent

- 结构化重试历史 / Toggle 检测 / 同位置连错检测 → escalate
- 系统提示词重构：身份锚定 + JSON 示例

### Bug Fixes

- `Hypothesis` 构造函数 `tools_used` 未传入 → 所有假设无工具执行
- `_execute_hypothesis` 每步调 LLM 获取参数
- API 密钥硬编码 → `环境变量(SANYAN_API_KEY)`

---

## [v3.30.0] — 2026-06-12 🏁 Milestone

> **效应类型系统 + 四后端差分模糊测试 + 自举 Level 2/3/4 + ISA v2。**

### ⭐ Highlights

- **自举 Level 2**：A→B→C 不动点验证 / **Level 3**：318 行 C 种子 VM / **Level 4**：617 行 x86_64 NASM
- **ISA v2**：LOAD16 / STORE16 / CALL32 / PUSH_STR16 / CLOSURE
- 效应类型系统 `确定[X]`/`不确定[X]` + 四后端差分模糊测试

---

### Compiler

- sanyanc 编译器 + 包管理 CLI（install/search/list/info/uninstall）
- 字节码编译器：负数识别修复、函数体编译修复

### VM

- 哈希字典 FNV-1a + 开放寻址 O(1)
- 汇编器 CLI / 反汇编器 / 字节码验证器

### Agent

- 多 Agent 协作 v0.4：调度子 Agent / Agent 消息 / 列出 Agent

### Bug Fixes

- C VM 编译 10 项修复 / LLVM 死循环修复 / Level 4 汇编安全加固 30+ 项
- 10 个已知 bug 清除

### Metrics

| 指标 | 数值 |
|------|------|
| Tests | 1650+ |
| Effect types | 30 tests |
| Diff fuzz | 12 tests |
| Self-host | 8 tests (Level 2 + 3) |

---

## [v3.29.0] — 2026-06-11

> **TritValue 歧义修复 + Ops 双语别名补全 + 测试全量覆盖。**

### ⭐ Highlights

- TritValue 歧义修复：int 列表必须全 ∈ {-1,0,1} 才视为 trit
- ops 双语别名补全（加/减/乘/除/余/幂/连接/取长/若/做/循环/遍历 等）
- 1251 项 Python 测试 + 46 项 .san 测试，核心模块 ≥ 90% 覆盖率

---

### Language

- `TritValue([1,2,3])` 不再被误判为平衡三进制数值

### Build

- `ternary_generic_ops.py` 694 行 → 3 模块
- system_prompt 缓存稳定化
- 数学函数覆盖 sin/cos/tan/sqrt/exp/log/log10（55 项）

---

## [v3.28.0] — 2026-06-11

> **并发融合 + 三态模式匹配 + 三态容器 + Web 框架 + 数据管线。**

### ⭐ Highlights

- 并发融合/竞速/全部操作
- 链式信度传播 `链` / `链断` / `解包` / `尝试链`
- 三态集/图/队列/栈 + 三态 Web 框架 + 数据管线
- 47 项新功能测试

---

### Language

- `并发融合(任务1, 任务2)` / `并发竞速(超时ms, ...)` / `并发全部(...)`
- `匹配3(值) { 真→... 可能→... 假→... }` / `匹配信度(值, 阈值)`
- 三态集/图/队列/栈 / 三态 Web 服务器 / 三态数据管线
- `共识(a, b, ...)` — 多传感器共识

### Bug Fixes

- `字列` → `字典键列表`：修复 bytecode_compiler.san 皮肤映射冲突（self-compile KeyError）
- stdlib/bytecode_compiler.bin 重编（6298B）
- stdlib/sugar.bin 重编（9839B）
- `data_pipeline_ops.py` `TernaryData.__str__` 字符串转换修复

---

## [v3.27.0] — 2026-06-07

> **TernaryEngine 独立模块 + 村庄三态追踪 + Agent V3 引擎重构。**

### ⭐ Highlights

- TernaryEngine 独立模块（131 行）：Kleene × 贝叶斯 × 保护门控
- Agent V3 引擎：`run_agent.py` 1485→1072 行（-28%），拆为 `agent_runtime.py` + `agent_tools.py`
- Plan Mode / Token Budget / Fail-Closed / Reflection / Constraints 完整闭环

---

### Agent

- MemoryStore（关键词检索）/ SymbolTable / ProjectGraph
- 信任感知规则 / 必须全部匹配 / Agent 自毁保护
- 7 家 LLM 提供商：DeepSeek/OpenAI/千问/小米MIMO/Gemini/Ollama
- `--dry-run` / `--report` / `--list-tasks` / `--resume`
- V3 单元测试 27 项
- 协议简化为 `tool|params`，协议不再输出 JSON

### Bug Fixes

- sugar parser `tok.tok_type` → `tok.kind`（CI 崩溃）
- JSON 清理 + 空工具纠正 + bare `except:` → `except Exception`

---

## [v3.26.0] — 2026-06-02

> **VM 浮点支持 + C VM UTF-8 + 常量折叠 + 静态类型检查 + LLVM 三态。**

### ⭐ Highlights

- VM `PUSH_FLOAT` (0x48) IEEE 754 double
- C VM UTF-8 字符计数修复（STRLEN/STRSUB 对中文的正确处理）
- 常量折叠 `(加 1 2)` → `3`
- 静态类型检查器 `type_checker.py`（50+ 内置操作类型签名）

---

### VM

- C VM float 字典键支持 / LLVM 三态运行时

### Language

- 类型标注：`定义 f (x: int) { ... }` 调用时校验

### Build

- 运行时合并（3 文件→1）/ 标准库拆分（combined.san 2960 行 → 3 模块）
- 覆盖率 69.2% → 75.32%

### Bug Fixes

- C VM UTF-8 / 字典 key_eq / 糖解析 try/catch / 分派器哨兵
- mypy 37 + ruff 24 全修

### Metrics

| 指标 | 数值 |
|------|------|
| Tests | 617 |
| Integration | 45/46 |
| Coverage | 75.32% |

---

## [v3.25.0] — 2026-06-02

> **村庄观察器全面升级 + 事件系统 + SVG 图表 + 三态信任传播。**

### ⭐ Highlights

- 村庄观察器：单次调用 → Python 逐日主循环
- 夜间事件系统：8 项负面事件，按角色约束分配
- SVG 交互式信任演变图 + 热力图 + JSON 导出

---

### Agent / Simulation

- 宏观趋势分析 / 事件记忆系统 / LLM 行为标签分类器
- 性格乘数 / 天气乘数 / 对话长度因子 / 语气检测
- 间接信任传播 / 凝聚度指数 / 动态 delta 公式
- 剧情续写游戏 + 叙事分支和状态记忆

### Bug Fixes

- sugar parser `_parse_try` 带括号捕获修复
- 分派器 `_DISPATCH_NOT_FOUND` 哨兵
- agent.san 多个函数修复

---

## [v3.23.0] — 2026-06 🏁 Milestone

> **三态系统完整闭环 + 信念系统 + 全后端三态支持。**

### ⭐ Highlights

- 三态系统四元组（值+信度+来源+时间戳）
- 52 个三态 API：构造/传播/判定/冲突/融合/衰减/序列化/容器/调试/数学/逻辑/分布/校准/信念
- VM / C VM / LLVM 全后端三态支持

---

### Language

- 信念系统 `信念(命题,信度,来源,时间)`
- 主观逻辑共识融合 + 贝叶斯更新
- 三态容器（列/字典）/ 时间衰减 / 量化编码 / 冲突模型

### VM

- VM 算术/比较/逻辑 ops 自动传播 TritValue 置信度
- C VM `OBJ_TRIT` 紧凑 12 字节存储
- LLVM `rt_trit_*` 辅助函数系列

### Bug Fixes

- 闭包支持 / lambda 关键字 / C VM 测试卡死 / agent.san 缺失括号

### Documentation

- `docs/ternary-confidence.md` / `docs/ternary-truth-table.md` / `docs/roadmap.md`

---

## [v3.22.0] — 2026-06-01

> **Agent 启动器修复 + 缺失函数补全 + 单元测试增强。**

### ⭐ Highlights

- 4 个启动器注册时序修复（SanyanKeyError）
- Agent 缺失 5 个函数补全
- 8 个村庄/NPC 单元测试

---

### Bug Fixes

- agent.san 缺失闭合括号 / demo_compress.san 英文 op / 断言空壳

---

## [v3.21.0] — 2026-06-01

> **闭包/第一类函数 + import as 别名 + 默认参数 + VM 保护。**

### ⭐ Highlights

- 闭包/第一类函数：`_make_closure_value()` 捕获当前作用域
- `import "path" as alias` 语法
- 默认参数 `定义 foo (x, y = 10) { ... }`

---

### VM

- 最大步数保护 `VM_MAX_STEPS=5_000_000` / 版本号检查
- C VM 字典容量上限 `RT_DICT_MAX_CAP=65536`

### Bug Fixes

- 闭包返回字符串而非 FunctionValue / lambda 关键字误解析
- C VM 测试卡死（sugar parser 缓存）/ 循环错误消息中文化

---

## [v3.20.0] — 2026-05-31

> **Agent v0.3——可读决策 DSL + 概率三态 + 声明式规则 + 自解释深化。**

### ⭐ Highlights

- Agent v0.3：概率三态置信度 + 声明式策略 DSL
- 决策追踪 → 声明式策略 → 自解释 Agent 三层
- 三态推理管线：LLM 5 态 → 5→3 映射 → 贝叶斯传播 → 保护门控 → 表决

---

### Agent

- TritValue 新增 `confidence` 字段（0-1），贝叶斯传播
- `agent_policy.san` 纯数据规则文件（5 条场景规则）
- 交互命令：`/解释 N` / `/最近` / `/原因 N` / `/策略`

---

## [v3.19.0] — 2026-05-30 🏁 Milestone

> **llvmgen.san 自举完成 + sugar.bin 自举验证 + 标准库扩充。**

### ⭐ Highlights

- llvmgen.san 自举（V5）：11 个 Python 辅助函数全内联，69932 字节
- sugar.bin SHA256 自举验证
- LLVM 代码生成器文件拆分（925 行 → 3 文件）

---

### Compiler

- `#include` 预处理接入编译管线 / C VM #include 支持
- llvmgen.san 全中文化 + 繁体修正

### Language

- IoT 三值逻辑案例：传感器融合 / 容错控制 / 状态机
- 标准库扩充：network / hardware / math
- 包管理器：`卸载` / `搜索` / `包信息`

### Bug Fixes

- `_check_div_zero` 常量折叠 / `_normalize_fn_format` 多语句体截断

---

## [v3.18.0] — 2026-05-29

> **C VM 与 Python VM 三值逻辑统一。**

### ⭐ Highlights

- Python VM 所有布尔返回指令统一为三值逻辑（1=真，-1=假）
- 编译管线双解析器：sugar → S-表达式回退

---

### VM

- 比较/逻辑/类型检查/字符串/字典/跳转指令全统一

---

## [v3.17.0] — 2026-05-28

> **C VM 单元测试 + BUILTIN_OPS 自动生成 + 架构文档。**

### ⭐ Highlights

- C VM 61 项单元测试 `csrc/test_runtime.c`
- BUILTIN_OPS 从硬编码 → `language/*.json` 自动生成（170→235 项）
- 架构文档 `ARCHITECTURE.md` + 贡献指南 `CONTRIBUTING.md`

---

### VM

- 性能优化：移除冗余 `resolve_op_name` 调用

### Bug Fixes

- test.san 测试框架修复 / 集成测试 25/43 → 43/43

---

## [v3.16.0] — 2026-05-28

> **自举 .bin 文件 + 字节码格式升级 + JMP32 + 双语 OP 映射。**

### ⭐ Highlights

- sugar.bin / llvmgen.bin 独立 VM 可执行
- 字节码格式 16→32 位 / JMP32 操作码支持 >64KB
- VM 73 项单元测试覆盖全部操作码

---

### Compiler

- 字节码编译器全中文化 / .san 注释全角→半角统一

### Build

- 模块化发行 `pyproject.toml` extras 分组
- sanyan 包命名空间入口

### Bug Fixes

- fn 处理器地址公式修正 / VM DICT/LIST_NEW 空栈安全处理

---

## [v3.15.1] — 2026-05-27

> **参数求值修复 + 自举验证测试。**

### ⭐ Highlights

- 列表代码表达式不再被当作数据字面量（修复自举编译 C 栈递归溢出）
- 自举验证：VM vs 求值器逐字节一致（5442 字节）

---

### Bug Fixes

- `div`/`mod` 补全 `_to_tritvalue()` 转换
- `_list_get_safe` 保护转换

---

## [v3.15.0] — 2026-05-24 🏁 Milestone

> **渐进类型系统 + 标准库扩充 + LLVM 浮点/63位/import/try-catch 全面升级。**

### ⭐ Highlights

- 渐进类型系统：返回类型标注 + 可选类型 `?数字`
- 标准库：JSON / HTTP / Regex / CSV
- LLVM：IEEE 754 double / 63 位整数 / import 静态链接 / try-catch 重写

---

### Language

- 类型标注 `定义 fn() -> 数字` 糖语法支持

### Compiler

- LLVM 优化 passes（mem2reg / instcombine / GVN 等）
- Arena 字符串分配器（64KB auto-grow）
- 字典 FNV-1a 哈希 + 开放寻址 + 动态扩容

### Bug Fixes

- C VM 7 项修复（CALL 格式 / 算术补充 / CONCAT 栈泄漏 / DICT 动态扩容 等）
- ruff 4 + mypy 9 全清

### Metrics

| 指标 | 数值 |
|------|------|
| LLVM int | 63-bit (±4.6×10^18) |
| Ruff / Mypy | 0 |

---

## [v3.14.0] — 2026-05-23 🏁 Milestone

> **字节码 VM 完整自举 + 行注释 + DICT_KEYS 操作码。**

### ⭐ Highlights

- **VM 编译与求值器完全一致**：5442 字节，5406 字节码——自举达成
- 行注释 `//`（半角）和 `／／`（全角）
- DICT_KEYS 操作码 (0x32)

---

### VM

- 栈隔离：CALL/RET 正确清理被调方泄漏
- STORE 扫描自动推算参数个数
- DICT_SET 去 push / `_exec_frame` 变量隔离
- `from_bin` 自动执行模块初始化

### Bug Fixes

- 发射 i32 溢出 / 字符串引号检测 / OP 映射全别名 / 非列表节点 op 路由

---

## [v3.13.0] — 2026-05-20

> **求值器模块拆分 + 命令模块重构 + 统一错误处理 + 标准库扩充。**

### ⭐ Highlights

- 求值器 315→176 行（-44%），命令模块 200→105 行（-48%）
- 统一错误处理 `ops/_error_handler.py`
- 标准库：algorithm / collection / validate

---

### Language

- `stdlib/algorithm.san`（二分查找/排序/数论）/ `collection.san`（栈/队列/集合）/ `validate.san`（邮箱/IP/身份证/URL）
- 示例：学生成绩管理 / 销售数据分析 / 文件批量处理

---

## [v3.12.0] — 2026-05-20

> **LLVM 文档 + 多解析器回退 + 运行时字符串修复 + GUI 工具集。**

### ⭐ Highlights

- LLVM 编译管线完整文档 `docs/llvm.md`
- 运行时字符串格式不兼容修复（12 个字符串操作 + 4 个字典函数）

---

### Bug Fixes

- `runtime.c` 裸 `const char*` vs `rt_str_t*` 类型不匹配——新增 `_cstr()`/`_cstr_len()` 统一访问

### Toolchain

- GUI IDE `gui.py`（Dev-C++ 风格）+ PyInstaller 打包 + Inno Setup 安装包

---

## [v3.11.0] — 2026-05-17 🏁 Milestone

> **交叉编译工具链 + STM32 固件 + C VM + 纯三进制数学。**

### ⭐ Highlights

- `sanyancc.py`：AST → 平坦字节码编译器（~27 条指令）
- **STM32 硬件运行成功**：`examples/stm32-blinky/` Blue Pill PC13 LED 200ms 闪烁
- 纯三进制数学：三角函数/平方根/对数纯三进制定点实现

---

### VM

- C 字节码解释器 `runtime.c`，与 STM32 共享指令集
- WAIT / 7 个比较指令 / 栈式 IO

### Bug Fixes

- STM32：BSS 初始化 / WFI 掉线 / 设备数组越界 / 向量表 / SysTick / USART1

---

## [v3.10.0] — 2026-05-16 🏁 Milestone

> **类型标注 + LSP Hover + 性能剖析 + 表达式断点 + 源码格式化器 + DAP。**

### ⭐ Highlights

- 类型标注系统 + LSP 6 个 provider（格式化/符号/折叠/引用/重命名/语义补全）
- DAP 调试适配器（VS Code 断点/单步/变量查看/栈帧）
- `sanfmt.py` 格式化器（类 black/prettier，注释保留）

---

### Language

- 性能剖析（`:profile`）/ 表达式断点（`:step/:break/:watch/:continue`）
- SrcNode AST 位置注入 + 异常「第N行第M列」
- `--ast-json` 序列化导出

### Toolchain

- 性能基准套件 `benchmark/`
- 包管理器 URL 白名单 / `#include` 相对路径
- REPL 历史持久化 + 语法高亮

---

## [v3.9.0] — 2026-05-16

> **sugar.san 接入导入管线 + 性能优化 + 操作注册表统一。**

### ⭐ Highlights

- sugar.san 自举接入 `import_module()` 解析管线
- 词法分析 O(n²) → O(n) 性能优化
- 37 项 sugar.san 兼容性测试

---

### Build

- `含键`/`计数` 内置操作注册
- 代码重复清理 / 错误处理收紧 / 安全隐患修复（zip-slip）
- `self.vars` → `scope_vars` 消除 Python 内置遮蔽

---

## [v3.8.0] — 2026-05-16

> **纯 Sanyan 元循环求值器 + 操作注册表 + 测试覆盖全面升级。**

### ⭐ Highlights

- `stdlib/eval.san`（~300 行）：自举级求值器，支持闭包/高阶函数
- 操作注册表统一：`registry.get_op()` 替代手写分发表
- 66 项 ops 单元测试 + 6 项 LSP + 6 项包管理器 + 22 项 AST 校验

---

### Language

- `dict_contains` 操作 `含键`（永不抛异常）

### Bug Fixes

- 断言框架除零触发 / 路径穿越加固 / HTTPS 强制

---

## [v3.7.1] — 2026-05-15

> **Sugar 解析器修复 + TritValue LRU + 类型注解补充。**

### ⭐ Highlights

- 前缀运算符解析修复（同时查询 KEYWORD_MAP 和 OP_MAP）
- TritValue 对象池 `dict.clear()` → `OrderedDict` LRU

---

### Bug Fixes

- 列表推导式裸 `except Exception` 收紧
- evaluator.py 死代码清理

### Toolchain

- CI/CD：`actions/checkout@v3→v4` / `setup-python@v4→v5`
- 类型注解补充（8 文件）/ `_name_cache` 5000 上限

---

## [v3.7] — 2026-05-14

> **浮点数 + JSON + 标准库 + CI/CD + 模块拆分。**

### ⭐ Highlights

- TritValue 扩展 float 支持 / `转JSON` `解析JSON`
- GitHub Actions CI/CD + Ruff Linter + pyproject.toml

---

### Language

- 标准库：math（最大公约数/最小公倍数/素数）、list
- ops 拆分：`io_ops.py` → `io_ops.py` + `file_ops.py` + `type_ops.py`
- 三角函数从千分位返回改为高精度浮点

---

## [v3.6] — 2026-05-13

> **预处理模块 + 异常体系 + 作用域栈式重构。**

### ⭐ Highlights

- `preprocess.py` 公共预处理模块
- 8 种语言层异常（SanyanSyntaxError / SanyanTypeError / SanyanValueError 等）
- 作用域栈式链：`_scopes` 栈替代全量拷贝，零拷贝 `push_scope()` / `pop_scope()`

---

### Language

- 跨作用域变量查找 / 模块导入缓存 / 路径安全校验

### Bug Fixes

- main.py O(n²) 语法检测 / 尾递归作用域重复弹出

---

## [v3.5] — 2026-05-13

> **语义化运算符 + 双语法测试 + Include 预处理器 + REPL 增强。**

### ⭐ Highlights

- `不大于` / `不小于` 语义化比较运算符
- 双语法对照测试（糖语法 + S 表达式 `_se` 版本）
- `#include` 预处理器 + REPL 历史记录 + Tab 补全

---

### Language

- Lambda 闭包 / 字典点号访问 / 三进制字面量
- REPL 中文切换命令 / S 表达式自动检测

### Bug Fixes

- 尾递归作用域重复弹出 / ModuleValue.call 参数二次 eval / `pow` 键重复

---

## [v3.4] — 2026-05-08

> **国际化皮肤系统 + 全角符号 + 字符串插值 + 三态分支。**

### ⭐ Highlights

- 国际化皮肤系统 `skin.py`（中/英文关键字切换）
- 全角符号兼容 + 字符串插值 `模板{文本${expr}文本}`
- 三态分支 `判 x { 真 {...} 可能 {...} 假 {...} }`

---

### Language

- `跳出` 关键字 / 窄异常捕获
- 示例：三态投票统计 / 不确定数据清洗

### Build

- `builtins_ops.py`（500+ 行）→ `ops/` 模块包拆分
- 消除循环依赖：提取 `values.py`

---

## [v3.3] — 2026-05-04 🏁 Milestone

> **初始发布：平衡三进制核心 + 糖语法 + S 表达式 + 高阶函数 + IoT。**

### ⭐ Highlights

- 平衡三进制核心数据类型（TritValue）
- 糖语法解析器（Pratt）+ S-表达式双语法
- 高阶函数 + 闭包支持
- IoT 设备抽象 + 温室示例

---

