"""文档自动同步脚本：在代码变更后更新 docs/ 的关键表格。

用法: python doc_sync.py
"""

from __future__ import annotations
import os
import re


MANUAL_PATH = 'docs/manual.md'
COMMANDS_PATH = 'docs/commands.md'
ERRORS_PATH = 'docs/manual.md'  # 错误表已合并到统一手册

# 需要检查版本号的文件及其版本号所在行的正则模式
VERSION_FILES = {
    'README.md': r'# 三言 Sanyan v([\d.]+)',
    'README_EN.md': r'# Sanyan v([\d.]+)',
    'docs/manual.md': r'# 三言 v([\d.]+) 语言手册',
    'docs/llvm.md': r'# 三言 LLVM 代码生成器 v([\d.]+)',
}


def _read(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _write(path: str, content: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def _get_canonical_version() -> str:
    """从 sanyan/__init__.py 读取权威版本号。"""
    init = _read('sanyan/__init__.py')
    m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", init)
    return m.group(1) if m else '0.0.0'


def _guess_syntax(op: str) -> str:
    """为缺失的内置操作猜测合理的语法列内容。"""
    return f'`{op}(…)`'


def _guess_description(op: str) -> str:
    """为缺失的内置操作猜测合理的说明列内容。"""
    return f'内置操作（{op}）'


def check_version_consistency() -> bool:
    """检查所有 md 文件中的版本号是否与 sanyan/__init__.py 一致。

    Returns:
        True 表示全部一致，False 表示有不一致。
    """
    canonical = _get_canonical_version()
    print(f'权威版本: v{canonical}')
    ok = True

    for filepath, pattern in VERSION_FILES.items():
        if not os.path.exists(filepath):
            continue
        content = _read(filepath)
        # 只检查文件开头的标题行（前 3 行）
        header = '\n'.join(content.split('\n')[:3])
        m = re.search(pattern, header)
        if m:
            found_ver = m.group(1)
            if found_ver != canonical:
                print(f'  版本不一致: {filepath} = v{found_ver} (应为 v{canonical})')
                ok = False
        # 检查 CHANGELOG 最新条目
    changelog = _read('CHANGELOG.md')
    m = re.search(r'## \[(v[^\]]+)\]', changelog)
    if m:
        changelog_ver = m.group(1).lstrip('v')
        if changelog_ver != canonical:
            print(f'  CHANGELOG 最新条目: v{changelog_ver} (应为 v{canonical})')
            ok = False

    if ok:
        print('版本号全部一致')
    return ok


def fix_version_consistency() -> None:
    """将所有 md 文件的版本号同步为 sanyan/__init__.py 的版本。"""
    canonical = _get_canonical_version()
    print(f'同步版本号: v{canonical}')

    for filepath, pattern in VERSION_FILES.items():
        if not os.path.exists(filepath):
            continue
        content = _read(filepath)
        lines = content.split('\n')
        # 只修改前 3 行中的版本号
        changed = False
        for i in range(min(3, len(lines))):
            new_line = re.sub(r'v[\d.]+(?!.*\d{4})', f'v{canonical}', lines[i])
            if new_line != lines[i]:
                lines[i] = new_line
                changed = True
        if changed:
            _write(filepath, '\n'.join(lines))
            print(f'  已更新: {filepath}')


def sync_builtin_ops_table():
    """从 core/runtime.py:BUILTIN_OPS 同步命令速查表到 docs/commands.md。"""
    runtime = _read('core/runtime.py')
    ops_match = re.search(r'BUILTIN_OPS\s*=\s*\{(.*?)\}', runtime, re.DOTALL)
    if not ops_match:
        return
    ops_text = ops_match.group(1)
    ops = re.findall(r"'([^']+)'", ops_text)

    manual = _read(COMMANDS_PATH)
    table_start = manual.find('| `')
    if table_start < 0:
        return
    section_end = manual.find('\n\n', table_start)
    while section_end > 0 and (
        manual[section_end : section_end + 3] in ('\n| ', '\n|`') or manual[section_end + 1 : section_end + 2] == '|'
    ):
        section_end = manual.find('\n\n', section_end + 1)
    if section_end < 0:
        section_end = len(manual)

    table_lines = manual[table_start:section_end].split('\n')
    table_cmds = set()
    for line in table_lines:
        line_stripped = line.strip()
        if line_stripped.startswith('|'):
            parts = line_stripped.split('|')
            if len(parts) >= 2:
                cell = parts[1].strip()
                m = re.match(r'`([^`]+)`', cell)
                if m:
                    table_cmds.add(m.group(1))

    missing = []
    for op in sorted(ops):
        if op not in table_cmds:
            missing.append(op)
    extra = [c for c in sorted(table_cmds) if c not in ops]

    if missing:
        print(f'警告: BUILTIN_OPS 中有 {len(missing)} 个操作未出现在命令速查表:')
        for m in missing:
            print(f'  - {m}')
    elif extra:
        print(f'注意: 命令速查表中有 {len(extra)} 个条目不在 BUILTIN_OPS 中:')
        for e in extra:
            print(f'  - {e}')
    else:
        print('BUILTIN_OPS 与命令速查表一致')


def sync_version():
    """将版本号从 CHANGELOG.md 同步到 README.md 和 docs/manual.md。"""
    changelog = _read('CHANGELOG.md')
    # 获取最新版本号
    ver_match = re.search(r'## \[(v[^\]]+)\]', changelog)
    if not ver_match:
        return
    version = ver_match.group(1)
    date_match = re.search(r'## \[v[^\]]+\] — (\S+)', changelog)
    date = date_match.group(1) if date_match else ''

    # 更新 README.md
    readme = _read('README.md')
    readme = re.sub(r'# 三言 Sanyan v[0-9.]+', f'# 三言 Sanyan {version}', readme)
    _write('README.md', readme)

    # 更新 docs/manual.md
    manual = _read(MANUAL_PATH)
    manual = re.sub(r'# 三言 v[0-9.]+ 语言手册', f'# 三言 {version} 语言手册', manual)
    manual = re.sub(
        r'文档版本: v[0-9.]+',
        f'文档版本: {version}',
        manual,
    )
    if date:
        manual = re.sub(
            r'更新日期: \S+',
            f'更新日期: {date}',
            manual,
        )
    _write(MANUAL_PATH, manual)
    print(f'版本同步: {version} ({date})')


def sync_error_table():
    """从 core/values.py 同步异常类到 docs/errors.md。"""
    values = _read('core/values.py')
    errors = re.findall(r'class (Sanyan\w+Error)', values)

    doc = _read(ERRORS_PATH)
    missing = [e for e in errors if e not in doc]
    if missing:
        print(f'警告: 以下异常未出现在文档中: {missing}')
    else:
        print('异常体系一致')


def main():
    print('=== 文档同步 ===')
    check_version_consistency()
    fix_version_consistency()
    sync_builtin_ops_table()
    sync_error_table()
    print('=== 完成 ===')


if __name__ == '__main__':
    main()
    exit(0)
