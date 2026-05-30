"""构建合并 .san 文件。

将带有 #include 指令的拆分 .san 文件合并为单文件，
确保 VM 可直接编译（无需 Python 预处理）。

用法:
    python build_combined.py                    # 重建所有合并文件
    python build_combined.py stdlib/llvmgen.san # 重建指定文件
"""

import os
import sys
import re

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 需要合并的源文件 → 输出文件
BUILD_TARGETS = {
    'stdlib/llvmgen_src.san': 'stdlib/llvmgen.san',
}


def expand_includes(filepath: str, seen: set | None = None, base_dir: str | None = None) -> str:
    """展开 #include 指令，递归内联文件内容。

    Args:
        filepath: 主文件路径
        seen: 已处理文件集合（防循环引用）
        base_dir: 相对路径基准目录

    Returns:
        展开后的完整源码
    """
    if seen is None:
        seen = set()
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(filepath))

    abs_path = os.path.abspath(filepath)
    if abs_path in seen:
        raise ValueError(f'循环 #include: {filepath}')
    seen.add(abs_path)

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f'文件不存在: {filepath}')

    with open(abs_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    result = []
    for line in lines:
        stripped = line.strip()
        # 匹配 #include "path" 或 ＃include "path"
        m = re.match(r'^[#＃]include\s+["\'](.+?)["\']', stripped)
        if m:
            inc_path = m.group(1)
            # 解析相对路径
            if not os.path.isabs(inc_path):
                inc_abs = os.path.normpath(os.path.join(base_dir, inc_path))
            else:
                inc_abs = inc_path

            if not os.path.exists(inc_abs):
                result.append(f'// #include "{inc_path}" — 文件不存在，已跳过\n')
                continue

            inc_dir = os.path.dirname(inc_abs)
            included = expand_includes(inc_abs, seen, inc_dir)
            result.append(f'// ── #include "{inc_path}" ──\n')
            result.append(included)
            result.append(f'// ── end #include "{inc_path}" ──\n')
        else:
            result.append(line)

    return ''.join(result)


def build_target(src_rel: str, out_rel: str) -> bool:
    """构建单个目标。

    Args:
        src_rel: 源文件相对路径（带 #include）
        out_rel: 输出文件相对路径（合并后）

    Returns:
        是否成功
    """
    src_path = os.path.join(PROJECT_ROOT, src_rel)
    out_path = os.path.join(PROJECT_ROOT, out_rel)

    if not os.path.exists(src_path):
        print(f'  跳过 {src_rel}（源文件不存在）')
        return False

    try:
        combined = expand_includes(src_path)
    except (ValueError, FileNotFoundError) as e:
        print(f'  错误 {src_rel}: {e}')
        return False

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(combined)

    lines = combined.count('\n')
    size = len(combined.encode('utf-8'))
    print(f'  {out_rel}: {lines} 行, {size} 字节')
    return True


def main():
    if len(sys.argv) > 1:
        # 只重建指定文件
        targets = {}
        for arg in sys.argv[1:]:
            arg = arg.replace('\\', '/')
            if arg in BUILD_TARGETS:
                targets[arg] = BUILD_TARGETS[arg]
            else:
                # 尝试查找
                for src, out in BUILD_TARGETS.items():
                    if out == arg or src == arg:
                        targets[src] = out
                        break
        if not targets:
            print(f'未找到匹配的目标: {sys.argv[1:]}')
            print(f'可用目标: {", ".join(BUILD_TARGETS.values())}')
            return 1
    else:
        targets = BUILD_TARGETS

    print('构建合并 .san 文件...')
    ok = 0
    for src, out in targets.items():
        if build_target(src, out):
            ok += 1

    print(f'完成: {ok}/{len(targets)} 成功')
    return 0 if ok == len(targets) else 1


if __name__ == '__main__':
    sys.exit(main())
