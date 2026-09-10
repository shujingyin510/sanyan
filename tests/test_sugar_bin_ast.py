"""糖解析契约：生产路径必须返回嵌套 AST（list/SrcNode），绝不是字符串。

背景
----
- roadmap 曾记「sugar.bin 返回字符串」。根因之一已修：`bytecode_compiler.san`
  把 `字列`（str_to_list）错映射到 `DICT_KEYS`，导致 sugar.bin 词法分析把整段
  源码收成一个「标识符」字符串。
- 生产解析路径（`ops/file_ops._parse_code`）优先 Python SugarConverter，
  已稳定返回 SrcNode AST；本文件锁住该契约。
- sugar.bin 经 VM 导出调用的词法仍有缺口（修复映射后仍可能把多字符源收成
  单 token），属自举次级路径；`_parse_with_sugar_san` 会在非 list 结果时
  回退 Python。缺口用 test_sugar_bin_vm_lex_gap 显式记录，不静默。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluator import SanyanEvaluator
from core.skin import SkinManager
from core.values import SrcNode
from ops.file_ops import (
    _load_sugar_from_bin,
    _parse_code,
    _parse_with_python_converter,
    _parse_with_sugar_san,
    clear_cache,
)


def _evaluator():
    return SanyanEvaluator(skin_manager=SkinManager('chinese'), max_loop_steps=500000)


def _leaves(node, path='$'):
    if isinstance(node, (list, SrcNode)):
        for i, x in enumerate(node):
            yield from _leaves(x, f'{path}[{i}]')
    else:
        yield path, type(node).__name__, node


def _normalize(node):
    if isinstance(node, (list, SrcNode)):
        return [_normalize(x) for x in node]
    return node


# 生产路径契约用例
_CASES = [
    '42',
    '"hello"',
    '设 x = 42',
    '输出(加(1, 2))',
    '若 (真) { 输出("hi") }',
    '若 (假) { 输出("a") } 否则 { 输出("b") }',
    '定义 f(a) { 返回(加(a, 1)) }',
    '循环 (i < 3) { 输出(i) }',
    '任务 t { 约束 { 许 网 } 输出("x") }',
    '设 a = 1\n设 b = 2\n输出(加(a, b))',
    '设 x = 42; 输出(x)',
]


class TestProductionParseReturnsAst(unittest.TestCase):
    """生产路径（_parse_code / Python SugarConverter）契约。"""

    @classmethod
    def setUpClass(cls):
        clear_cache()
        cls.e = _evaluator()

    def test_parse_code_never_string(self):
        for code in _CASES:
            with self.subTest(code=code):
                r = _parse_code(code, self.e)
                self.assertIsNotNone(r, f'解析失败: {code!r}')
                self.assertNotIsInstance(r, str)
                self.assertIsInstance(r, (list, SrcNode), f'非 AST: {type(r)} for {code!r}')

    def test_python_converter_never_string(self):
        for code in _CASES:
            with self.subTest(code=code):
                r = _parse_with_python_converter(code, self.e)
                self.assertIsNotNone(r, f'Python 路径失败: {code!r}')
                self.assertNotIsInstance(r, str)
                self.assertIsInstance(r, (list, SrcNode))

    def test_no_stringified_subtree(self):
        for code in _CASES:
            with self.subTest(code=code):
                r = _parse_code(code, self.e)
                for path, tname, val in _leaves(r):
                    if tname == 'str' and isinstance(val, str) and val.startswith('[') and val.endswith(']'):
                        self.fail(f'{code!r} 在 {path} 出现字符串化列表: {val!r}')

    def test_number_leaf_is_text(self):
        r = _parse_code('设 x = 42', self.e)
        leaves = list(_leaves(r))
        self.assertTrue(any(v == '42' for _, _, v in leaves), leaves)
        for path, tname, val in leaves:
            if isinstance(val, int):
                self.fail(f'{path} 出现 int 叶子 {val}')

    def test_sugar_san_fallback_always_ast(self):
        """_parse_with_sugar_san：无论 bin 路径成败，对外必须是 AST 或 None（回退）。"""
        for code in _CASES:
            with self.subTest(code=code):
                r = _parse_with_sugar_san(code, self.e)
                if r is None:
                    continue  # 回退/失败 → 调用方走 Python
                self.assertNotIsInstance(r, str, f'sugar 路径泄漏字符串: {code!r}')
                self.assertIsInstance(r, (list, SrcNode))


class TestSugarBinLoader(unittest.TestCase):
    def test_bin_loads_and_exports_parse(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bin_path = os.path.join(root, 'stdlib', 'sugar.bin')
        self.assertTrue(os.path.exists(bin_path))
        mod = _load_sugar_from_bin(bin_path)
        self.assertIsNotNone(mod)
        self.assertIn('解析', mod.exports)

    def test_sugar_bin_vm_lex_gap(self):
        """已知缺口（记录，不静默）：VM 导出词法仍可能把多字符源收成单 token。

        根因之一（字列→DICT_KEYS 错映射）已在 bytecode_compiler.san 修复并重编
        sugar.bin；若本用例变绿，说明 VM 词法已对齐，可删此记录并收紧契约。
        """
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bin_path = os.path.join(root, 'stdlib', 'sugar.bin')
        mod = _load_sugar_from_bin(bin_path)
        self.assertIsNotNone(mod)
        from core.evaluator import SanyanEvaluator as E

        temp = E(skin_manager=SkinManager('chinese'), max_loop_steps=500000)
        r = mod.call(temp, ['词法分析', '设 x = 42'])
        # 若已修复：应为多 token 列表；若仍缺口：单 token 且值为整段源码
        if isinstance(r, list) and len(r) >= 3:
            self.skipTest('sugar.bin VM 词法已对齐多 token——可删除本缺口记录')
        # 记录现状：单 token / 整段标识符
        self.assertIsInstance(r, list)
        if r:
            self.assertEqual(r[0][0], '标识符')


if __name__ == '__main__':
    unittest.main(verbosity=2)
