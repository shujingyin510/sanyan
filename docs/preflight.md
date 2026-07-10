# 预检与 CI

> 推送前的质量门禁 + GitHub Actions 自动化。

## preflight.py

**文件**：`scripts/preflight.py` (406行)

推送前必须通过的 8 项检查：

| 检查项 | 说明 |
|--------|------|
| 1. ruff format | 代码格式化 |
| 2. ruff check | Lint 检查 |
| 3. mypy | 静态类型检查（0 errors 要求） |
| 4. pytest full | 全量 Python 测试 (~2700 项) |
| 5. path check | 大小写 / 反斜杠跨平台检测 |
| 6. self-host | 自举 Level 0-3 验证 |
| 7. diff fuzz | 四后端一致性差分模糊 |
| 8. encoding | UTF-8 / CRLF 编码检查 |

## 使用

```bash
# 全量检查
python -X utf8 scripts/preflight.py

# 快速模式（跳过自举 + 差分模糊）
python -X utf8 scripts/preflight.py --quick

# AGENTS.md 规定的推送前强制自查
ruff check . && ruff format --check . && mypy . && python -X utf8 scripts/preflight.py --quick
```

**规则**：preflight 绿了才能 push。

## CI 流水线

`.github/workflows/test.yml` — 每个 commit 触发：

```
push → ruff check + format → mypy → pytest full → preflight
```

## 环境配置

### LLVM 工具链（可选）

```bash
# Windows (MSYS2 + LLVM)
MSYS2_PATH=/d/msys64/usr
BASH_PATH=/d/msys64/usr/bin/bash.exe
GCC_PATH=/d/msys64/mingw64/bin/gcc.exe

# 或设置环境变量
set LLC_PATH=C:\Program Files\LLVM\bin\llc.exe
set SANYAN_CC=gcc
```

## 覆盖率

```bash
python -X utf8 -m pytest tests/ --cov=. --cov-report=term-missing
```

`.coveragerc` 配置了排除规则和 `fail_under = 73`。

## 相关文件

| 文件 | 说明 |
|------|------|
| `scripts/preflight.py` | 预检脚本 |
| `.github/workflows/test.yml` | GitHub Actions |
| `.coveragerc` | 覆盖率配置 |
| `pyproject.toml` | ruff/mypy 配置 |
| `docs/AGENTS.md` | 提交前强制自查规则 |
