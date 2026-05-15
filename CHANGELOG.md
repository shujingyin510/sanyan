# Changelog

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
- **CONTRIBUTING.md**: 贡献指南文档。
- **ops/__init__.py**: 添加模块文档字符串。
- **tests/test_core.py**: 新增 `TestPreprocess` 测试类（3 项）、`TestTernaryEdge` 测试类（4 项）。


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

## [v3.3] — 2025-05
- 初始发布：平衡三进制核心、糖语法、S 表达式、高阶函数、IoT 抽象、温室示例

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

### 变更
- **删除无用文件**：`test_debug.py`、`test_repl.py`、`gen_pipeline.py`、`tests/test_debug2.san`、`tools/generate_clean_tests.py`、`tools/safe_fullwidth.py`