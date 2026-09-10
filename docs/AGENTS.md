# AGENTS.md — 三言项目维护约定

## 🚨 最高优先级：提交前强制自查

**每次 `git commit` 前，必须先跑本地全量测试和CI测试，绿了才能提交：**

```bash
ruff check . && ruff format --check . && mypy . && python -X utf8 scripts/preflight.py --quick
```

绿了 → 提交。红灯 → 修完再提。**不允许跳过。不允许 `--no-verify`。**
这条规则优先级高于一切——宁可慢一点，不要再把 CI 红着推上去。

---

## 📋 工作优先级（从上到下执行）

| 等级 | 触发条件 | 行为 |
|------|------|------|
| 🚨 P0 | 用户直接指令 | 立即执行，其他事暂停 |
| 🚨 P0 | git commit / push | **必须用户明确要求**，禁止自行决定 |
| 🚨 P0 | 准备提交/推送前 | **必须先跑全量 CI 测试**（ruff + mypy + pytest 全量），本地全绿才能推。不许依赖 CI 远程验证 |
| 🚨 P0 | CI 红灯 / bug 报错 | 立即修，修完跑 preflight 绿了再继续 |
| 🚨 P0 | 发现预存问题/技术债 | 及时修复，不跳过不延后，不让 CI 持续红灯 |
| 🚨 P0 | 不确定需求 | 先问，不要猜 |
| 🚨 P0 | 不确定文件用途 | 先搜索引用关系 |
| 🚨 P0 | 不确定修改影响 | 先分析再修改 |
| 🚨 P0 | CHANGELOG 格式 | 按模板写：Summary → Highlights(3-4条) → Language/Compiler/VM/Agent/Build/Project Layout/Toolchain/CI → Bug Fixes → Metrics |
| 🔴 P1 | 写完任何代码 | 先跑 `ruff check . && ruff format --check . && mypy .` |
| 🔴 P1 | 推送前 | 检查 CHANGELOG 是否更新、版本号是否一致（README/manual/llvm 等） |
| 🔴 P1 | CHANGELOG | 记录原因，不只记录结果；功能写完就写，同日合并为一个版本号 |
| 🔴 P1 | 修改代码 | 优先最小变更 |
| 🔴 P1 | 新增函数/模块前 | 先搜索项目是否已有实现 |
| 🟡 P2 | 多文件替换 / 中文内容编辑 | 用外置 `.py` 脚本操作，不要 bash 内联（避免 GBK/UTF-8 编码错误） |
| 🟡 P2 | 新增/删除/重命名文件 | 同步更新 README 目录树 + 文件结构表格 |
| 🟡 P2 | 新增 CLI 标志 | 同步更新 AGENTS.md / CHANGELOG；本仓 CLI 不再提供 Agent 子命令 |
| 🟡 P2 | 新文件行数 | 超过 500 行提示审查；超过 1000 行必须说明为什么不拆。已有文件不回溯 |
| 🟢 P3 | 日常小改动、调试、提示词调优 | 只本地 commit，不 push，等用户确认 |

---

## 汇编器（Agent 写字节码用）

> **重要**：汇编器允许 Agent 直接写 Sanyan 字节码程序。语法和陷阱见 → [`docs/asm_guide.md`](asm_guide.md)

```bash
python asm.py program.sasm -o program.bin     # 汇编
python -X utf8 sanyanc.py program.bin --run   # 运行
```

关键陷阱：比较指令返回 TritValue(-1/1) 而非 int(0/1)，JZ/JNZ 需要加 1 归一化。

## Agent 系统（已迁出）

> **2026-09-10 起，Agent 子系统不在本仓维护。**
> 新仓：<https://github.com/shujingyin510/sanyan-agent>
> 本仓只保留语言 / 编译器 / VM / 约束系统；`sanyan agent` / `sanyan bench` CLI 子命令改为指路提示。
> 决策、死因考古与冻结条件见知识库 `sanyan-obsidian`，本仓入口 [`AGENT_MOVED.md`](AGENT_MOVED.md)。

汇编器仍可被任意宿主（含 sanyan-agent）用来写字节码，见上方「汇编器」一节。

## 自举层级

| 层级 | 状态 | 说明 |
|------|------|------|
| Level 0 | ✅ | Python evaluator 作为宿主编译器 |
| Level 1 | ✅ | bytecode_compiler.san 用三言写 |
| Level 2 | ✅ | VM 加载 A → 编译 B → B 编译 C → B==C（不动点验证） |
| Level 3 | ✅ | C 种子 VM：Linux TCC/gcc -nostdlib ~2KB；Windows MinGW CRT 路径 |
| Level 4 | ✅ | 617 行 x86_64 NASM 汇编 VM，无需 C 编译器 |

```bash
# Level 3 编译（Linux）
gcc -nostdlib -Os -fno-builtin -lgcc csrc/sanyan_vm_seed.c -o sanyan_vm -s
# Level 3 编译（Windows / MSYS2 MinGW）
gcc -Os -std=c99 csrc/sanyan_vm_seed.c -o sanyan_vm_seed.exe
# Level 4 汇编（Linux + nasm）
nasm -f bin -o sanyan_vm csrc/sanyan_vm_l4.asm
```

## ISA v2

| opcode | 编号 | 说明 |
|--------|------|------|
| LOAD16 | 0x3B | 2 字节变量索引 |
| STORE16 | 0x3C | 2 字节变量索引 |
| CALL32 | 0x3D | 4 字节函数地址 |
| PUSH_STR16 | 0x3E | 2 字节字符串长度 |
| CLOSURE | 0x4B | 创建闭包：4字节函数体地址 |
| CALL_CLOSURE | 0x4C | 调用闭包 |

## 工具

| 工具 | 文件 | 用途 |
|------|------|------|
| 汇编器 | `asm.py` | 汇编文本 → .bin |
| 反汇编器 | `disasm.py` | .bin → 反汇编（--hex/--brief/--export） |
| 验证器 | `verify.py` | JMP/LOAD/STORE 边界检查 |
| 编译器 | `sanyanc.py` | .san → .bin（S-表达式 + sugar 双语法） |
| 预检 | `scripts/preflight.py` | 发版前全量检查（lint/mypy/全测试/编码/自举） |

## 环境

- **Python**: `python`（≥3.12）
- **UTF-8**: 运行 `.san` 文件时始终用 `python -X utf8`

## Git 操作

**⚠ 提交规则**：仅在以下情况提交到 GitHub，其余情况等待用户指令：
- 重大功能完成（如新模块、新系统）
- 较大重构完成
- 修复 CI 失败

日常小改动、调试、提示词调优等一律不提交，等用户确认后再操作。

**⚠ 推送规则**：功能开发中优先本地保存，不做 `git push`：
```bash
git add -A
git commit -m "本地保存：xxx"   # 不加 --push
```

**⚠ 推送前强制自查**：
```bash
python -X utf8 scripts/preflight.py          # 全量: lint + mypy + 全测试 + 编码 + 自举
python -X utf8 scripts/preflight.py --quick  # 快速: 跳过自举
```

preflight 绿了 → `git push`。红了 → 修完再推。

**提交信息使用中文**。

**Git 配置**：`git config core.autocrlf input` 避免 CRLF 混入。

**版本号一致性**：推送前检查 `README.md`、`README_EN.md`、`docs/manual.md`、`docs/llvm.md`、`CHANGELOG.md` 中的版本号是否一致。

**CHANGELOG 约定**：功能写完就写条目，不要攒到一天结束。同一天的多次改动合并为一个版本号。
**CHANGELOG 模板**：每个版本必须包含 Summary 一行概括 + Highlights(3-4条) + 分类段落(Language/Compiler/VM/Build/Project Layout/Toolchain/CI；历史版本可含 Agent) + Bug Fixes + Metrics 表格。

## 测试

```bash
python -X utf8 scripts/preflight.py          # 包含全部测试
# 或单独：
python -X utf8 -m pytest tests/ -q          # 全量 ~2457 项
python -X utf8 tests/test_self_host.py -v   # 自举 3 项(含 Level 2+3)
python -X utf8 tests/test_vm.py -v          # VM 测试
python -X utf8 tests/test_sugar_san.py -v   # Sugar 语法测试
python -X utf8 tests/run_all.py             # 集成测试
```

## 代码约定

### 操作注册双语规则

每个 `ops/*.py` 文件必须同时注册中英文操作名：

```python
from ops.registry import register, register_alias as _ra

register('source', _source_op)
_ra('来源', 'source')
```

### 异常体系

使用 `values.py` 中的 `Sanyan*` 系列异常：`SanyanSyntaxError`、`SanyanTypeError`、`SanyanValueError`、`SanyanRuntimeError`、`SanyanNameError`、`SanyanKeyError`、`SanyanAttributeError`、`SanyanIOError`

### 全角符号

**绝对不能** 为了通过测试而将全角符号（`（` `）` `，` `；` 等）转换为半角。

### 注释

每次增加或修改代码，必须为整段代码写中文注释。

### 预处理

`#include` 展开统一使用 `preprocess.py` 中的 `preprocess_includes(code)` 函数。
