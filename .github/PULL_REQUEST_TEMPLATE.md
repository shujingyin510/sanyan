## 改动说明
<!-- 做了什么 + 为什么。关联 issue 用 Closes #123 -->

## 类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 文档 / 测试
- [ ] 重构 / 内部清理

## 自查清单
- [ ] `ruff format .` 与 `ruff check .` 通过
- [ ] `mypy .` 通过
- [ ] 相关测试通过（贴出跑的是哪些文件）；新功能/修复已带测试
- [ ] 未向语言核心引入第三方运行时依赖（如需依赖，已放入 `pyproject.toml` 的 extras）
- [ ] 面向用户的改动已更新 `CHANGELOG.md`（未发布的进 `[Unreleased]`）
- [ ] 若改动版本相关，已保持 `sanyan.__version__` 单一真源（`python scripts/doc_sync.py` 通过）

## 测试记录
<!-- 粘贴关键测试输出 -->

```
```
