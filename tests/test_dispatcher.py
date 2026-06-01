"""命令分发器测试 — 覆盖 resolve_op_name、dispatch_op、handle_dot_access、handle_variable_call 等"""

import unittest
from evaluator import SanyanEvaluator
from ternary_core import TritValue, ArrayValue
from values import (
    FunctionValue,
    ModuleValue,
    SanyanNameError,
    SanyanSyntaxError,
    SanyanTypeError,
    SanyanKeyError,
    SanyanAttributeError,
)
from skin import SkinManager
from ops.dispatcher import (
    resolve_op_name,
    dispatch_op,
    handle_dot_access,
    handle_variable_call,
    apply,
)


class TestResolveOpName(unittest.TestCase):
    """操作名解析测试"""

    def setUp(self):
        self.env = SanyanEvaluator(skin_manager=SkinManager('chinese'))

    def test_no_skin_returns_original(self):
        from skin import SkinManager
        e = SanyanEvaluator(skin_manager=None)
        self.assertEqual(resolve_op_name(e, 'add'), 'add')

    def test_skin_internal_keyword(self):
        self.assertEqual(resolve_op_name(self.env, '加'), 'add')
        self.assertEqual(resolve_op_name(self.env, '减'), 'sub')
        self.assertEqual(resolve_op_name(self.env, '乘'), 'mul')
        self.assertEqual(resolve_op_name(self.env, '除'), 'div')

    def test_skin_internal_op(self):
        self.assertEqual(resolve_op_name(self.env, '输出'), 'print')
        self.assertEqual(resolve_op_name(self.env, '输入'), 'input')

    def test_unknown_returns_original(self):
        self.assertEqual(resolve_op_name(self.env, '非存在命令'), '非存在命令')

    def test_cache_hit(self):
        self.env._name_cache['foo'] = 'bar'
        self.assertEqual(resolve_op_name(self.env, 'foo'), 'bar')

    def test_cache_eviction(self):
        e = SanyanEvaluator(skin_manager=SkinManager('chinese'))
        e._name_cache_max = 2
        resolve_op_name(e, 'a')
        resolve_op_name(e, 'b')
        resolve_op_name(e, 'c')
        self.assertNotIn('a', e._name_cache)


class TestDispatchOp(unittest.TestCase):
    """操作分派测试"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def test_dispatch_builtin(self):
        result = dispatch_op(self.env, 'add', [3, 4])
        self.assertEqual(result.to_int(), 7)

    def test_dispatch_unknown(self):
        result = dispatch_op(self.env, '非存在', [1])
        self.assertIsNone(result)

    def test_dispatch_with_extra(self):
        from ops.registry import register, register_alias
        called = []

        def mock_op(e, extra, args):
            called.append(extra)
            return TritValue(1)

        register('mock_with_extra', mock_op, 'test_extra')
        result = dispatch_op(self.env, 'mock_with_extra', [])
        self.assertEqual(result.to_int(), 1)
        self.assertEqual(called, ['test_extra'])

    def test_dispatch_cache(self):
        dispatch_op(self.env, 'add', [1, 2])
        self.assertIn('add', self.env._op_cache)

    def test_no_cache_op_always_lookup(self):
        from ops.registry import register
        counter = [0]

        def counting_op(e, args):
            counter[0] += 1
            return TritValue(counter[0])

        register('count_op', counting_op)
        result = dispatch_op(self.env, 'count_op', [])
        self.assertEqual(result.to_int(), 1)
        result = dispatch_op(self.env, 'count_op', [])
        self.assertEqual(result.to_int(), 2)


class TestDotAccess(unittest.TestCase):
    """点号访问测试"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def test_no_dot_returns_none(self):
        result = handle_dot_access(self.env, 'no_dot', [])
        self.assertIsNone(result)

    def test_module_dot_exported(self):
        mod = ModuleValue({}, {'func': (['x'], [['return', 'x']])})
        self.env.set_var('test_mod', mod)
        result = handle_dot_access(self.env, 'test_mod.func', [42])
        self.assertIsNotNone(result)

    def test_module_dot_not_exported(self):
        mod = ModuleValue({}, {'内部': (['x'], [['return', 'x']])}, exports={'func'})
        self.env.set_var('test_mod', mod)
        with self.assertRaises(SanyanNameError):
            handle_dot_access(self.env, 'test_mod.秘密', [])

    def test_dict_key_access(self):
        self.env.set_var('d', {'name': '小明', 'age': 25})
        result = handle_dot_access(self.env, 'd.name', [])
        self.assertEqual(result, '小明')
        result = handle_dot_access(self.env, 'd.age', [])
        self.assertEqual(result, 25)

    def test_dict_key_not_found(self):
        self.env.set_var('d', {'a': 1})
        with self.assertRaises(SanyanKeyError):
            handle_dot_access(self.env, 'd.未知', [])

    def test_dict_disallows_args(self):
        self.env.set_var('d', {'a': 1})
        with self.assertRaises(SanyanTypeError):
            handle_dot_access(self.env, 'd.a', [1])

    def test_list_index_access(self):
        self.env.set_var('lst', [10, 20, 30])
        result = handle_dot_access(self.env, 'lst.0', [])
        self.assertEqual(result, 10)
        result = handle_dot_access(self.env, 'lst.2', [])
        self.assertEqual(result, 30)

    def test_list_length_access(self):
        self.env.set_var('lst', [10, 20, 30])
        result = handle_dot_access(self.env, 'lst.length', [])
        self.assertEqual(result.to_int(), 3)
        result = handle_dot_access(self.env, 'lst.长度', [])
        self.assertEqual(result.to_int(), 3)

    def test_list_out_of_range(self):
        self.env.set_var('lst', [10, 20])
        with self.assertRaises(SanyanAttributeError):
            handle_dot_access(self.env, 'lst.99', [])

    def test_array_value_index_access(self):
        from ternary_core import ArrayValue
        arr = ArrayValue(3, TritValue(0))
        arr.set(0, TritValue(5))
        arr.set(1, TritValue(10))
        arr.set(2, TritValue(15))
        self.env.set_var('arr', arr)
        result = handle_dot_access(self.env, 'arr.0', [])
        self.assertEqual(result.to_int(), 5)


class TestVariableCall(unittest.TestCase):
    """变量调用测试"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def test_unknown_var(self):
        result = handle_variable_call(self.env, '未知', [])
        self.assertIsNone(result)

    def test_function_call(self):
        f = FunctionValue(['x'], ['x'])
        self.env.set_var('id_fn', f)
        result = handle_variable_call(self.env, 'id_fn', [42])
        self.assertIsNotNone(result)
        self.assertEqual(result.to_int(), 42)

    def test_module_call(self):
        mod = ModuleValue({}, {'mod_func': (['x'], [['return', 'x']])})
        self.env.set_var('mod', mod)
        result = handle_variable_call(self.env, 'mod', ['mod_func', '"hello"'])
        self.assertIsNotNone(result)

    def test_list_indexing(self):
        self.env.set_var('lst', [10, 20, 30])
        result = handle_variable_call(self.env, 'lst', [1])
        self.assertEqual(result, 20)

    def test_list_indexing_too_many_args(self):
        self.env.set_var('lst', [10, 20])
        with self.assertRaises(SanyanSyntaxError):
            handle_variable_call(self.env, 'lst', [1, 2])

    def test_dict_key_access(self):
        self.env.set_var('d', {'a': 1, 'b': 2})
        result = handle_variable_call(self.env, 'd', ['a'])
        self.assertEqual(result, 1)

    def test_variable_value_return(self):
        self.env.set_var('x', 42)
        result = handle_variable_call(self.env, 'x', [])
        self.assertEqual(result, 42)

    def test_uncallable_value_with_args(self):
        self.env.set_var('x', 42)
        with self.assertRaises(SanyanTypeError):
            handle_variable_call(self.env, 'x', [1])


class TestApply(unittest.TestCase):
    """主分派入口测试"""

    def setUp(self):
        self.env = SanyanEvaluator(skin_manager=SkinManager('chinese'))

    def test_apply_builtin(self):
        result = apply(self.env, '加', [3, 4])
        self.assertEqual(result.to_int(), 7)

    def test_apply_variable(self):
        f = FunctionValue(['x'], ['x'])
        self.env.set_var('id_fn', f)
        result = apply(self.env, 'id_fn', [42])
        self.assertIsNotNone(result)
        self.assertEqual(result.to_int(), 42)

    def test_apply_custom_command(self):
        result = apply(self.env, 'add', [1, 2])
        self.assertEqual(result.to_int(), 3)

    def test_apply_sandbox_blocked(self):
        """测试沙箱限制：沙箱激活后受保护操作被拦截"""
        from sandbox import restrict, unblock, is_active
        restrict(ops=['debug'])
        self.assertTrue(is_active())
        unblock()
        self.assertFalse(is_active())


if __name__ == '__main__':
    unittest.main()
