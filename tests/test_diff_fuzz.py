"""差分模糊测试：验证四个后端输出一致

生成随机三言 S 表达式程序，同时在 Python VM、C VM、LLVM 三个后端运行，
比较输出字节级一致。求值器单独验证不崩溃。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.diff_fuzzer import run_diff_test, BackendRunner


class TestDiffFuzzBasic(unittest.TestCase):
    """基础差分测试：算术/比较/逻辑"""

    def test_diff_small_arithmetic(self):
        """小型算术程序差分（depth=2, 20 个程序）"""
        failures = run_diff_test(seed=42, count=20, max_depth=2, max_stmts=2)
        if failures:
            details = '\n'.join(f'  [{f.iteration}] {f.diff_detail}\n    PROG: {f.program[:80]}' for f in failures[:5])
            self.fail(f'发现 {len(failures)} 个差异:\n{details}')

    def test_diff_medium(self):
        """中等复杂度差分（depth=3, 10 个程序）"""
        failures = run_diff_test(seed=123, count=10, max_depth=3, max_stmts=3)
        if failures:
            details = '\n'.join(f'  [{f.iteration}] {f.diff_detail}\n    PROG: {f.program[:80]}' for f in failures[:5])
            self.fail(f'发现 {len(failures)} 个差异:\n{details}')


class TestDiffFuzzFeatures(unittest.TestCase):
    """特性差分测试：变量/条件/循环/函数"""

    def test_diff_with_variables(self):
        failures = run_diff_test(seed=456, count=10, max_depth=3, max_stmts=3)
        if failures:
            details = '\n'.join(f'  [{f.iteration}] {f.diff_detail}\n    PROG: {f.program[:80]}' for f in failures[:5])
            self.fail(f'发现 {len(failures)} 个差异:\n{details}')

    def test_diff_with_functions(self):
        failures = run_diff_test(seed=789, count=10, max_depth=3, max_stmts=3)
        if failures:
            details = '\n'.join(f'  [{f.iteration}] {f.diff_detail}\n    PROG: {f.program[:80]}' for f in failures[:5])
            self.fail(f'发现 {len(failures)} 个差异:\n{details}')

    def test_diff_with_loops(self):
        failures = run_diff_test(seed=321, count=10, max_depth=2, max_stmts=2)
        if failures:
            details = '\n'.join(f'  [{f.iteration}] {f.diff_detail}\n    PROG: {f.program[:80]}' for f in failures[:5])
            self.fail(f'发现 {len(failures)} 个差异:\n{details}')


class TestDiffFuzzMixed(unittest.TestCase):
    """混合操作：算术/比较/逻辑混用"""

    def test_diff_mixed_ops(self):
        failures = run_diff_test(seed=333, count=15, max_depth=4, max_stmts=4)
        if failures:
            details = '\n'.join(f'  [{f.iteration}] {f.diff_detail}\n    PROG: {f.program[:80]}' for f in failures[:5])
            self.fail(f'发现 {len(failures)} 个差异:\n{details}')

    def test_diff_deep_nesting(self):
        failures = run_diff_test(seed=444, count=10, max_depth=5, max_stmts=3)
        if failures:
            details = '\n'.join(f'  [{f.iteration}] {f.diff_detail}\n    PROG: {f.program[:80]}' for f in failures[:5])
            self.fail(f'发现 {len(failures)} 个差异:\n{details}')


class TestDiffFuzzReproduce(unittest.TestCase):
    """可重现性：相同种子产生相同结果"""

    def test_same_seed_same_programs(self):
        """相同种子生成相同的程序序列"""
        from tests.diff_fuzzer import ProgramGenerator

        gen1 = ProgramGenerator(seed=999, max_depth=2, max_stmts=2)
        gen2 = ProgramGenerator(seed=999, max_depth=2, max_stmts=2)
        for _ in range(10):
            self.assertEqual(gen1.generate(), gen2.generate())


class TestDiffFuzzBackendAvailability(unittest.TestCase):
    """后端可用性检查"""

    def test_evaluator_always_available(self):
        """求值器始终可用"""
        status, _ = BackendRunner.run_evaluator('(输出 42)')
        self.assertEqual(status, 'OK')

    def test_python_vm_always_available(self):
        """Python VM 始终可用"""
        status, output = BackendRunner.run_python_vm('(输出 42)')
        self.assertEqual(status, 'OK')
        self.assertEqual(output.strip(), '42')

    def test_c_vm_availability(self):
        """C VM 可用性（可能跳过）"""
        status, output = BackendRunner.run_c_vm('(输出 42)')
        if status == 'SKIP':
            self.skipTest(output)
        self.assertEqual(status, 'OK')
        self.assertEqual(output.strip(), '42')

    def test_llvm_availability(self):
        """LLVM 可用性"""
        status, output = BackendRunner.run_llvm('(输出 42)')
        if status == 'SKIP':
            self.skipTest(output)
        self.assertEqual(status, 'OK')
        self.assertIn('42', output)


if __name__ == '__main__':
    unittest.main()
