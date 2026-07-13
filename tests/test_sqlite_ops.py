"""SQLite 算子测试 — 覆盖 ops/sqlite_ops.py 的增删改查、表结构与错误路径。

sqlite 算子只调用 evaluator.eval()，故用最小求值器（字面量原样返回）直接喂值，
配临时库跑真 SQL，覆盖建表 / 插入 / 查询 / 计数 / 更新 / 删除 / 表列表 / 表结构
以及缺参、坏 SQL、非字典等错误分支。
"""

import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ops import sqlite_ops
from core.ternary_core import TritValue
from core.values import SanyanValueError, SanyanTypeError, SanyanRuntimeError


class _E:
    """最小求值器：字面量原样返回（sqlite 算子只用 evaluator.eval）。"""

    def eval(self, x):
        return x


class TestSqliteOps(unittest.TestCase):
    def setUp(self):
        self.e = _E()
        self.tmpdir = tempfile.mkdtemp()
        self.db = os.path.join(self.tmpdir, 'test.db')
        sqlite_ops._sqlite_open(self.e, [self.db])
        sqlite_ops._sqlite_exec(
            self.e,
            [self.db, 'CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)'],
        )

    def tearDown(self):
        sqlite_ops._close_conn(self.db)
        try:
            shutil.rmtree(self.tmpdir)
        except OSError:
            pass

    def _insert(self, name, age):
        return sqlite_ops._sqlite_insert(self.e, [self.db, 'users', {'name': name, 'age': age}])

    # ── 正常路径 ──

    def test_open_returns_path(self):
        self.assertEqual(sqlite_ops._sqlite_open(self.e, [self.db]), self.db)

    def test_insert_and_count(self):
        rowid = self._insert('Alice', 30)
        self.assertIsInstance(rowid, int)
        self.assertEqual(sqlite_ops._sqlite_count(self.e, [self.db, 'users']), 1)

    def test_insert_accepts_tritvalue(self):
        # 覆盖 _to_python 的 TritValue 数值分支
        rowid = sqlite_ops._sqlite_insert(self.e, [self.db, 'users', {'name': 'Bob', 'age': TritValue(42)}])
        self.assertIsInstance(rowid, int)
        rows = sqlite_ops._sqlite_query(self.e, [self.db, "SELECT age FROM users WHERE name = 'Bob'"])
        self.assertEqual(rows[0]['age'], 42)

    def test_query_returns_dicts(self):
        self._insert('Alice', 30)
        rows = sqlite_ops._sqlite_query(self.e, [self.db, 'SELECT * FROM users'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'Alice')
        self.assertEqual(rows[0]['age'], 30)

    def test_tables_lists_created(self):
        self.assertIn('users', sqlite_ops._sqlite_tables(self.e, [self.db]))

    def test_schema_columns(self):
        cols = sqlite_ops._sqlite_schema(self.e, [self.db, 'users'])
        names = [c['name'] for c in cols]
        self.assertEqual(names, ['id', 'name', 'age'])
        pk = next(c for c in cols if c['name'] == 'id')
        self.assertTrue(pk['pk'])

    def test_update_changes_row(self):
        self._insert('Alice', 30)
        n = sqlite_ops._sqlite_update(self.e, [self.db, 'users', {'age': 31}, 'WHERE age = 30'])
        self.assertEqual(n, 1)
        rows = sqlite_ops._sqlite_query(self.e, [self.db, 'SELECT age FROM users'])
        self.assertEqual(rows[0]['age'], 31)

    def test_delete_removes_row(self):
        self._insert('Alice', 30)
        n = sqlite_ops._sqlite_delete(self.e, [self.db, 'users', 'WHERE age = 30'])
        self.assertEqual(n, 1)
        self.assertEqual(sqlite_ops._sqlite_count(self.e, [self.db, 'users']), 0)

    def test_delete_string_where(self):
        # 回归 _unquote 修复：以引号结尾的 WHERE 不再被削尾
        self._insert('Alice', 30)
        n = sqlite_ops._sqlite_delete(self.e, [self.db, 'users', "WHERE name = 'Alice'"])
        self.assertEqual(n, 1)
        self.assertEqual(sqlite_ops._sqlite_count(self.e, [self.db, 'users']), 0)

    def test_query_string_where(self):
        self._insert('Bob', 25)
        rows = sqlite_ops._sqlite_query(self.e, [self.db, "SELECT age FROM users WHERE name = 'Bob'"])
        self.assertEqual(rows[0]['age'], 25)

    def test_unquote_matched_pair_only(self):
        self.assertEqual(sqlite_ops._unquote('"x"'), 'x')
        self.assertEqual(sqlite_ops._unquote("'x'"), 'x')
        self.assertEqual(sqlite_ops._unquote("WHERE name = 'Alice'"), "WHERE name = 'Alice'")
        self.assertEqual(sqlite_ops._unquote('plain'), 'plain')

    def test_exec_returns_rowcount(self):
        n = sqlite_ops._sqlite_exec(self.e, [self.db, "INSERT INTO users (name, age) VALUES ('Carol', 25)"])
        self.assertEqual(n, 1)

    def test_close_returns_zero(self):
        self.assertEqual(sqlite_ops._sqlite_close(self.e, [self.db]), 0)

    # ── 错误路径 ──

    def test_open_missing_arg(self):
        with self.assertRaises(SanyanValueError):
            sqlite_ops._sqlite_open(self.e, [])

    def test_exec_missing_arg(self):
        with self.assertRaises(SanyanValueError):
            sqlite_ops._sqlite_exec(self.e, [self.db])

    def test_query_missing_arg(self):
        with self.assertRaises(SanyanValueError):
            sqlite_ops._sqlite_query(self.e, [self.db])

    def test_insert_missing_arg(self):
        with self.assertRaises(SanyanValueError):
            sqlite_ops._sqlite_insert(self.e, [self.db, 'users'])

    def test_update_missing_arg(self):
        with self.assertRaises(SanyanValueError):
            sqlite_ops._sqlite_update(self.e, [self.db, 'users', {'age': 1}])

    def test_delete_missing_arg(self):
        with self.assertRaises(SanyanValueError):
            sqlite_ops._sqlite_delete(self.e, [self.db, 'users'])

    def test_count_missing_arg(self):
        with self.assertRaises(SanyanValueError):
            sqlite_ops._sqlite_count(self.e, [self.db])

    def test_insert_non_dict(self):
        with self.assertRaises(SanyanTypeError):
            sqlite_ops._sqlite_insert(self.e, [self.db, 'users', 'not_a_dict'])

    def test_update_non_dict(self):
        with self.assertRaises(SanyanTypeError):
            sqlite_ops._sqlite_update(self.e, [self.db, 'users', 'not_a_dict', 'WHERE id=1'])

    def test_query_bad_sql(self):
        with self.assertRaises(SanyanRuntimeError):
            sqlite_ops._sqlite_query(self.e, [self.db, 'SELECT * FROM does_not_exist'])

    def test_exec_bad_sql(self):
        with self.assertRaises(SanyanRuntimeError):
            sqlite_ops._sqlite_exec(self.e, [self.db, 'THIS IS NOT SQL'])

    def test_tables_missing_arg(self):
        with self.assertRaises(SanyanValueError):
            sqlite_ops._sqlite_tables(self.e, [])

    def test_schema_missing_arg(self):
        with self.assertRaises(SanyanValueError):
            sqlite_ops._sqlite_schema(self.e, [self.db])


if __name__ == '__main__':
    unittest.main(verbosity=2)
