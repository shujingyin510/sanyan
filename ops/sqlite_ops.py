"""SQLite 操作 — 内置数据库支持

提供操作：
  - sqlite_open(path) — 打开数据库连接
  - sqlite_close(conn) — 关闭连接
  - sqlite_exec(conn, sql) — 执行 SQL（无返回值）
  - sqlite_query(conn, sql) — 查询 SQL（返回列表）
  - sqlite_tables(conn) — 列出所有表
  - sqlite_schema(conn, table) — 获取表结构
"""

import os
import sqlite3
from typing import Any, Dict
from ops.registry import register, register_alias
from ternary_core import TritValue
from values import SanyanValueError, SanyanTypeError, SanyanRuntimeError

# 连接缓存
_connections: Dict[str, sqlite3.Connection] = {}


def _to_python(value):
    """将 TritValue 转换为 Python 原生类型"""
    if isinstance(value, TritValue):
        if value.is_numeric():
            return value.to_int() if value.float_val is None else value.to_float()
        elif value.is_string():
            return str(value.value)
        else:
            return str(value)
    return value


def _get_conn(path: str) -> sqlite3.Connection:
    """获取或创建数据库连接"""
    # 去除引号
    path = path.strip('"').strip("'")
    abs_path = os.path.abspath(path)
    if abs_path not in _connections:
        _connections[abs_path] = sqlite3.connect(abs_path)
        _connections[abs_path].row_factory = sqlite3.Row
    return _connections[abs_path]


def _close_conn(path: str):
    """关闭数据库连接"""
    # 去除引号
    path = path.strip('"').strip("'")
    abs_path = os.path.abspath(path)
    if abs_path in _connections:
        _connections[abs_path].close()
        del _connections[abs_path]


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """将 sqlite3.Row 转为字典"""
    return {key: row[key] for key in row.keys()}


# ── 操作实现 ──


def _sqlite_open(evaluator, args):
    """打开数据库连接

    用法: (sqlite_open "path/to/db.sqlite")
    返回: 数据库路径（字符串）
    """
    if len(args) < 1:
        raise SanyanValueError('sqlite_open 需要 1 个参数: 数据库路径')
    path = str(evaluator.eval(args[0])).strip('"').strip("'")
    _get_conn(path)
    return path


def _sqlite_close(evaluator, args):
    """关闭数据库连接

    用法: (sqlite_close "path/to/db.sqlite")
    """
    if len(args) < 1:
        raise SanyanValueError('sqlite_close 需要 1 个参数: 数据库路径')
    path = str(evaluator.eval(args[0])).strip('"').strip("'")
    _close_conn(path)
    return 0


def _sqlite_exec(evaluator, args):
    """执行 SQL（无返回值）

    用法: (sqlite_exec "path/to/db.sqlite" "CREATE TABLE ...")
    返回: 影响行数
    """
    if len(args) < 2:
        raise SanyanValueError('sqlite_exec 需要 2 个参数: 数据库路径, SQL语句')
    path = str(evaluator.eval(args[0])).strip('"').strip("'")
    sql = str(evaluator.eval(args[1])).strip('"').strip("'")
    conn = _get_conn(path)
    try:
        cursor = conn.execute(sql)
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        raise SanyanRuntimeError(f'SQLite 执行错误: {e}')


def _sqlite_query(evaluator, args):
    """查询 SQL（返回列表）

    用法: (sqlite_query "path/to/db.sqlite" "SELECT * FROM table")
    返回: 字典列表
    """
    if len(args) < 2:
        raise SanyanValueError('sqlite_query 需要 2 个参数: 数据库路径, SQL语句')
    path = str(evaluator.eval(args[0])).strip('"').strip("'")
    sql = str(evaluator.eval(args[1])).strip('"').strip("'")
    conn = _get_conn(path)
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        return [_row_to_dict(row) for row in rows]
    except sqlite3.Error as e:
        raise SanyanRuntimeError(f'SQLite 查询错误: {e}')


def _sqlite_tables(evaluator, args):
    """列出所有表

    用法: (sqlite_tables "path/to/db.sqlite")
    返回: 表名列表
    """
    if len(args) < 1:
        raise SanyanValueError('sqlite_tables 需要 1 个参数: 数据库路径')
    path = str(evaluator.eval(args[0])).strip('"').strip("'")
    conn = _get_conn(path)
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise SanyanRuntimeError(f'SQLite 查询错误: {e}')


def _sqlite_schema(evaluator, args):
    """获取表结构

    用法: (sqlite_schema "path/to/db.sqlite" "table_name")
    返回: 列信息列表
    """
    if len(args) < 2:
        raise SanyanValueError('sqlite_schema 需要 2 个参数: 数据库路径, 表名')
    path = str(evaluator.eval(args[0])).strip('"').strip("'")
    table = str(evaluator.eval(args[1])).strip('"').strip("'")
    conn = _get_conn(path)
    try:
        cursor = conn.execute(f'PRAGMA table_info({table})')
        columns = []
        for row in cursor.fetchall():
            columns.append(
                {
                    'name': row[1],
                    'type': row[2],
                    'notnull': bool(row[3]),
                    'default': row[4],
                    'pk': bool(row[5]),
                }
            )
        return columns
    except sqlite3.Error as e:
        raise SanyanRuntimeError(f'SQLite 查询错误: {e}')


def _sqlite_insert(evaluator, args):
    """插入数据

    用法: (sqlite_insert "path/to/db.sqlite" "table_name" (dict "col1" "val1" "col2" "val2"))
    返回: 插入行的 rowid
    """
    if len(args) < 3:
        raise SanyanValueError('sqlite_insert 需要 3 个参数: 数据库路径, 表名, 数据字典')
    path = str(evaluator.eval(args[0])).strip('"').strip("'")
    table = str(evaluator.eval(args[1])).strip('"').strip("'")
    data = evaluator.eval(args[2])

    if not isinstance(data, dict):
        raise SanyanTypeError(f'sqlite_insert 的第3个参数必须是字典，得到: {type(data)}')

    # 清理字典值中的引号
    clean_data = {}
    for k, v in data.items():
        key = str(k).strip('"').strip("'")
        val = _to_python(v)
        if isinstance(val, str):
            val = val.strip('"').strip("'")
        clean_data[key] = val

    columns = ', '.join(clean_data.keys())
    placeholders = ', '.join(['?'] * len(clean_data))
    sql = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'

    conn = _get_conn(path)
    try:
        cursor = conn.execute(sql, list(clean_data.values()))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        raise SanyanRuntimeError(f'SQLite 插入错误: {e}')


def _sqlite_update(evaluator, args):
    """更新数据

    用法: (sqlite_update "path/to/db.sqlite" "table_name" (dict "col1" "val1") "WHERE id=1")
    返回: 影响行数
    """
    if len(args) < 4:
        raise SanyanValueError('sqlite_update 需要 4 个参数: 数据库路径, 表名, 数据字典, WHERE条件')
    path = str(evaluator.eval(args[0])).strip('"').strip("'")
    table = str(evaluator.eval(args[1])).strip('"').strip("'")
    data = evaluator.eval(args[2])
    where = str(evaluator.eval(args[3])).strip('"').strip("'")

    if not isinstance(data, dict):
        raise SanyanTypeError(f'sqlite_update 的第3个参数必须是字典，得到: {type(data)}')

    # 清理字典值中的引号
    clean_data = {}
    for k, v in data.items():
        key = str(k).strip('"').strip("'")
        val = _to_python(v)
        if isinstance(val, str):
            val = val.strip('"').strip("'")
        clean_data[key] = val

    set_clause = ', '.join([f'{k} = ?' for k in clean_data.keys()])
    sql = f'UPDATE {table} SET {set_clause} {where}'

    conn = _get_conn(path)
    try:
        cursor = conn.execute(sql, list(clean_data.values()))
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        raise SanyanRuntimeError(f'SQLite 更新错误: {e}')


def _sqlite_delete(evaluator, args):
    """删除数据

    用法: (sqlite_delete "path/to/db.sqlite" "table_name" "WHERE id=1")
    返回: 影响行数
    """
    if len(args) < 3:
        raise SanyanValueError('sqlite_delete 需要 3 个参数: 数据库路径, 表名, WHERE条件')
    path = str(evaluator.eval(args[0])).strip('"').strip("'")
    table = str(evaluator.eval(args[1])).strip('"').strip("'")
    where = str(evaluator.eval(args[2])).strip('"').strip("'")

    sql = f'DELETE FROM {table} {where}'

    conn = _get_conn(path)
    try:
        cursor = conn.execute(sql)
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        raise SanyanRuntimeError(f'SQLite 删除错误: {e}')


def _sqlite_count(evaluator, args):
    """统计行数

    用法: (sqlite_count "path/to/db.sqlite" "table_name")
    返回: 行数
    """
    if len(args) < 2:
        raise SanyanValueError('sqlite_count 需要 2 个参数: 数据库路径, 表名')
    path = str(evaluator.eval(args[0])).strip('"').strip("'")
    table = str(evaluator.eval(args[1])).strip('"').strip("'")

    conn = _get_conn(path)
    try:
        cursor = conn.execute(f'SELECT COUNT(*) FROM {table}')
        return cursor.fetchone()[0]
    except sqlite3.Error as e:
        raise SanyanRuntimeError(f'SQLite 查询错误: {e}')


# ── 注册操作 ──

register('sqlite_open', _sqlite_open)
register('sqlite_close', _sqlite_close)
register('sqlite_exec', _sqlite_exec)
register('sqlite_query', _sqlite_query)
register('sqlite_tables', _sqlite_tables)
register('sqlite_schema', _sqlite_schema)
register('sqlite_insert', _sqlite_insert)
register('sqlite_update', _sqlite_update)
register('sqlite_delete', _sqlite_delete)
register('sqlite_count', _sqlite_count)

# 中文别名
register_alias('数据库打开', 'sqlite_open')
register_alias('数据库关闭', 'sqlite_close')
register_alias('数据库执行', 'sqlite_exec')
register_alias('数据库查询', 'sqlite_query')
register_alias('数据库表列表', 'sqlite_tables')
register_alias('数据库表结构', 'sqlite_schema')
register_alias('数据库插入', 'sqlite_insert')
register_alias('数据库更新', 'sqlite_update')
register_alias('数据库删除', 'sqlite_delete')
register_alias('数据库计数', 'sqlite_count')
