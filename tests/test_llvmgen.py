"""LLVM 代码生成器专项测试：验证 AST → LLVM IR 编译正确性"""



import unittest
from llvmgen.codegen import compile_top_level


def _compile_ast(ast_nodes):
    """编译 AST 列表为 IR 文本。"""
    cg = compile_top_level(ast_nodes, 'test')
    return cg.verify()


def _has_pattern(ir_text, pattern):
    """检查 IR 文本是否包含给定模式。"""
    return pattern in ir_text


def _count_pattern(ir_text, pattern):
    """统计模式出现次数。"""
    return ir_text.count(pattern)


class TestLLVMBasicLiterals(unittest.TestCase):
    """基本字面量编译"""

    def test_int_literal(self):
        ir = _compile_ast([['设', 'x', 42]])
        self.assertIn('shl i64', ir)
        self.assertIn('or i64', ir)

    def test_bool_true(self):
        ir = _compile_ast([['设', 'x', '真']])
        self.assertIn('shl i64 1', ir)

    def test_bool_false(self):
        ir = _compile_ast([['设', 'x', '假']])
        self.assertIn('shl i64 0', ir)


class TestLLVMArithmetic(unittest.TestCase):
    """算术运算"""

    def test_add(self):
        ir = _compile_ast([['设', 'x', ['加', 3, 4]]])
        self.assertIn('add i64', ir)

    def test_sub(self):
        ir = _compile_ast([['设', 'x', ['减', 10, 3]]])
        self.assertIn('sub i64', ir)

    def test_mul(self):
        ir = _compile_ast([['设', 'x', ['乘', 6, 7]]])
        self.assertIn('mul i64', ir)

    def test_div(self):
        ir = _compile_ast([['设', 'x', ['除', 8, 2]]])
        self.assertIn('sdiv i64', ir)

    def test_mod(self):
        ir = _compile_ast([['设', 'x', ['余', 10, 3]]])
        self.assertIn('srem i64', ir)

    def test_nested_arithmetic(self):
        ir = _compile_ast([['设', 'x', ['加', ['乘', 2, 3], 4]]])
        self.assertIn('mul', ir)
        self.assertIn('add', ir)


class TestLLVMComparison(unittest.TestCase):
    """比较运算"""

    def test_eq(self):
        ir = _compile_ast([['设', 'x', ['等于', 5, 5]]])
        self.assertIn('icmp eq', ir)

    def test_gt(self):
        ir = _compile_ast([['设', 'x', ['大于', 5, 3]]])
        self.assertIn('icmp sgt', ir)

    def test_lt(self):
        ir = _compile_ast([['设', 'x', ['小于', 3, 5]]])
        self.assertIn('icmp slt', ir)

    def test_ne(self):
        ir = _compile_ast([['设', 'x', ['不等于', 3, 5]]])
        self.assertIn('icmp ne', ir)


class TestLLVMLogic(unittest.TestCase):
    """逻辑运算"""

    def test_and(self):
        ir = _compile_ast([['设', 'x', ['且', '真', '真']]])
        self.assertTrue(_has_pattern(ir, 'and i1') or _has_pattern(ir, 'and i64'))

    def test_or(self):
        ir = _compile_ast([['设', 'x', ['或', '真', '假']]])
        self.assertTrue(_has_pattern(ir, 'or i1') or _has_pattern(ir, 'or i64'))

    def test_not(self):
        ir = _compile_ast([['设', 'x', ['非', '真']]])
        self.assertIn('not', ir)


class TestLLVMControlFlow(unittest.TestCase):
    """控制流"""

    def test_if_then(self):
        ir = _compile_ast([['若', 1, ['输出', '"yes"']]])
        self.assertIn('br i1', ir)
        self.assertIn('if_test', ir)

    def test_if_else(self):
        ir = _compile_ast([['若', 1, ['输出', '"yes"'], ['输出', '"no"']]])
        self.assertIn('br i1', ir)

    def test_loop(self):
        ir = _compile_ast(
            [
                ['设', 'i', 0],
                ['循环', ['小于', 'i', 5], ['做', ['设', 'i', ['加', 'i', 1]]]],
            ]
        )
        self.assertIn('loop_h', ir)
        self.assertIn('loop_b', ir)

    def test_do_block(self):
        ir = _compile_ast([['做', ['设', 'a', 1], ['设', 'b', 2]]])
        self.assertIn('store', ir)

    def test_return(self):
        ir = _compile_ast(
            [
                ['定义', 'f', [], ['返回', 42]],
            ]
        )
        self.assertIn('ret i8*', ir)

    def test_judge(self):
        ir = _compile_ast([['判', 0, ['输出', '"真"'], ['输出', '"可能"'], ['输出', '"假"']]])
        self.assertIn('switch', ir)


class TestLLVMFunctions(unittest.TestCase):
    """函数定义与调用"""

    def test_define_function(self):
        ir = _compile_ast([['定义', 'add1', ['n'], ['返回', ['加', 'n', 1]]]])
        self.assertIn('define i8* @"add1"', ir)

    def test_function_call(self):
        ir = _compile_ast(
            [
                ['定义', 'double', ['n'], ['返回', ['乘', 'n', 2]]],
                ['设', 'r', ['double', 5]],
            ]
        )
        self.assertIn('call i8* @"double"', ir)

    def test_recursion(self):
        ir = _compile_ast(
            [
                [
                    '定义',
                    'fact',
                    ['n'],
                    ['若', ['小于', 'n', 2], ['返回', 1], ['返回', ['乘', 'n', ['fact', ['减', 'n', 1]]]]],
                ],
            ]
        )
        self.assertIn('@"fact"', ir)
        self.assertIn('ret i8*', ir)

    def test_multiple_params(self):
        ir = _compile_ast(
            [
                ['定义', 'add3', ['a', 'b', 'c'], ['返回', ['加', ['加', 'a', 'b'], 'c']]],
            ]
        )
        self.assertIn('define i8* @"add3"(i8* %"a", i8* %"b", i8* %"c")', ir)


class TestLLVMForLoop(unittest.TestCase):
    """遍历循环"""

    def test_range_for(self):
        ir = _compile_ast(
            [
                ['设', 's', 0],
                ['遍历', 'i', 1, 10, ['做', ['设', 's', ['加', 's', 'i']]]],
            ]
        )
        self.assertIn('for_h', ir)
        self.assertIn('for_b', ir)

    def test_container_for(self):
        ir = _compile_ast(
            [
                ['设', 'lst', ['列表', 1, 2, 3]],
                ['遍历', 'v', 'lst', ['做', ['输出', 'v']]],
            ]
        )
        self.assertIn('call', ir)  # 应包含 rt_list_len / rt_list_get 调用


class TestLLVMPrint(unittest.TestCase):
    """输出"""

    def test_print_int(self):
        ir = _compile_ast([['输出', 42]])
        self.assertIn('printf', ir)
        self.assertIn('%lld', ir)

    def test_print_string(self):
        ir = _compile_ast([['输出', '"hello world"']])
        self.assertIn('rt_print_str', ir)

    def test_print_variable(self):
        ir = _compile_ast([['设', 'x', 99], ['输出', 'x']])
        self.assertIn('printf', ir)


class TestLLVMStrings(unittest.TestCase):
    """字符串操作"""

    def test_concat(self):
        ir = _compile_ast([['设', 's', ['连接', '"a"', '"b"']]])
        self.assertIn('rt_str_concat', ir)

    def test_concat_multi(self):
        ir = _compile_ast([['设', 's', ['连接', '"a"', '"b"', '"c"']]])
        self.assertIn('rt_str_concat', ir)

    def test_concat_mixed_types(self):
        ir = _compile_ast([['设', 's', ['连接', '"n="', 42]]])
        self.assertIn('rt_str_concat', ir)

    def test_str_len(self):
        ir = _compile_ast([['设', 'n', ['取长', '"abc"']]])
        self.assertIn('rt_str_len', ir)


class TestLLVMLists(unittest.TestCase):
    """列表操作"""

    def test_list_new(self):
        ir = _compile_ast([['设', 'lst', ['列表', 1, 2, 3]]])
        self.assertIn('rt_list_new', ir)

    def test_list_len(self):
        ir = _compile_ast([['设', 'lst', ['列表', 1, 2, 3]], ['设', 'n', ['表长', 'lst']]])
        self.assertIn('rt_list_len', ir)

    def test_list_get(self):
        ir = _compile_ast([['设', 'lst', ['列表', 10, 20]], ['设', 'x', ['取', 'lst', 1]]])
        self.assertIn('rt_list_get', ir)


class TestLLVMVariableIndex(unittest.TestCase):
    """变量作为容器索引"""

    def test_variable_as_function_index(self):
        ir = _compile_ast([['设', 'lst', ['列表', 10, 20]], ['设', 'x', ['lst', 1]]])
        self.assertIn('rt_list_get', ir)


class TestLLVMImport(unittest.TestCase):
    """模块导入"""

    def test_import_resolves(self):
        ir = _compile_ast([['设', 'test', ['导入', '"stdlib/test.san"']]])
        self.assertIn('@"测试套件"', ir)


class TestLLVMEdgeCases(unittest.TestCase):
    """边界情况"""

    def test_empty_program(self):
        ir = _compile_ast([])
        self.assertIn('define i8* @"main"', ir)
        self.assertIn('ret i8* null', ir)

    def test_empty_function(self):
        ir = _compile_ast([['定义', 'noop', [], []]])
        self.assertIn('@"noop"', ir)

    def test_nested_if(self):
        ir = _compile_ast([['若', 1, ['做', ['若', 1, ['输出', '"yes"']]]]])
        self.assertIn('br i1', ir)

    def test_deep_expression(self):
        ir = _compile_ast([['设', 'x', ['加', ['乘', ['减', 10, 3], ['除', 8, 2]], 5]]])
        self.assertIn('add', ir)
        self.assertIn('mul', ir)

    def test_box_unbox(self):
        """验证装箱/拆箱指令存在"""
        ir = _compile_ast([['设', 'x', 42], ['输出', 'x']])
        self.assertIn('inttoptr', ir)
        self.assertIn('ptrtoint', ir)


class TestLLVMTryCatch(unittest.TestCase):
    """异常处理"""

    def test_try_catch_basic(self):
        ir = _compile_ast(
            [
                [
                    '尝试',
                    ['做', ['输出', '"try"']],
                    ['捕获', '错误', ['做', ['输出', '"catch"']]],
                ]
            ]
        )
        self.assertIn('g_error', ir)
        self.assertIn('catch_body', ir)


class TestLLVMNoRegression(unittest.TestCase):
    """回归防护：已知通过的示例不应引入新错误"""

    def _check_example(self, name):
        path = f'examples/{name}.san'
        with open(path, encoding='utf-8') as f:
            code = f.read()
        from llvmgen.compiler import compile_source

        ir, _ = compile_source(code, name)
        self.assertGreater(ir.count('\n'), 10, f'{name} should produce substantial IR')
        self.assertIn('define', ir)

    def test_fizzbuzz(self):
        self._check_example('fizzbuzz')

    def test_guess_number(self):
        self._check_example('guess_number')

    def test_greenhouse(self):
        self._check_example('greenhouse')

    def test_voting(self):
        self._check_example('voting')

    def test_data_clean(self):
        self._check_example('data_cleaning')

    def test_sensor_pipeline(self):
        self._check_example('sensor_pipeline_simple')

    def test_text_analysis(self):
        self._check_example('text_analysis')


if __name__ == '__main__':
    unittest.main()
