"""预处理：统一处理 #include 指令展开"""
import os
from typing import Optional


def _safe_include_path(raw_path: str) -> None:
    normalized = raw_path.replace('\\', '/')
    if '..' in normalized.split('/'):
        raise ValueError(f"#include 路径不允许包含 '..': {raw_path}")


def preprocess_includes(code: str, add_comment: bool = False,
                        _seen: Optional[set] = None) -> str:
    """展开 #include 指令，将外部文件内容内联到代码中。

    Args:
        code: 源代码
        add_comment: 是否在展开内容前添加注释行标记
        _seen: 内部递归使用，检测循环引用

    Returns:
        展开后的源代码

    Raises:
        ValueError: 检测到循环 #include
    """
    if _seen is None:
        _seen = set()
    lines = code.split('\n')
    processed = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#include') or stripped.startswith('＃include'):
            parts = stripped.split(None, 1)
            if len(parts) == 2:
                path = parts[1].strip('"').strip("'").strip('＂').strip('＇')
                _safe_include_path(path)
                if os.sep not in path and not path.endswith('.san'):
                    candidate = os.path.join('stdlib', path + '.san')
                    if os.path.exists(candidate):
                        path = candidate
                abspath = os.path.abspath(path)
                if abspath in _seen:
                    raise ValueError(f"检测到循环 #include: {path}")
                if os.path.exists(path):
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            included = f.read()
                    except (IOError, OSError):
                        processed.append(f'／／ #include {path} (文件读取失败，已跳过)')
                        continue
                    if add_comment:
                        processed.append(f'／／ #include {path}')
                    _seen.add(abspath)
                    processed.append(preprocess_includes(included, add_comment, _seen))
                    _seen.discard(abspath)
                else:
                    processed.append(f'／／ #include {path} (文件不存在，已跳过)')
            else:
                processed.append(line)
        else:
            processed.append(line)
    return '\n'.join(processed)
