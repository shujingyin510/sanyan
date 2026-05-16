# Changelog

---

## [v3.10.0] — 2026-05-16

### 新增
- **5 个 stdlib 文件文档** (`docs/manual.md` 第 15 节): 新增 `stat.san`（三态统计）、`tokenize.san`（词法分析器）、`parse.san`（S 表达式解析器）、`eval.san`（元循环求值器）、`sugar.san`（糖语法解析器）的 API 说明。
- **3 个互动示例** (`examples/`): `text_analysis.san`（文本分析）、`guess_number.san`（猜数字游戏）、`fizzbuzz.san`（FizzBuzz）——验证糖语法、作用域、逻辑判断、异常处理、字典操作、`含键`/`计数` 等特性。
- **新功能测试** (`tests/test_new_features.san`, `tests/test_new_features_se.san`): 含键、计数、范围、字典键存在检查、浮点数序列化。

### 修复
- **全角负号解析** (`sugar/lexer.py:123`): NEGATIVE NUMBER 词法单元中的全角减号 `－` 现在正确转换为半角 `-`。
- **test_fullwidth.san** (`tests/test_fullwidth.san`): 重写为完整的全角字符测试套件，覆盖全角数字/运算符/注释/方括号。

### 文档
- **stdlib 文档补全**: `docs/manual.md` 新增 5 个缺失 stdlib 模块的 API 参考。
- **run_all.py 更新**: `tests/run_all.py` 新增新示例，共 35 项集成测试。

---

## [v3.9.0] — 2026-05-16

### 新增
- **sugar.san 接入导入管线** (`ops/file_ops.py`): `import_module()` 和 `_parse_and_eval_file()` 统一经过 `_parse_code()`，按序尝试 sugar.san → Python SugarConverter → S 表达式回退。sugar.san 通过 `_load_sugar_parser()` 自举（Python SugarConverter 编译 → SanyanEvaluator 执行注册 `解析`/`词法分析` 命令）。
- **sugar.san 性能优化** (`stdlib/sugar.san`): `词法分析` 开头调用 `设 chars = 字列(source)` 将字符串拆为字符列表，后续所有单字符访问 `子串(source, i, 1)` 替换为 `取(chars, i)`，复杂度从 O(n²) 降至 O(n)。
- **sugar.san 鲁棒性**: 修复注释 `/` 误判、全角数字识别、运算符映射、`再若`/`elif` 支持、`捕获` 不带 `(var)` 语法。
- **sugar.san 测试** (`tests/test_sugar_san.py`): 37 项测试覆盖加载、基础解析、控制流、列表/字典、try/catch、运算符优先级、边界条件、全角、点号访问、结构校验、Python 兼容性。
- **`含键`/`计数` 内置操作**: `runtime.py` BUILTIN_OPS 新增 `'含键'`、`'计数'`；`language/chinese.json` 新增 `"dict_contains": "含键"`。
- **文档同步**: `docs/manual.md` 第 17 节新增 `含键` 条目。

### 修复
- **eval.san 语义** (`stdlib/eval.san:269`): 分析确认 `是字符串(stripped)` 正确，未做改动。

### 重构
- **代码重复清理** — 提取共享 `to_num()` 工具函数到 `values.py`，消除 `container_ops.py` 中 10+ 处重复的 `TritValue` 数值转换模式；`package_ops.py` 复用 `file_ops._parse_code` 消除文件解析逻辑重复。
- **错误处理收紧** — 20 处 `except Exception` 替换为精确异常类型（`ValueError`, `TypeError`, `IOError`, `json.JSONDecodeError` 等）；`main.py` sugar 语法失败不再静默，错误信息叠加显示。
- **安全隐患修复** — `package_ops.py` zip-slip 攻击防护（逐文件校验路径）；丢失的 `with open()` 上下文管理器补全。
- **职责拆分** — `evaluator.py._eval_str` 拆分为 `_parse_string_literal` / `_parse_numeric_literal` / `_resolve_identifier` 三方法；`_eval_symbol` 从 `runtime.py` 移至 `evaluator.py`（求值逻辑归求值器）。
- **TritValue 对象池** — 新增 `threading.Lock` 线程安全保护；池大小通过 `TRIT_POOL_SIZE` 环境变量可配置。
- **`self.vars` 改名** — `runtime.py` 属性 `vars` → `scope_vars`，消除对 Python 内置 `vars()` 的遮蔽；波及 `control_ops.py`, `values.py`, `file_ops.py`, `package_ops.py`, `test_core.py`。
- **测试深度提升** — `test_parser.py` 转为 unittest 格式（28 项）；`test_ops.py` 新增 12 项负面测试（除零、类型错误、参数缺失、边界条件、混合类型等）。

### 基础
- 全部 6 项技术债清理完毕，252 项测试（含 37 项 sugar.san 测试 + 28 项 parser unittest + 12 项负面测试）全部通过。

---

## [v3.8.0] — 2026-05-16

### 新增
- **纯 Sanyan 元循环求值器** (`stdlib/eval.san`, ~300 行): 运行在 Python 求值器之上的自举级求值器——支持变量绑定、特殊形式（若/做/设/定义/函数/循环/遍历/尝试）、内置操作分派（40+ 操作）、闭包与高阶函数调用。10 组集成测试覆盖算术、比较、逻辑、列表、条件、递归、lambda、闭包、斐波那契。
- **`dict_contains` 操作** (`ops/container_ops.py`): 安全的字典键存在检查（`含键`），返回 `真`/`假` 永不抛异常，配套内置包装。
- **操作注册表统一** (`ops/registry.py`): 每个 `ops/*.py` 模块末尾加 `register()` 调用，`evaluator.py` 的 `_OP_DISPATCH` 手写分发表完成迁移到 `registry.get_op()`。
- **ops 模块单元测试** (`tests/test_ops.py`): 66 项 Python unittest 覆盖算术、比较、逻辑、数学函数、字符串、容器、控制流、JSON、Lambda、文件等全部操作类别。
- **LSP 测试** (`tests/test_lsp.py`): 6 项（initialize/completion/hover/definition/signatureHelp/didOpen），使用后台读取线程 + 响应 ID 匹配正确区分通知和请求。
- **包管理器测试** (`tests/test_package.py`): 6 项覆盖安装拒绝 HTTP/FTP、加载不存在的包、包路径解析。
- **解析器 AST 校验** (`tests/test_parser.py`): 从仅检查"不崩溃"升级为 22 项精确 AST 结构验证（每个测试检查特定的节点类型、子结构、字面值格式）。
- **`editor.skel.py`, `doc_sync.py`** 等辅助工具。

### 修复
- **断言框架** (`stdlib/test.san`): `_断言失败` 改为 `1 / 0`（除零触发 `SanyanValueError`），修复断言失败不报错的 bug。
- **路径穿越加固** (`ops/file_ops.py`): `_resolve_path` 先 `os.path.normpath` 再检查 `..`，防止 `./../../` 绕过。
- **HTTPS 强制** (`ops/package_ops.py`): 下载包前检查 URL 以 `https://` 开头。
- **`input_op` 鲁棒性** (`ops/io_ops.py`): 改用 `try: float()` 替代手动 `isdigit` 校验。
- **`get_var` 语义** (`runtime.py`): 找不到变量时改为 `raise SanyanNameError` 替代返回 `None`。
- **`eval` 支持 `float`** (`evaluator.py`): 原只支持 `int` 节点类型，现同时支持 `float`。
- **CHANGELOG 顺序** — v3.3→v3.4→v3.5→v3.6 恢复正确时间线。

### 变更
- **求值器重构** (`evaluator.py`): `eval()` 拆分为 `_eval_list()` / `_eval_str()`；`_apply()` 拆分为 `_resolve_op_name()` / `_dispatch_op()` / `_handle_dot_access()` / `_handle_variable_call()`。
- **死代码移除** (`evaluator.py`): `_name_cache_put()` 方法已定义但从未调用 — 删除。
- **分号风格统一** (`ternary_core.py`): 5 行 `res.append(...); carry = ...` 拆为两行。
- **测试覆盖增强**: 10 个 `.san` 测试文件（math/string/container/edge/scope/stress/tailcall/type/v37/regression）新增断言语句，`run_all.py` 退出码检查因此更有意义。
- **`ModuleValue.call`** (`values.py`): 执行函数体期间暴露模块内部 commands，使嵌套调用可达。
- **文档同步**: README 删除重复文件树（317-339 行），补充遗漏的 `main.py`，修正错误注释。
- **覆盖率配置** (`pyproject.toml`): 新增 `[tool.coverage.run]` / `[tool.coverage.report]`。

### 文档
- **CHANGELOG.md**: 新增 v3.8.0 条目。
- **README.md**: 更新版本号、修正项目结构树、删除重复条目。

---

## [v3.7.1] — 2026-05-15

### 修复
- **sugar.py**: `parse_primary` 同时查询 `KEYWORD_MAP` 和 `OP_MAP`，修复 `非`/`取位` 前缀运算符解析失败。
- **evaluator.py**: 移除 `_apply` 方法中无操作 `if ...: pass` 死代码块。
- **ternary_core.py**: `TritValue` 对象池从 `dict.clear()` 整体清空改为 `OrderedDict` LRU 逐出策略。
- **sugar.py**: 列表推导式试探解析的 `except Exception` 裸捕获改为 `except (SyntaxError, SanyanError)` 精确异常。

### 变更
- **skin.py**: 移除重复的 `ROOT_TERNARY` 硬编码，统一从 `TritValue.STATE_MAP` 获取三态词根表。
- **CI/CD**: `actions/checkout@v3→v4`、`setup-python@v4→v5`；新增 `test_parser.py` 回归测试步骤。
- **类型注解**: 为 `values.py`、`commands.py`、`lexer.py`、`parser.py`、`preprocess.py`、`evaluator.py`、`repl.py`、`runtime.py` 补充 `typing` 签名。
- **evaluator.py**: `_name_cache` 加入 5000 上限保护，防止长 REPL 会话中无界增长。
- **commands.py**: TCO 迭代乘数从魔数 `10` 提取为 `_TCO_LOOP_MULTIPLIER` 常量。

### 文档
- **CHANGELOG.md**: 新增 v3.7.1 条目。

### 新增
- **模块导出系统**: `导出 name1 name2` 控制模块可见性；`import_module` 循环依赖检测。
- **设备注册表**: `Device` 协议 + `MockDevice`/`FileDevice` + `DeviceRegistry`；`注册设备 名称 为 类型` 语法。
- **糖语法解析器拆分**: `sugar.py` 拆分为 `sugar/` 包（`lexer.py`、`parser.py`、`errors.py`），Pratt 解析替代手写递归。
- **三进制定点数**: `BT.from_float()` / `BT.to_float()` 将浮点转为平衡三进制 trits 表示。
- **`#` 行注释**: 新增 `#` 注释语法。
- **全角引号定界符**: 新增 `「」`、`『』`、`""`、`''` 六种字符串定界符。
- **S 表达式 IoT 中文别名**: `读取`、`写入`、`查询` 直接可用。
- **希腊字母 Lambda**: `λ(x) { ... }` 等价于 `函数(x) { ... }`。
- **`BUILTIN_OPS` 补全**: 补充 `跳出`/`继续`/`判`/`导入`/`导出`/`注册设备`/`读取`/`写入`/`查询`/`从`/`到`/`在`。
- **CONTRIBUTING.md**: 贡献指南文档。
- **ops/__init__.py**: 添加模块文档字符串。
- **测试**: 新增 `TestPreprocess` 3 项、`TestTernaryEdge` 4 项（含定点数）。
- **三进制数学库**: `sin`/`cos`/`tan`/`sqrt`/`exp`/`log`/`log10` 纯三进制定点实现（CORDIC + Taylor + Newton），替代 Python float 回退。
- **LSP 语言服务器**: `lsp_server.py` 提供代码补全、诊断、悬停提示、跳转定义、签名帮助。
- **`ops/registry.py`**: 装饰器驱动的操作注册表，替代 `_OP_DISPATCH` 手写分发表。
- **`_name_cache` LRU 淘汰**: 全量清空 → 单条目 LRU 逐出。
- **`commands.py:call()` 重构**: 108 行单方法拆分为 6 个子方法（`_resolve_command`/`_match_params`/`_evaluate_args`/`_detect_tail_call`/`_run_tail_call`/`_run_normal`）。
- **VS Code 扩展**: `sanyan-vscode/` 扩展包，提供语法高亮 + LSP 客户端。
- **`doc_sync.py`**: 文档自动同步脚本。
- **移除 `sugar/sugar_old.py`**: 旧解析器 fallback 删除，减少 680 行遗留代码。
- **全角 `<=` 等运算符修复**: `sugar/lexer.py` 多字符运算符检查改用 mapped 字符。
- **`parse_if` 递归修复**: 再若/否则的双消费 token 问题。
- **`.vscode/settings.json`**: VS Code 工作区配置。
- **包管理器**: `ops/package_ops.py` 提供 `安装`/`包列表`/`加载包` 命令；本地+远程包索引；示例包 `sample`。
- **VS Code Marketplace 上架**: `sanyan-language-0.1.0.vsix` 已发布，VS Code 搜索 `三言` 即可安装。
- **扩展 Logo**: 128x128 自定义图标。


## [v3.7] — 2026-05-14

### 新增
- **浮点数支持**：`TritValue` 扩展支持 Python float，算术运算（加减乘除幂）支持自动类型提升。
- **JSON 支持**：新增 `转JSON` (`to_json`) 和 `解析JSON` (`from_json`) 内置操作。
- **标准库扩充**：
    - `math.san`: 新增 `最大公约数`、`最小公倍数`、`素数判断`、`圆面积`。
    - `list.san`: 新增 `计数`、`是列表`。
- **工程化增强**：
    - `pyproject.toml`: 引入现代打包配置，集成 Ruff Linter。
    - `CI/CD`: 增加 GitHub Actions 自动化测试。
    - **模块拆分**: `ops/io_ops.py` 拆分为 `io_ops.py`, `file_ops.py`, `type_ops.py`。
- **类型标注**: 为 `ternary_core.py` 和 `runtime.py` 补充类型注解。

### 变更
- **三角函数**: 从整数千分位返回改为直接返回高精度浮点数。
- **`main.py`**: 提取 `main()` 入口，版本号更新至 v3.7。

---

## [v3.6] — 2026-05-13

### 新增
- **`preprocess.py` 预处理模块**：将 `main.py` 和 `sugar.py` 中重复的 `#include` 展开逻辑提取为公共函数 `preprocess_includes()`
- **`SanyanValueError` / `SanyanRuntimeError` / `SanyanKeyError` / `SanyanAttributeError`**：补齐语言层异常体系
- **跨作用域变量查找**：`SanyanRuntime.get_var(name)` / `has_var(name)` / `set_var(name, value)` / `all_scoped_vars()` 方法
- **模块导入缓存**：`导入()` 重复加载同一文件不再重新解析，直接返回缓存的 `ModuleValue`
- **文件路径安全校验**：`_resolve_path()` 阻止 `..` 目录穿越，覆盖 `读文件`/`写文件`/`加载`/`导入`
- **`#include` 路径安全校验**：`preprocess.py` 禁止 `..` 穿越
- **`tests/test_core.py`**：Python 单测 26 项（三进制核心、作用域栈、异常体系、函数调用、模块）

### 变更
- **统一错误类型**：所有运行阶段 `raise` 从 Python 原生异常改为 Sanyan 系列
  - `SyntaxError` → `SanyanSyntaxError` / `TypeError` → `SanyanTypeError` / `ValueError` → `SanyanValueError` 等 8 种
  - 保留 Python 原生的仅 `parser.py`（解析阶段）和 `ternary_core.py`（避免循环依赖）
- **作用域栈式链重构**：替代 `saved_vars = dict(evaluator.vars)` 全量拷贝方案
  - `SanyanRuntime` 新增 `_scopes` 作用域栈，`vars` 改为 property 指向栈顶
  - `commands.py:call()`、`values.py:FunctionValue.call()`、`values.py:ModuleValue.call()` 使用 `push_scope()` / `pop_scope()` 零拷贝
  - 闭包捕获、调试显示、REPL 补全均改用 `all_scoped_vars()`
- **main.py 语法检测简化**：删除手动注释/字符串扫描（30 行），改为 try-fallback 模式对齐 REPL
- **`_load_file` 语法检测对齐**：同样改为 try-fallback
- **循环条件求值修正** (`loop_op`)：条件表达式从循环末尾移到开头重新求值
- **三进制乘法加速**：用 Python int 乘法替代 trit-by-trit 移位加，大数 O(n·m)→O(log n)
- **IO 异常规范化**：文件 IO 错误从 `IOError`/`FileNotFoundError` 转为 `SanyanValueError`，可被 `尝试/捕获` 捕获
- **sugar.py 结构优化**：`_is_ident` 提取为模块级函数，类内加分区注释
- **`lexer.py` 全角符号补全**：新增 `；`（全角分号）和 `　`（全角空格）
- **`evaluator.py` `_name_cache`**：缓存原始关键词→内部标识映射，减少运行时皮肤查表

### 修复
- **main.py O(n²) 语法检测**：`code.index(ch)` 循环内扫描修复为标准索引遍历
- **尾递归作用域重复弹出**：`finally` 与 `except` 双重 `pop_scope()` 修复
- **sugar.py 导入优化**：`preprocess_includes` 提升为模块级 import
- **sugar.py token 行号定位**：从 `str.find()` 重构为同步扫描定位，避免重复 token 匹配错误

---

## [v3.5] — 2026-05-13

### 新增
- **`不大于` / `不小于` 运算符**：语义化比较运算符，分别等价于 `<=` / `>=`，支持中文和半角符号（`!>` / `!<`）
- **双语法对照测试与示例**：所有测试和示例均提供糖语法 + S 表达式双版本（`_se` 后缀），方便对照学习
- **测试框架增强**：新增 `断言不相等`、`断言大于`、`断言小于`、`断言大于等于`、`断言小于等于`、`断言错误`（支持可变参数）
- **S 表达式语法检测**：`main.py` 自动识别 S 表达式文件，注释中的 `{` 不再误判为糖语法
- **REPL 中文切换命令**：`切换中文`/`切换英文` 替代 `:lang chinese`/`:lang english`，同时支持 `:lang 中文`/`:lang 英文`
- **模块路径解析**：`导入("test")` 自动查找 `stdlib/test.san`，无需写完整路径
- **调试信息增强**：`调试()` 输出包含变量类型、调用栈深度和最近调用
- **性能优化**：TritValue 对象池 + `__slots__` + `_apply` 方法缓存
- **Lambda 闭包**：Lambda 自动捕获定义时的变量环境，支持闭包
- **字典点号访问**：`学生.姓名` 等价于 `取键(学生, "姓名")`
- **三进制字面量**：`三进制("+-0")` 将三进制字符串转为整数（即 6）
- **#include 预处理器**：`#include "test"` 编译时展开文件内容
- **REPL 历史记录**：上下键翻历史，Tab 键自动补全关键字和变量名
- **基准测试**：`tests/benchmark.san` 测量运算/调用/列表/逻辑性能

### 变更
- **删除无用文件**：`greenhouse.log`、`__pycache__/`、`.github/workfliws/`、`tools/`、`tests/fuzz.py`
- **版本号统一**：`main.py`、`repl.py` 版本号更新至 v3.5
- **skin.py**：`switch_skin()` 支持中文参数（`'中文'`/`'英文'`）

### 修复
- **尾递归作用域重复弹出**：`commands.py` 中 `ReturnException` 触发时 `finally` 与 `except` 均调用 `pop_scope()`，修复为仅 `finally` 负责清理
- **ModuleValue.call 参数求值**：修复已求值参数被二次 `eval` 导致列表值作为代码执行的 bug
- **evaluator.py 重复键**：修复 `_OP_DISPATCH` 中 `pow` 键重复导致三进制幂运算被覆盖
- **repl.py :maxloop**：修复 `:maxloop` 命令嵌套在 `:lang` 分支内不可达的问题
- **stdlib/test.san 断言**：断言失败时不再静默通过，改为返回错误消息触发异常
- **stdlib/list.san 空列表**：`最大值([])` 和 `最小值([])` 不再因 `空` 未定义而崩溃
- **stdlib/string.san 计数**：修复 `计数` 函数切片后位置计算错误
- **language/english.json**：补充缺失的 `do` 关键字
- **docs/manual.md**：删除重复的目录标题和重复的 4.6 节

---

## [v3.4] — 2026-05-08

### 新增
- **国际化皮肤系统** (`skin.py`)：关键字、操作符可切换，默认中/英文皮肤
- **全角符号兼容**：纯中文输入法可自由编写代码，全角空格智能跳过
- **字符串插值**：`模板{文本${表达式}文本}` 自动展开为 `连接` 调用
- **三态分支 `判`**：`判 x { 真 {...} 可能 {...} 假 {...} }` 原生三态模式匹配
- **`跳出` 关键字**：可在 `循环` 和 `遍历` 中提前退出
- **窄异常捕获**：`尝试`/`捕获` 只捕捉语言层 `SanyanError`，系统错误直接暴露
- **新增示例**：
  - 三态投票统计 (`examples/voting.san`)
  - 不确定数据清洗 (`examples/data_clean.san`)
- **回归测试**：解析器测试 24 项 + 运算符/容器/跳出/异常测试

### 变更
- **拆分内置操作**：将原先 500+ 行的 `builtins_ops.py` 拆分为 `ops/` 模块包（control、math、string、container、io、iot）
- **消除循环依赖**：提取公共值类型与异常到 `values.py`
- **清理死代码**：移除未使用的 `_maybe_implicit_and` 方法
- **优化语义**：温室示例输出措辞调整，`查` 命令显示中文状态词（开/守/关）
- **皮肤文件整理**：`language/chinese.json`、`language/english.json` 完善所有关键字

### 修复
- **运算符优先级**：比较运算符优先级高于逻辑运算符（`a > 2 且 b < 4` 正确解析）
- **前缀操作符**：`读 人体` 在S表达式全中文输入下正确识别
- **容器操作**：字典/列表/数组的边界情况处理
- **REPL 中断**：`Ctrl+C` 优雅退出，不再显示 traceback
- **异常处理**：文件不存在等系统错误不会被误吞

### 文档
- 更新语言手册：新增 `跳出`、`判`、`模板`、皮肤、窄异常章节
- 更新 README：温室输出示例含三进制后缀

### 测试
- 新增自动回归测试运行器 `tests/run_all.py`
- 新增边界测试 `tests/test_edge.san`

---

## [v3.3] — 2025-05
- 初始发布：平衡三进制核心、糖语法、S 表达式、高阶函数、IoT 抽象、温室示例
