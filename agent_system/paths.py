"""统一的 Agent 数据目录 / DB 路径解析。

把"DB 落在哪"从各模块的 `ROOT` 里解耦出来。问题背景：有的模块 `ROOT` 指仓库根、
有的指 `agent_system/`，而 `ROOT` 还兼作源码定位 / 子进程 cwd，于是同名 `.db`
会散落在两个目录、造成状态分裂。本模块给出唯一的规范目录，DB 路径只认它。

规范目录优先级：环境变量 `AGENT_DATA_DIR` > 本文件所在目录（`agent_system/`）。
"""

from __future__ import annotations

import os

_DEFAULT_DIR = os.path.dirname(os.path.abspath(__file__))


def data_dir() -> str:
    """返回 Agent 持久化数据的规范目录（不存在则创建）。"""
    d = os.environ.get('AGENT_DATA_DIR', '').strip() or _DEFAULT_DIR
    os.makedirs(d, exist_ok=True)
    return d


def db_path(name: str) -> str:
    """返回规范目录下某个 DB 文件的完整路径。"""
    return os.path.join(data_dir(), name)
