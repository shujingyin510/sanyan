"""文档自动同步脚本：在代码变更后更新 docs/manual.md 的关键表格。

用法: python doc_sync.py
"""
from __future__ import annotations
import re
import os


MANUAL_PATH = "docs/manual.md"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def sync_builtin_ops_table():
    """从 runtime.py:BUILTIN_OPS 同步命令速查表到 manual 第 17 节。"""
    runtime = _read("runtime.py")
    # 提取 BUILTIN_OPS 集合
    ops_match = re.search(r"BUILTIN_OPS\s*=\s*\{(.*?)\}", runtime, re.DOTALL)
    if not ops_match:
        return
    ops_text = ops_match.group(1)
    ops = re.findall(r"'([^']+)'", ops_text)

    manual = _read(MANUAL_PATH)
    # 找到第 17 节
    section_start = manual.find("## 17. 内置命令速查表")
    if section_start < 0:
        return
    # 找到表格开始
    table_start = manual.find("| `", section_start)
    if table_start < 0:
        return
    # 找到表格结束
    next_section = manual.find("## 1", table_start + 1)
    if next_section < 0:
        next_section = len(manual)

    # 检查每个操作是否出现在表格中
    missing = []
    for op in sorted(ops):
        if op not in manual[section_start:next_section]:
            missing.append(op)

    if missing:
        print(f"警告: BUILTIN_OPS 中有 {len(missing)} 个操作未出现在手册第 17 节:")
        for m in missing:
            print(f"  - {m}")
    else:
        print("BUILTIN_OPS 与第 17 节一致")


def sync_version():
    """将版本号从 CHANGELOG.md 同步到 README.md 和 docs/manual.md。"""
    changelog = _read("CHANGELOG.md")
    # 获取最新版本号
    ver_match = re.search(r"## \[(v[^\]]+)\]", changelog)
    if not ver_match:
        return
    version = ver_match.group(1)
    date_match = re.search(r"## \[v[^\]]+\] — (\S+)", changelog)
    date = date_match.group(1) if date_match else ""

    # 更新 README.md
    readme = _read("README.md")
    readme = re.sub(r"# 三言 Sanyan v[0-9.]+", f"# 三言 Sanyan {version}", readme)
    _write("README.md", readme)

    # 更新 docs/manual.md
    manual = _read(MANUAL_PATH)
    manual = re.sub(r"# 三言 v[0-9.]+ 语言手册", f"# 三言 {version} 语言手册", manual)
    manual = re.sub(
        r"文档版本: v[0-9.]+",
        f"文档版本: {version}",
        manual,
    )
    if date:
        manual = re.sub(
            r"更新日期: \S+",
            f"更新日期: {date}",
            manual,
        )
    _write(MANUAL_PATH, manual)
    print(f"版本同步: {version} ({date})")


def sync_error_table():
    """从 values.py 同步异常类到 manual 第 18 节。"""
    values = _read("values.py")
    errors = re.findall(r"class (Sanyan\w+Error)", values)

    manual = _read(MANUAL_PATH)
    section = manual.find("## 18. 错误信息说明")
    if section < 0:
        return

    missing = [e for e in errors if e not in manual[section:section + 2000]]
    if missing:
        print(f"警告: 以下异常未出现在第 18 节: {missing}")
    else:
        print("异常体系一致")


def main():
    print("=== 文档同步 ===")
    sync_version()
    sync_builtin_ops_table()
    sync_error_table()
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
