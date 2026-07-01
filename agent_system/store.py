"""单一存储层（阶段 2）：规范连接 + schema_version + 旧库**非破坏**迁移。

目标：把 agent 的持久化逐步并入单一 `agent.db`（同库多表，表名各异不冲突），并给每个
component 一个 schema 版本，便于将来加迁移钩子。

设计要点：
  * `connect()` 打开规范目录（`paths.db_path`，认 `AGENT_DATA_DIR`）下的 `agent.db`。
  * `_schema_version(component, version)` 记录各子系统的 schema 版本。
  * `adopt_legacy(conn, legacy_db, tables)` 把旧的独立 `.db` 里的表数据一次性搬进当前库
    —— **只在目标表为空时拷贝、且不删旧库**（可回滚）。

迁移策略：各 store 默认改连 `agent.db`；首次打开时若旧独立库存在，把历史数据拷过来。
旧库保留为回滚副本，确认无误后可手动删除。
"""

from __future__ import annotations

import os
import sqlite3
from typing import Iterable

from agent_system.paths import db_path

AGENT_DB = 'agent.db'


def _ensure_version_table(conn: sqlite3.Connection) -> None:
    conn.execute('CREATE TABLE IF NOT EXISTS _schema_version ( component TEXT PRIMARY KEY, version INTEGER NOT NULL)')


def connect(name: str = AGENT_DB) -> sqlite3.Connection:
    """打开规范目录下的库（默认单一 agent.db），并保证版本表存在。"""
    conn = sqlite3.connect(db_path(name))
    _ensure_version_table(conn)
    conn.commit()
    return conn


def get_version(conn: sqlite3.Connection, component: str) -> int:
    _ensure_version_table(conn)
    row = conn.execute('SELECT version FROM _schema_version WHERE component=?', (component,)).fetchone()
    return int(row[0]) if row else 0


def set_version(conn: sqlite3.Connection, component: str, version: int) -> None:
    _ensure_version_table(conn)
    conn.execute(
        'INSERT INTO _schema_version(component, version) VALUES(?, ?) ON CONFLICT(component) DO UPDATE SET version=?',
        (component, version, version),
    )
    conn.commit()


def adopt_legacy(conn: sqlite3.Connection, legacy_db_name: str, tables: Iterable[str]) -> int:
    """把旧独立库 `legacy_db_name` 里 `tables` 的数据搬进当前库。

    仅当：旧库存在、旧库有该表、且**当前库该表为空**时才拷贝（避免覆盖新数据）。
    不删旧库。返回实际迁移的表数。
    """
    legacy = db_path(legacy_db_name)
    target = db_path(AGENT_DB)
    if not os.path.exists(legacy) or os.path.abspath(legacy) == os.path.abspath(target):
        return 0
    try:
        conn.execute('ATTACH DATABASE ? AS legacy', (legacy,))
    except sqlite3.Error:
        return 0
    migrated = 0
    try:
        for t in tables:
            has = conn.execute("SELECT name FROM legacy.sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()
            if not has:
                continue
            try:
                if conn.execute(f'SELECT COUNT(*) FROM main."{t}"').fetchone()[0]:
                    continue  # 当前库已有数据，跳过
            except sqlite3.Error:
                continue
            conn.execute(f'INSERT INTO main."{t}" SELECT * FROM legacy."{t}"')
            migrated += 1
        conn.commit()
    finally:
        conn.execute('DETACH DATABASE legacy')
    return migrated
