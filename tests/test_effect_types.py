"""效应类型测试：确定[X] / 不确定[X] 编译期与运行期校验

验证：
- parser 正确解析 确定[int] / 不确定[int] 语法
- check_type 正确校验信度阈值（>= 0.99）
- 编译期拒绝：不确定值 → 确定参数
- 运行期拒绝：低信度值 → 确定参数
- 子类型关系：确定[X] → 不确定[X] 允许，反之拒绝
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.ternary_core import TritValue
from core.values import SanyanTypeError, check_type


class TestCheckTypeEffect(unittest.TestCase):
    """check_type 对 确定/不确定 类型的运行期校验"""

    def test_certain_int_accepts_high_confidence(self):
        """确定[int] 接受信度 >= 0.99 的 TritValue"""
        val = TritValue(42, confidence=1.0)
        check_type(val, '确定[int]', 'x')  # 不应抛异常

    def test_certain_int_accepts_confidence_099(self):
        """确定[int] 接受信度 = 0.99 的 TritValue（边界值）"""
        val = TritValue(42, confidence=0.99)
        check_type(val, '确定[int]', 'x')  # 不应抛异常

    def test_certain_int_rejects_low_confidence(self):
        """确定[int] 拒绝信度 < 0.99 的 TritValue"""
        val = TritValue(42, confidence=0.8)
        with self.assertRaises(SanyanTypeError) as ctx:
            check_type(val, '确定[int]', 'x')
        self.assertIn('信度', str(ctx.exception))

    def test_certain_int_rejects_confidence_098(self):
        """确定[int] 拒绝信度 = 0.98 的 TritValue（边界值）"""
        val = TritValue(42, confidence=0.98)
        with self.assertRaises(SanyanTypeError):
            check_type(val, '确定[int]', 'x')

    def test_uncertain_int_accepts_any_confidence(self):
        """不确定[int] 接受任意信度的 TritValue"""
        for conf in [0.0, 0.3, 0.5, 0.8, 0.99, 1.0]:
            val = TritValue(42, confidence=conf)
            check_type(val, '不确定[int]', f'x_conf_{conf}')  # 不应抛异常

    def test_certain_str_accepts_string(self):
        """确定[str] 接受普通字符串（字符串无信度概念，视为确定）"""
        check_type('hello', '确定[str]', 's')  # 不应抛异常

    def test_certain_int_rejects_wrong_base_type(self):
        """确定[int] 拒绝非 int 类型"""
        with self.assertRaises(SanyanTypeError) as ctx:
            check_type('hello', '确定[int]', 'x')
        self.assertIn('int', str(ctx.exception))

    def test_uncertain_int_rejects_wrong_base_type(self):
        """不确定[int] 拒绝非 int 类型"""
        with self.assertRaises(SanyanTypeError):
            check_type('hello', '不确定[int]', 'x')

    def test_certain_str_rejects_wrong_type(self):
        """确定[str] 拒绝非 str 类型"""
        with self.assertRaises(SanyanTypeError):
            check_type(42, '确定[str]', 's')


class TestParserEffectType(unittest.TestCase):
    """sugar parser 对 确定/不确定 类型语法的解析"""

    def test_parse_fn_with_certain_param(self):
        """解析 定义 f (x: 确定[int]) -> int { ... }"""
        from sugar.parser import parse_code

        ast, _ = parse_code('定义 f (x: 确定[int]) -> int { 返回 x }')
        # 找到 fn 定义节点
        fn_node = self._find_fn(ast)
        self.assertIsNotNone(fn_node)
        param_types = fn_node[3] if len(fn_node) > 3 else {}
        self.assertEqual(param_types.get('x'), '确定[int]')

    def test_parse_fn_with_uncertain_param(self):
        """解析 定义 f (x: 不确定[int]) -> int { ... }"""
        from sugar.parser import parse_code

        ast, _ = parse_code('定义 f (x: 不确定[int]) -> int { 返回 x }')
        fn_node = self._find_fn(ast)
        self.assertIsNotNone(fn_node)
        param_types = fn_node[3] if len(fn_node) > 3 else {}
        self.assertEqual(param_types.get('x'), '不确定[int]')

    def test_parse_fn_with_certain_return(self):
        """解析 定义 f (x: int) -> 确定[int] { ... }"""
        from sugar.parser import parse_code

        ast, _ = parse_code('定义 f (x: int) -> 确定[int] { 返回 x }')
        fn_node = self._find_fn(ast)
        self.assertIsNotNone(fn_node)
        param_types = fn_node[3] if len(fn_node) > 3 else {}
        self.assertEqual(param_types.get('__return__'), '确定[int]')

    def test_parse_fn_with_uncertain_return(self):
        """解析 定义 f (x: int) -> 不确定[int] { ... }"""
        from sugar.parser import parse_code

        ast, _ = parse_code('定义 f (x: int) -> 不确定[int] { 返回 x }')
        fn_node = self._find_fn(ast)
        self.assertIsNotNone(fn_node)
        param_types = fn_node[3] if len(fn_node) > 3 else {}
        self.assertEqual(param_types.get('__return__'), '不确定[int]')

    def test_parse_fn_with_effect_combo(self):
        """解析 定义 f (x: 确定[int]) -> 不确定[int] { ... }"""
        from sugar.parser import parse_code

        ast, _ = parse_code('定义 f (x: 确定[int]) -> 不确定[int] { 返回 x }')
        fn_node = self._find_fn(ast)
        self.assertIsNotNone(fn_node)
        param_types = fn_node[3] if len(fn_node) > 3 else {}
        self.assertEqual(param_types.get('x'), '确定[int]')
        self.assertEqual(param_types.get('__return__'), '不确定[int]')

    def _find_fn(self, node):
        """递归查找 fn 定义节点"""
        if isinstance(node, list):
            if len(node) > 0 and node[0] == 'fn':
                return node
            for child in node:
                result = self._find_fn(child)
                if result:
                    return result
        return None


class TestSubtypeRelation(unittest.TestCase):
    """效应类型子类型关系：确定 → 不确定 允许，反之拒绝"""

    def test_certain_to_uncertain_allowed(self):
        """确定[X] 可以流向 不确定[X]（放宽）"""
        from core.type_checker import _matches

        self.assertTrue(_matches('确定[int]', '不确定[int]'))

    def test_uncertain_to_certain_rejected(self):
        """不确定[X] 不能流向 确定[X]（收紧）"""
        from core.type_checker import _matches

        self.assertFalse(_matches('不确定[int]', '确定[int]'))

    def test_certain_to_certain_allowed(self):
        """确定[X] 匹配 确定[X]"""
        from core.type_checker import _matches

        self.assertTrue(_matches('确定[int]', '确定[int]'))

    def test_uncertain_to_uncertain_allowed(self):
        """不确定[X] 匹配 不确定[X]"""
        from core.type_checker import _matches

        self.assertTrue(_matches('不确定[int]', '不确定[int]'))

    def test_certain_str_to_uncertain_str(self):
        """确定[str] → 不确定[str] 允许"""
        from core.type_checker import _matches

        self.assertTrue(_matches('确定[str]', '不确定[str]'))


class TestCompileTimeUncertainty(unittest.TestCase):
    """编译期不确定性检查：evaluator._is_uncertain_expr"""

    def test_literal_is_certain(self):
        """字面量视为确定"""
        from core.evaluator import SanyanEvaluator

        ev = SanyanEvaluator()
        self.assertFalse(ev._is_uncertain_expr(42))
        self.assertFalse(ev._is_uncertain_expr(3.14))
        self.assertFalse(ev._is_uncertain_expr('hello'))

    def test_high_confidence_trit_is_certain(self):
        """高信度 TritValue 视为确定"""
        from core.evaluator import SanyanEvaluator

        ev = SanyanEvaluator()
        self.assertFalse(ev._is_uncertain_expr(TritValue(42, confidence=1.0)))
        self.assertFalse(ev._is_uncertain_expr(TritValue(42, confidence=0.99)))

    def test_low_confidence_trit_is_uncertain(self):
        """低信度 TritValue 视为不确定"""
        from core.evaluator import SanyanEvaluator

        ev = SanyanEvaluator()
        self.assertTrue(ev._is_uncertain_expr(TritValue(42, confidence=0.5)))
        self.assertTrue(ev._is_uncertain_expr(TritValue(42, confidence=0.0)))

    def test_uncertain_function_return_is_uncertain(self):
        """返回类型标注 不确定[X] 的函数调用视为不确定"""
        from core.evaluator import SanyanEvaluator

        ev = SanyanEvaluator()
        # 定义一个返回不确定值的函数
        ev.eval(['fn', 'data_src', [], {'__return__': '不确定[int]'}, [42]])
        self.assertTrue(ev._is_uncertain_expr(['data_src']))

    def test_certain_function_return_is_certain(self):
        """返回类型标注 确定[X] 的函数调用视为确定"""
        from core.evaluator import SanyanEvaluator

        ev = SanyanEvaluator()
        ev.eval(['fn', 'safe_src', [], {'__return__': '确定[int]'}, [42]])
        self.assertFalse(ev._is_uncertain_expr(['safe_src']))

    def test_arithmetic_propagates_uncertainty(self):
        """算术运算传播不确定性：确定 + 不确定 → 不确定"""
        from core.evaluator import SanyanEvaluator

        ev = SanyanEvaluator()
        # 加 确定 不确定 → 不确定
        expr = ['add', 1, TritValue(2, confidence=0.5)]
        self.assertTrue(ev._is_uncertain_expr(expr))

    def test_arithmetic_certain_both(self):
        """算术运算：确定 + 确定 → 确定"""
        from core.evaluator import SanyanEvaluator

        ev = SanyanEvaluator()
        expr = ['add', 1, 2]
        self.assertFalse(ev._is_uncertain_expr(expr))


class TestEndToEndEffectType(unittest.TestCase):
    """端到端效应类型测试：evaluator 执行"""

    def test_certain_param_accepts_certain_value(self):
        """确定参数接受确定值"""
        from core.evaluator import SanyanEvaluator

        ev = SanyanEvaluator()
        # 定义要求确定参数的函数
        ev.eval(['fn', 'safe_op', ['x'], {'x': '确定[int]'}, ['add', 'x', 1]])
        # 调用：传入确定值
        result = ev.eval(['safe_op', 42])
        self.assertEqual(result if isinstance(result, int) else result.to_int(), 43)

    def test_certain_param_rejects_uncertain_value_compile_time(self):
        """确定参数拒绝不确定值（编译期）"""
        from core.evaluator import SanyanEvaluator
        from core.values import SanyanTypeError

        ev = SanyanEvaluator()
        # 定义返回不确定值的函数
        ev.eval(['fn', 'sensor', [], {'__return__': '不确定[int]'}, [TritValue(42, confidence=0.5)]])
        # 定义要求确定参数的函数
        ev.eval(['fn', 'safe_op', ['x'], {'x': '确定[int]'}, ['add', 'x', 1]])
        # 调用：传入不确定值 → 应抛 SanyanTypeError
        with self.assertRaises(SanyanTypeError) as ctx:
            ev.eval(['safe_op', ['sensor']])
        self.assertIn('确定[int]', str(ctx.exception))

    def test_uncertain_param_accepts_any_value(self):
        """不确定参数接受任意值"""
        from core.evaluator import SanyanEvaluator

        ev = SanyanEvaluator()
        ev.eval(['fn', 'flex_op', ['x'], {'x': '不确定[int]'}, ['add', 'x', 1]])
        # 传入确定值
        result = ev.eval(['flex_op', 42])
        self.assertEqual(result if isinstance(result, int) else result.to_int(), 43)
        # 传入不确定值
        result2 = ev.eval(['flex_op', TritValue(10, confidence=0.5)])
        self.assertEqual(result2 if isinstance(result2, int) else result2.to_int(), 11)

    def test_certain_return_check(self):
        """确定返回值校验：函数标注 确定[int] 但返回低信度值"""
        from core.evaluator import SanyanEvaluator
        from core.values import SanyanTypeError

        ev = SanyanEvaluator()
        # 定义标注 确定[int] 返回但实际返回低信度值的函数
        # body 直接传 TritValue（不额外包裹列表）
        ev.eval(['fn', 'bad_fn', [], {'__return__': '确定[int]'}, TritValue(42, confidence=0.5)])
        # 调用 → 应在返回值校验时抛 SanyanTypeError
        with self.assertRaises(SanyanTypeError) as ctx:
            ev.eval(['bad_fn'])
        self.assertIn('信度', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
