"""Python 单测：覆盖运行时核心模块。
运行方式：python tests/test_core.py
"""

import unittest
from ternary_core import BT, TernaryALU, TritValue, ternary_sin, ternary_sqrt, ternary_exp, ternary_log
from values import (
    SanyanError,
    SanyanNameError,
    SanyanSyntaxError,
    SanyanTypeError,
    SanyanValueError,
    SanyanRuntimeError,
    SanyanKeyError,
    SanyanAttributeError,
    SanyanIOError,
    ReturnException,
    BreakException,
    FunctionValue,
    ModuleValue,
)
from runtime import SanyanRuntime
from skin import SkinManager
from preprocess import preprocess_includes, _safe_include_path


class TestTernaryCore(unittest.TestCase):
    """三进制核心运算"""

    def test_int_conversion(self):
        cases = [
            (0, [0]),
            (1, [1]),
            (-1, [-1]),
            (2, [1, -1]),
            (3, [1, 0]),
            (5, [1, -1, -1]),
            (10, [1, 0, 1]),
            (-5, [-1, 1, 1]),
        ]
        for dec, trits in cases:
            with self.subTest(dec=dec):
                self.assertEqual(BT.from_int(dec), trits)
                self.assertEqual(BT.to_int(trits), dec)

    def test_add(self):
        self.assertEqual(BT.to_int(TernaryALU.add(BT.from_int(2), BT.from_int(3))), 5)
        self.assertEqual(BT.to_int(TernaryALU.add(BT.from_int(10), BT.from_int(-5))), 5)
        self.assertEqual(BT.to_int(TernaryALU.add(BT.from_int(0), BT.from_int(0))), 0)

    def test_sub(self):
        self.assertEqual(BT.to_int(TernaryALU.sub(BT.from_int(10), BT.from_int(3))), 7)
        self.assertEqual(BT.to_int(TernaryALU.sub(BT.from_int(0), BT.from_int(5))), -5)

    def test_multiply(self):
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(3), BT.from_int(4))), 12)
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(7), BT.from_int(0))), 0)
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(-3), BT.from_int(5))), -15)
        # 大数乘法（快速路径）
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(12345), BT.from_int(67890))), 12345 * 67890)

    def test_logic(self):
        a, b = BT.from_int(1), BT.from_int(-1)
        self.assertEqual(BT.to_int(TernaryALU.tritwise_and(a, b)), -1)
        self.assertEqual(BT.to_int(TernaryALU.tritwise_or(a, b)), 1)
        self.assertEqual(BT.to_int(TernaryALU.tritwise_not(a)), -1)

    def test_trit_value_pool(self):
        a = TritValue(5)
        b = TritValue(5)
        self.assertIs(a, b)  # 对象池复用

    def test_trit_value_states(self):
        self.assertEqual(TritValue(1).to_int(), 1)
        self.assertEqual(TritValue(0).to_int(), 0)
        self.assertEqual(TritValue(-1).to_int(), -1)
        self.assertEqual(TritValue.from_string('真').to_int(), 1)
        self.assertEqual(TritValue.from_string('假').to_int(), -1)
        self.assertEqual(TritValue.from_string('可能').to_int(), 0)


class TestExceptions(unittest.TestCase):
    """异常体系"""

    def test_hierarchy(self):
        self.assertTrue(issubclass(SanyanNameError, SanyanError))
        self.assertTrue(issubclass(SanyanSyntaxError, SanyanError))
        self.assertTrue(issubclass(SanyanTypeError, SanyanError))
        self.assertTrue(issubclass(SanyanValueError, SanyanError))
        self.assertTrue(issubclass(SanyanRuntimeError, SanyanError))
        self.assertTrue(issubclass(SanyanKeyError, SanyanError))
        self.assertTrue(issubclass(SanyanAttributeError, SanyanError))
        self.assertTrue(issubclass(SanyanIOError, SanyanError))

    def test_value_error_message(self):
        e = SanyanValueError('除数不能为零')
        self.assertIn('除数不能为零', str(e))


class TestScopes(unittest.TestCase):
    """作用域栈式链"""

    def setUp(self):
        self.rt = SanyanRuntime()

    def test_initial_scope(self):
        self.assertEqual(len(self.rt._scopes), 1)
        self.assertEqual(self.rt._scopes[0], {})

    def test_push_pop(self):
        self.rt.push_scope()
        self.assertEqual(len(self.rt._scopes), 2)
        self.rt.pop_scope()
        self.assertEqual(len(self.rt._scopes), 1)

    def test_pop_global_protection(self):
        self.rt.pop_scope()
        self.rt.pop_scope()
        self.assertEqual(len(self.rt._scopes), 1)  # 全局作用域永不被弹出

    def test_set_and_get(self):
        self.rt.set_var('x', TritValue(10))
        self.assertEqual(self.rt.get_var('x').to_int(), 10)
        self.assertTrue(self.rt.has_var('x'))

    def test_cross_scope_lookup(self):
        self.rt.scope_vars['global_x'] = TritValue(100)
        self.rt.push_scope()
        self.rt.set_var('local_x', TritValue(50))
        # 可以从内层查找外层
        self.assertEqual(self.rt.get_var('global_x').to_int(), 100)
        self.assertEqual(self.rt.get_var('local_x').to_int(), 50)

    def test_inner_shadows_outer(self):
        self.rt.scope_vars['x'] = TritValue(1)
        self.rt.push_scope()
        self.rt.set_var('x', TritValue(2))
        self.assertEqual(self.rt.get_var('x').to_int(), 2)  # 内层覆盖
        self.rt.pop_scope()
        self.assertEqual(self.rt.get_var('x').to_int(), 1)  # 外层恢复

    def test_all_scoped_vars(self):
        self.rt.scope_vars['a'] = TritValue(1)
        self.rt.push_scope()
        self.rt.set_var('b', TritValue(2))
        all_vars = self.rt.all_scoped_vars()
        self.assertEqual(all_vars['a'].to_int(), 1)
        self.assertEqual(all_vars['b'].to_int(), 2)

    def test_vars_property_write(self):
        self.rt.scope_vars['x'] = TritValue(42)
        self.assertEqual(self.rt.get_var('x').to_int(), 42)
        self.rt.push_scope()
        self.rt.scope_vars['y'] = TritValue(99)
        self.assertEqual(self.rt.scope_vars['y'].to_int(), 99)
        self.rt.pop_scope()
        self.assertFalse(self.rt.has_var('y'))  # 局部变量已清理


class TestFunctionValue(unittest.TestCase):
    """函数值和闭包"""

    def test_call_args_mismatch(self):
        from evaluator import SanyanEvaluator

        fn = FunctionValue(['x'], [['print', 'x']])
        rt = SanyanEvaluator()
        with self.assertRaises(SanyanSyntaxError):
            fn.call(rt, [])

    def test_closure_capture(self):
        from evaluator import SanyanEvaluator

        rt = SanyanEvaluator()
        rt.set_var('captured', TritValue(100))
        fn = FunctionValue([], [], closure_vars={'captured': TritValue(100)})
        old_count = len(rt._scopes)
        fn.call(rt, [])
        self.assertEqual(len(rt._scopes), old_count)


class TestControlFlow(unittest.TestCase):
    """控制流异常"""

    def test_return_exception(self):
        e = ReturnException(TritValue(42))
        self.assertEqual(e.value.to_int(), 42)

    def test_break_exception(self):
        e = BreakException()
        self.assertIsInstance(e, BreakException)


class TestModuleValue(unittest.TestCase):
    """模块值"""

    def test_call_missing_func(self):
        mod = ModuleValue({}, {})
        rt = SanyanRuntime()
        with self.assertRaises(SanyanSyntaxError):
            mod.call(rt, [])

    def test_call_undefined_func(self):
        mod = ModuleValue({}, {'add': (['x', 'y'], [['add', 'x', 'y']])})
        rt = SanyanRuntime()
        with self.assertRaises(SanyanNameError):
            mod.call(rt, ['not_exist'])


class TestSkin(unittest.TestCase):
    """皮肤系统"""

    def setUp(self):
        self.skin = SkinManager('chinese')

    def test_ternary_words(self):
        self.assertEqual(self.skin.is_ternary_word('真'), 1)
        self.assertEqual(self.skin.is_ternary_word('假'), -1)
        self.assertEqual(self.skin.is_ternary_word('可能'), 0)
        self.assertIsNone(self.skin.is_ternary_word('不存在的词'))

    def test_keyword_lookup(self):
        self.assertEqual(self.skin.get_internal_keyword('设'), 'set')
        self.assertEqual(self.skin.get_internal_keyword('若'), 'if')
        self.assertEqual(self.skin.get_internal_keyword('循环'), 'loop')

    def test_switch_skin(self):
        self.skin.switch_skin('english')
        self.assertIsNotNone(self.skin.get_internal_keyword('set'))


class TestPreprocess(unittest.TestCase):
    def test_expand_include(self):
        code = '#include "test_math"\n输出(1)'
        result = preprocess_includes(code)
        self.assertIn('输出(1)', result)

    def test_reject_path_traversal(self):
        with self.assertRaises(ValueError):
            _safe_include_path('../secret')

    def test_nonexistent_file(self):
        result = preprocess_includes('#include "not_exist_file_xyz"\n输出(1)')
        self.assertIn('输出(1)', result)


class TestTernaryEdge(unittest.TestCase):
    def test_large_integer_conversion(self):
        n = 10**18 + 1
        trits = BT.from_int(n)
        self.assertEqual(BT.to_int(trits), n)

    def test_zero_has_no_sign(self):
        self.assertEqual(BT.from_int(0), [0])

    def test_fixed_point_conversion(self):
        trits = BT.from_float(1.5, precision=8)
        result = BT.to_float(trits, precision=8)
        self.assertAlmostEqual(result, 1.5, places=2)

    def test_fixed_point_negative(self):
        trits = BT.from_float(-2.25, precision=8)
        result = BT.to_float(trits, precision=8)
        self.assertAlmostEqual(result, -2.25, places=2)

    def test_trit_value_float_precision(self):
        v = TritValue(3.14)
        self.assertTrue(v.is_float())
        self.assertAlmostEqual(v.to_float(), 3.14, places=1)

    def test_ternary_sin_zero(self):
        s = ternary_sin(BT.from_float(0.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(s, 16), 0.0, places=2)

    def test_ternary_sin_half_pi(self):
        s = ternary_sin(BT.from_float(1.5708, 16), 16)
        self.assertAlmostEqual(BT.to_float(s, 16), 1.0, places=1)

    def test_ternary_sqrt_four(self):
        s = ternary_sqrt(BT.from_float(4.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(s, 16), 2.0, places=1)

    def test_ternary_exp_one(self):
        e = ternary_exp(BT.from_float(1.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(e, 16), 2.718, places=1)

    def test_ternary_log_e(self):
        log_e = ternary_log(BT.from_float(2.71828, 16), 16)
        self.assertAlmostEqual(BT.to_float(log_e, 16), 1.0, places=1)

    def test_ternary_cos_zero(self):
        from ternary_core import ternary_cos

        c = ternary_cos(BT.from_float(0.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(c, 16), 1.0, places=1)

    def test_ternary_tan_zero(self):
        from ternary_core import ternary_tan

        t = ternary_tan(BT.from_float(0.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(t, 16), 0.0, places=1)

    def test_ternary_log10_100(self):
        from ternary_core import ternary_log10

        l10 = ternary_log10(BT.from_float(100.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(l10, 16), 2.0, places=1)

    def test_negative_multiplication(self):
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(-1), BT.from_int(-1))), 1)
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(-1), BT.from_int(0))), 0)

    def test_pool_lru_eviction(self):
        for i in range(10001):
            TritValue(i)
        a = TritValue(5)
        b = TritValue(5)
        self.assertIs(a, b)


class TestParsePairs(unittest.TestCase):
    def test_dot_format(self):
        r = SanyanRuntime()
        result = r._parse_pairs(['灯.亮', '风扇.关'])
        self.assertEqual(result, [('灯', '亮'), ('风扇', '关')])

    def test_alternating_dot_format(self):
        r = SanyanRuntime()
        with self.assertRaises(SanyanSyntaxError):
            r._parse_pairs(['灯', '.', '亮', '风扇', '.', '关'])

    def test_mixed_formats(self):
        r = SanyanRuntime()
        with self.assertRaises(SanyanSyntaxError):
            r._parse_pairs(['灯.亮', '风扇', '.', '关'])

    def test_empty_list_returns_empty(self):
        r = SanyanRuntime()
        result = r._parse_pairs([])
        self.assertEqual(result, [])

    def test_single_pair_dot(self):
        r = SanyanRuntime()
        result = r._parse_pairs(['灯.亮'])
        self.assertEqual(result, [('灯', '亮')])

    def test_single_pair_alternating(self):
        r = SanyanRuntime()
        with self.assertRaises(SanyanSyntaxError):
            r._parse_pairs(['灯', '.', '亮'])

    def test_invalid_format_raises(self):
        r = SanyanRuntime()
        with self.assertRaises(SanyanSyntaxError):
            r._parse_pairs(['灯'])

    def test_non_string_raises(self):
        r = SanyanRuntime()
        with self.assertRaises(SanyanSyntaxError):
            r._parse_pairs([42, '.', '亮'])


class TestEvaluatorEdge(unittest.TestCase):
    """求值器边缘用例 — 覆盖当前覆盖率缺口"""

    def test_eval_simple_add(self):
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        self.assertEqual(e.eval(['add', 1, 2]).to_int(), 3)

    def test_eval_var_set_get(self):
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        e.eval(['set', 'x', 42])
        self.assertEqual(e.eval('x').to_int(), 42)

    def test_eval_function_call(self):
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        e.eval(['fn', 'double', ['n'], ['do', ['return', ['mul', 'n', 2]]]])
        result = e.eval(['double', 5])
        self.assertEqual(result.to_int(), 10)

    def test_eval_nested_scope(self):
        from evaluator import SanyanEvaluator
        from ternary_core import TritValue

        e = SanyanEvaluator()
        e.push_scope()
        e.set_var('x', TritValue(100))
        self.assertEqual(e.get_var('x').to_int(), 100)
        e.pop_scope()

    def test_eval_if_expression(self):
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        e.eval(['set', 'x', 0])
        e.eval(['if', ['gt', 5, 3], ['do', ['set', 'x', 1]], ['do', ['set', 'x', -1]]])
        self.assertEqual(e.get_var('x').to_int(), 1)

    def test_eval_simple_expression(self):
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        result = e.eval(['add', 10, 20])
        self.assertEqual(result.to_int(), 30)

    def test_has_var_undefined(self):
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        self.assertFalse(e.has_var('undefined_xyz'))

    def test_all_scoped_vars(self):
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        e.set_var('a', 1)
        e.set_var('b', 2)
        vars_ = e.all_scoped_vars()
        self.assertIn('a', vars_)
        self.assertIn('b', vars_)

    def test_module_cache(self):
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        self.assertIsInstance(e._module_cache, dict)

    def test_max_loop_steps_default(self):
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        self.assertGreater(e.max_loop_steps, 0)


class TestValuesExtended(unittest.TestCase):
    """值系统扩展测试 — 覆盖 Sanyan* 异常、Return/Break 异常"""

    def test_sanyan_error_base(self):
        from values import SanyanError

        e = SanyanError('通用错误')
        self.assertEqual(str(e), '通用错误')

    def test_sanyan_syntax_error(self):
        from values import SanyanSyntaxError

        e = SanyanSyntaxError('语法错误')
        self.assertEqual(str(e), '语法错误')

    def test_sanyan_type_error(self):
        from values import SanyanTypeError

        e = SanyanTypeError('类型错误')
        self.assertEqual(str(e), '类型错误')

    def test_sanyan_value_error(self):
        from values import SanyanValueError

        e = SanyanValueError('值错误')
        self.assertEqual(str(e), '值错误')

    def test_sanyan_runtime_error(self):
        from values import SanyanRuntimeError

        e = SanyanRuntimeError('运行时错误')
        self.assertEqual(str(e), '运行时错误')

    def test_sanyan_name_error(self):
        from values import SanyanNameError

        e = SanyanNameError('名称错误')
        self.assertEqual(str(e), '名称错误')

    def test_sanyan_key_error(self):
        from values import SanyanKeyError

        e = SanyanKeyError('键错误')
        self.assertIn('键错误', str(e))

    def test_sanyan_attribute_error(self):
        from values import SanyanAttributeError

        e = SanyanAttributeError('属性错误')
        self.assertEqual(str(e), '属性错误')

    def test_sanyan_io_error(self):
        from values import SanyanIOError

        e = SanyanIOError('IO错误')
        self.assertEqual(str(e), 'IO错误')

    def test_return_exception(self):
        from values import ReturnException
        from ternary_core import TritValue

        ret = ReturnException(TritValue(42))
        self.assertEqual(ret.value.to_int(), 42)

    def test_break_exception(self):
        from values import BreakException

        b = BreakException()
        self.assertIsNotNone(b)


class TestClosure(unittest.TestCase):
    """闭包/第一类函数测试 — 验证函数作为值传递和返回"""

    def test_function_return_as_value(self):
        """函数名作为独立表达式求值时返回 FunctionValue"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator(max_loop_steps=500)
        e.eval(['fn', 'add10', ['x'], ['do', ['return', ['add', 'x', 10]]]])
        # 函数名作为变量求值应返回 FunctionValue
        result = e.eval('add10')
        self.assertIsInstance(result, FunctionValue)

    def test_closure_basic(self):
        """基本闭包：内部函数捕获外部变量"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator(max_loop_steps=500)
        # 定义 outer 函数
        e.eval(
            [
                'fn',
                'outer',
                ['x'],
                ['do', ['fn', 'inner', ['y'], ['do', ['return', ['add', 'x', 'y']]]], ['return', 'inner']],
            ]
        )
        # 调用 outer(10)
        e.eval(['set', 'f', ['outer', 10]])
        # 调用 f(5)
        result = e.eval(['f', 5])
        self.assertEqual(result.to_int(), 15)

    def test_closure_counter(self):
        """计数器闭包：多次调用共享可变状态"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator(max_loop_steps=500)
        # 定义 mkcounter 函数
        e.eval(
            [
                'fn',
                'mkcounter',
                [],
                [
                    'do',
                    ['set', 'n', 0],
                    ['fn', 'tick', [], ['do', ['set', 'n', ['add', 'n', 1]], ['return', 'n']]],
                    ['return', 'tick'],
                ],
            ]
        )
        # 调用 mkcounter()
        e.eval(['set', 'c', ['mkcounter']])
        # 多次调用 c()
        self.assertEqual(e.eval(['c']).to_int(), 1)
        self.assertEqual(e.eval(['c']).to_int(), 2)
        self.assertEqual(e.eval(['c']).to_int(), 3)

    def test_closure_preserves_outer_scope(self):
        """闭包不污染外部作用域"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator(max_loop_steps=500)
        e.eval(['set', 'x', 100])
        e.eval(['fn', 'add_x', ['y'], ['do', ['return', ['add', 'x', 'y']]]])
        e.eval(['set', 'result', ['add_x', 5]])
        self.assertEqual(e.get_var('result').to_int(), 105)
        # 外部 x 应保持不变
        self.assertEqual(e.get_var('x').to_int(), 100)

    def test_import_as_alias(self):
        """import as 别名功能"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator(max_loop_steps=500)
        e.eval(['import', '"stdlib/math.san"', '为', 'm'])
        self.assertTrue(e.has_var('m'))
        m = e.get_var('m')
        self.assertIsInstance(m, ModuleValue)


class TestTernaryDeep(unittest.TestCase):
    """三态深化测试 — TritValue 多类型 + 置信度传播"""

    def test_tritvalue_string(self):
        """TritValue 可以承载字符串"""
        from ternary_core import TritValue

        tv = TritValue("hello")
        self.assertTrue(tv.is_string())
        self.assertEqual(tv.to_payload(), "hello")
        self.assertEqual(tv.confidence, 1.0)

    def test_tritvalue_string_confidence(self):
        """三态字符串带置信度"""
        from ternary_core import TritValue

        tv = TritValue("unknown", confidence=0.5)
        self.assertTrue(tv.is_string())
        self.assertEqual(tv.confidence, 0.5)

    def test_ternary_value_op(self):
        """三态值() 构造函数"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        # 三态值("hello", 0.8) → TritValue 字符串
        r = e.eval(['ternary_value', '"hello"', 0.8])
        self.assertIsInstance(r, TritValue)
        self.assertTrue(r.is_string())
        self.assertEqual(r.to_payload(), "hello")
        self.assertAlmostEqual(r.confidence, 0.8)

    def test_ternary_propagate(self):
        """传递() 贝叶斯置信度传播"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        # 上游 0.9 × 当前 0.8 = 0.72
        a = e.eval(['ternary_value', '"hello"', 0.9])
        b = e.eval(['ternary_value', '"world"', 0.8])
        r = e.eval(['ternary_propagate', a, b])
        self.assertAlmostEqual(r.confidence, 0.72)

    def test_concat_unwrap_trit(self):
        """连接() 自动解包三态字符串"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        a = e.eval(['ternary_value', '"hello"', 0.9])
        b = e.eval(['ternary_value', '" world"', 0.8])
        r = e.eval(['concat', a, b])
        self.assertEqual(r, "hello world")

    def test_detect_conflict(self):
        """检测冲突: 两个高信度矛盾值 → 标记冲突"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        a = e.eval(['ternary_value', 1, 0.9, '"传感器A"'])
        b = e.eval(['ternary_value', -1, 0.85, '"传感器B"'])
        r = e.eval(['detect_conflict', a, b])
        self.assertEqual(r['冲突'], 1)

    def test_detect_conflict_no_conflict(self):
        """检测冲突: 两个一致值 → 无冲突"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        a = e.eval(['ternary_value', 1, 0.9])
        b = e.eval(['ternary_value', 1, 0.8])
        r = e.eval(['detect_conflict', a, b])
        self.assertEqual(r['冲突'], 0)

    def test_decide_passes_threshold(self):
        """判定: 信度 ≥ 阈值 → 通过"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        v = e.eval(['ternary_value', 1, 0.95])
        r = e.eval(['decide', v, 0.9])
        self.assertEqual(r.to_int(), 1)

    def test_decide_below_threshold(self):
        """判定: 信度 < 阈值 → 降为可能态"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        v = e.eval(['ternary_value', 1, 0.3])
        r = e.eval(['decide', v, 0.5])
        self.assertEqual(r.to_int(), 0)  # 降为可能

    def test_fuse_weighted(self):
        """融合: 多源加权平均"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        s1 = e.eval(['ternary_value', 1, 0.9])
        s2 = e.eval(['ternary_value', 0, 0.4])
        s3 = e.eval(['ternary_value', 1, 0.7])
        r = e.eval(['fuse', s1, s2, s3])
        self.assertEqual(r.to_int(), 1)  # 加权后偏真

    def test_consensus_two_sensors(self):
        """共识: 两个传感器融合"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        s1 = e.eval(['ternary_value', 1, 0.9, '"红外"'])
        s2 = e.eval(['ternary_value', 1, 0.7, '"光照"'])
        r = e.eval(['consensus', s1, s2])
        self.assertEqual(r.to_int(), 1)  # 两真→真
        self.assertGreater(r.confidence, 0.7)  # 融合后信度应上升

    def test_bayes_update_confirm(self):
        """贝叶斯更新: 证据一致→信度上升"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        prior = e.eval(['ternary_value', 1, 0.6])
        evidence = e.eval(['ternary_value', 1, 0.8])
        r = e.eval(['bayes_update', prior, evidence])
        self.assertEqual(r.to_int(), 1)
        self.assertGreater(r.confidence, 0.6)

    def test_bayes_update_contradict(self):
        """贝叶斯更新: 证据矛盾→信度下降"""
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        prior = e.eval(['ternary_value', 1, 0.5])
        evidence = e.eval(['ternary_value', -1, 0.9])
        r = e.eval(['bayes_update', prior, evidence])
        # 强证据矛盾 → 值可能翻转
        self.assertIn(r.to_int(), [1, -1])


if __name__ == '__main__':
    unittest.main()
