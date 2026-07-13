# 贡献指南 · Contributing to 三言 Sanyan

感谢参与！三言是一门内置三态逻辑（真/假/可能）的中文编程语言。本指南说明如何搭环境、写代码、跑测试、提 PR。

> English speakers: this project is developed primarily in Chinese, but PRs and issues in English are welcome. The workflow below applies equally.

---

## 1. 环境搭建

需要 **Python ≥ 3.12**。语言核心零第三方依赖，开发工具走 extras：

```bash
git clone https://github.com/shujingyin510/sanyan
cd sanyan
pip install -e .[dev]      # pytest / ruff / mypy / llvmgen / rich
```

- `pip install -e .[core]` —— 仅语言核心（解释器 + 标准库，零依赖）
- `pip install -e .[cli]`  —— CLI 终端渲染（rich；缺失时 CLI 自动降级纯文本）
- `pip install -e .[all]`  —— 全部功能

---

## 2. 代码风格

CI 会强制以下三关，本地请先自查：

```bash
ruff format .        # 单引号，行宽 120（配置见 pyproject [tool.ruff]）
ruff check .         # E/F/W
mypy .               # 渐进式 strict：core 模块已开 disallow_untyped_defs
```

约定：

- **单引号** 字符串（`ruff format` 会自动纠正）。
- 中文标识符、中文注释是本项目的常态，放心用。
- 新增算子请走 `ops/registry.py` 的 `register`/`register_alias`，别绕过分发表。
- 别引入第三方运行时依赖到语言核心；确需依赖的功能放 extras（见 `pyproject.toml`）。

---

## 3. 测试

测试是 `unittest` 风格，单文件可直接跑：

```bash
python -X utf8 tests/test_core.py -v
python -X utf8 tests/run_all.py            # 汇总跑
```

覆盖率（CI 阈值 `fail_under = 73`，配置在 **`.coveragerc`** 单一真源）：

```bash
python -m pytest tests/ --cov=. --cov-report=term-missing
```

要求：

- **新功能必须带测试**；改 bug 请附能复现的回归测试。
- 涉及运行时行为的改动，跑一遍相关测试文件贴出结果，别只靠类型检查。
- 低配机可一次只跑一个测试文件，无需并行。

---

## 4. 版本一致性

版本号真源是 `sanyan/__init__.py` 的 `__version__`。CI 用 `scripts/doc_sync.py` 校验各处版本一致：

```bash
python -X utf8 scripts/doc_sync.py
```

不要在多处硬编码版本号——CLI 等应从 `sanyan.__version__` 读取。

---

## 5. 提交与 PR

- 分支从 `main` 切出，一个 PR 聚焦一件事。
- Commit 信息讲清「做了什么 + 为什么」，中英不限。
- PR 请填写 `.github/PULL_REQUEST_TEMPLATE.md` 的清单。
- 面向用户的改动请更新 `CHANGELOG.md`（未发布的先进 `[Unreleased]`，避免版本号通胀）。
- 更多协作约定（自举链状态、代码规范）见 `docs/AGENTS.md`。

有疑问先开 issue 讨论再动手，能省下双方时间。🌱
