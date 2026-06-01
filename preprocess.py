"""预处理：统一处理 #include 指令展开

文件缓存：相同路径的 #include 不重复读取磁盘。
"""

import os
from typing import Optional
from values import SanyanValueError

# 文件内容缓存：abspath → content，避免重复磁盘读取
_include_cache: dict[str, str] = {}


def _resolve_include_path(raw_path: str, base_dir: Optional[str] = None) -> str:
    """解析 #include 路径，支持 ../ 相对路径。

    安全检查：最终绝对路径必须在项目根目录内。
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(base_dir)

    # 标准化路径：允许 ../ 但防止越界
    normalized = raw_path.replace('\\', '/')
    if not normalized.endswith('.san'):
        cand = os.path.join(project_root, 'stdlib', normalized + '.san')
        if os.path.exists(cand):
            return cand
    # 相对路径解析
    if os.sep not in normalized and not normalized.startswith('stdlib/'):
        cand = os.path.join(project_root, 'stdlib', normalized)
        if os.path.exists(cand):
            return cand
    # 允许 ../ 相对路径
    abspath = os.path.abspath(os.path.join(project_root, normalized))
    if not abspath.startswith(os.path.abspath(project_root)):
        raise SanyanValueError(f'#include 路径越界: {raw_path} -> {abspath}')
    return abspath


def _safe_include_path(raw_path: str) -> None:
    """验证 #include 路径安全（兼容旧接口）。"""
    _resolve_include_path(raw_path)


def clear_cache() -> None:
    """清空 #include 文件缓存（热重载或测试用）。"""
    _include_cache.clear()


def preprocess_includes(
    code: str, add_comment: bool = False, _seen: Optional[set] = None, _base_dir: Optional[str] = None
) -> str:
    """展开 #include 指令，将外部文件内容内联到代码中。

    Args:
        code: 源代码
        add_comment: 是否在展开内容前添加注释行标记
        _seen: 内部递归使用，检测循环引用
        _base_dir: 当前文件的目录（用于解析相对路径）

    Returns:
        展开后的源代码

    Raises:
        ValueError: 检测到循环 #include
    """
    if _seen is None:
        _seen = set()
    if _base_dir is None:
        _base_dir = os.path.dirname(os.path.abspath(__file__))
    lines = code.split('\n')
    processed = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#include') or stripped.startswith('＃include'):
            parts = stripped.split(None, 1)
            if len(parts) == 2:
                path = parts[1].strip('"').strip("'").strip('＂').strip('＇')
                try:
                    abspath = _resolve_include_path(path, _base_dir)
                except ValueError as e:
                    processed.append(f'／／ #include {path} ({e})')
                    continue
                if abspath in _seen:
                    raise SanyanValueError(f'检测到循环 #include: {path}')
                if os.path.exists(abspath):
                    if abspath in _include_cache:
                        included = _include_cache[abspath]
                    else:
                        try:
                            with open(abspath, 'r', encoding='utf-8') as f:
                                included = f.read()
                        except (IOError, OSError):
                            processed.append(f'／／ #include {path} (文件读取失败，已跳过)')
                            continue
                        _include_cache[abspath] = included
                    if add_comment:
                        processed.append(f'／／ #include {path}')
                    _seen.add(abspath)
                    # 递归展开时使用 included 文件所在目录作为 base_dir
                    included_dir = os.path.dirname(abspath)
                    processed.append(preprocess_includes(included, add_comment, _seen, included_dir))
                    _seen.discard(abspath)
                else:
                    processed.append(f'／／ #include {path} (文件不存在，已跳过)')
            else:
                processed.append(line)
        else:
            processed.append(line)
    return '\n'.join(processed)
