"""新功能测试：模式匹配、异步语法、宏系统"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluator import SanyanEvaluator
from core.skin import SkinManager
from sugar import SugarConverter


class TestPatternMatching(unittest.TestCase):
    """模式匹配测试"""

    def _eval(self, code):
        skin_mgr = SkinManager('chinese')
        env = SanyanEvaluator(skin_manager=skin_mgr)
        ast = SugarConverter.convert(code, skin_mgr)
        return env.eval(ast)

    def test_match_literal(self):
        """字面量匹配"""
        result = self._eval('(匹配 42 42 "是42" _ "不是")')
        self.assertEqual(result, '是42')

    def test_match_wildcard(self):
        """通配符匹配"""
        result = self._eval('(匹配 42 _ "通配")')
        self.assertEqual(result, '通配')

    def test_match_variable(self):
        """变量绑定"""
        result = self._eval('(匹配 42 n n)')
        # 结果可能是 TritValue 或 int
        self.assertEqual(int(str(result).split('（')[0]), 42)

    def test_match_no_match(self):
        """无匹配分支"""
        result = self._eval('(匹配 42 1 "一" 2 "二")')
        # 默认返回 0 (可能是 TritValue 或 int)
        self.assertIn(str(result), ['0', '0（三进制: 0）'])

    def test_match_multiple_branches(self):
        """多分支匹配"""
        code = """
        设 x = 2
        (匹配 x 1 "一" 2 "二" 3 "三" _ "其他")
        """
        result = self._eval(code)
        self.assertEqual(result, '二')


class TestAsyncSyntax(unittest.TestCase):
    """异步语法测试"""

    def _eval_sexpr(self, code):
        """使用 S-表达式解析器求值"""
        from core.lexer import tokenize
        from core.parser import parse

        skin_mgr = SkinManager('chinese')
        env = SanyanEvaluator(skin_manager=skin_mgr)
        tokens = tokenize(code)
        ast = parse(tokens)
        return env.eval(ast)

    def test_async_define(self):
        """异步定义"""
        code = '(做 (设 f (异步定义 (加 1 2))) (异步完成 f))'
        result = self._eval_sexpr(code)
        # 异步操作返回值
        self.assertIsNotNone(result)

    def test_parallel_block(self):
        """并行块"""
        code = '(并行块 (加 1 2) (加 3 4))'
        result = self._eval_sexpr(code)
        # 并行块返回结果列表
        self.assertIsNotNone(result)


class TestMacroSystem(unittest.TestCase):
    """宏系统测试"""

    def _eval_sexpr(self, code):
        """使用 S-表达式解析器求值"""
        from core.lexer import tokenize
        from core.parser import parse

        skin_mgr = SkinManager('chinese')
        env = SanyanEvaluator(skin_manager=skin_mgr)
        tokens = tokenize(code)
        ast = parse(tokens)
        return env.eval(ast)

    def test_defmacro(self):
        """定义宏"""
        code = '(定义宏 守护 (条件 体) (若 条件 体 (可能)))'
        result = self._eval_sexpr(code)
        self.assertEqual(result, '守护')

    def test_macro_list(self):
        """宏列表"""
        code = '(做 (定义宏 测试宏 (x) (加 x 1)) (宏列表))'
        result = self._eval_sexpr(code)
        self.assertIn('测试宏', result)


class TestTypeInference(unittest.TestCase):
    """类型推断测试"""

    def _eval(self, code):
        skin_mgr = SkinManager('chinese')
        env = SanyanEvaluator(skin_manager=skin_mgr)
        ast = SugarConverter.convert(code, skin_mgr)
        return env.eval(ast)

    def test_int_inference(self):
        """整数类型推断"""
        code = """
        设 x = 10
        x
        """
        result = self._eval(code)
        # 结果可能是 TritValue 或 int
        self.assertEqual(int(str(result).split('（')[0]), 10)

    def test_float_inference(self):
        """浮点类型推断"""
        code = """
        设 x = 3.14
        x
        """
        result = self._eval(code)
        # 结果可能是 TritValue 或 float
        result_float = float(str(result).split('（')[0])
        self.assertAlmostEqual(result_float, 3.14, places=2)

    def test_string_inference(self):
        """字符串类型推断"""
        code = """
        设 x = "hello"
        x
        """
        result = self._eval(code)
        self.assertEqual(result, 'hello')


if __name__ == '__main__':
    unittest.main()
