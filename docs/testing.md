# 测试体系

> 三言的测试架构：~2700 项 Python 测试 + 46 项 .san 集成测试。

## 测试分类

| 类别 | 测试文件 | 规模 |
|------|---------|------|
| 核心语言 | `test_core.py` `test_lang_core.py` `test_lang_core_ext.py` | ~2300 行 |
| 编译器/VM | `test_vm.py` `test_c_vm.py` `test_self_host.py` `test_llvmgen.py` | ~2200 行 |
| Ops | `test_ops.py` `test_ops_ext.py` `test_dispatcher.py` | ~1500 行 |
| Agent | `test_agent.py` `test_agent_v5.py` `test_agent_runtime.py` | ~3000 行 |
| 覆盖率提升 | `test_coverage_boost[1-8]` `test_edge_cases.py` | ~4000 行 |
| 模糊/差分 | `diff_fuzzer.py` `test_diff_fuzz.py` `test_fuzzing.py` | ~1200 行 |
| 其他 | `test_sanfmt.py` `test_lsp.py` `test_package.py` 等 | ~1500 行 |
| .san 集成 | `run_all.py` (46 项) | — |

## 运行方式

```bash
# 全量 Python 测试
python -X utf8 -m pytest tests/ -q

# 特定模块
python -X utf8 -m pytest tests/test_vm.py -v
python -X utf8 -m pytest tests/test_core.py -v
python -X utf8 -m pytest tests/test_self_host.py -v

# .san 集成测试
python -X utf8 tests/run_all.py

# 差分模糊测试（四后端一致性）
python -X utf8 tests/test_diff_fuzz.py
```

## 自举测试

```bash
# Level 0-3 验证
python -X utf8 tests/test_self_host.py -v

# Sugar 自举验证 (SHA256)
python -X utf8 tests/test_sugar_self_host.py -v
```

## .san 集成测试

46 个 .san 文件，每个有 `_se`（S-表达式）和 sugar 语法两个版本，并行执行。

**排除规则**：`tests/run_all.py` 的 `EXCLUDE_TESTS` 集合可临时跳过预存问题测试。

## C VM 测试

```bash
# C VM 测试（自动编译 + 运行）
python -X utf8 -m pytest tests/test_c_vm.py -v
```

`setUpClass` 编译一次 C VM 复用（116s → 33s）。

## 编码检查

```bash
# UTF-8 / CRLF 检查（preflight 中自动运行）
python -X utf8 scripts/preflight.py --quick
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `tests/test_self_host.py` | 自举 Level 0-3 |
| `tests/test_vm.py` | VM 测试 (91项) |
| `tests/test_c_vm.py` | C VM 测试 |
| `tests/test_diff_fuzz.py` | 四后端差分 |
| `tests/run_all.py` | .san 集成测试 |
| `scripts/preflight.py` | 全量检查入口 |
| `docs/bootstrap.md` | 自举链文档 |
| `docs/vm-architecture.md` | VM 架构文档 |
