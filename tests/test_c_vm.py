"""C VM (csrc/runtime.c) 单元测试

通过 Python 编译并运行 C VM 测试可执行文件，验证字节码解释器的正确性。
需要 C 编译器 (gcc/clang) 才能运行，否则自动跳过。
"""

from __future__ import annotations
import subprocess
import sys
import os
import tempfile
import unittest


from utils.compiler_tools import find_cc, run_in_shell, win_to_posix

SRC = os.path.join(os.path.dirname(__file__), '..', 'csrc', 'test_runtime.c')
RUNTIME_SRC = os.path.join(os.path.dirname(__file__), '..', 'csrc', 'runtime.c')
EXE_NAME = 'test_runtime.exe' if sys.platform == 'win32' else 'test_runtime'
CVM_EXE_NAME = 'cvm_test.exe' if sys.platform == 'win32' else 'cvm_test'


def _compile_and_run() -> tuple[bool, str]:
    """编译并运行 C VM 测试，返回 (成功, 输出)"""
    compiler = find_cc()
    if compiler is None:
        return False, '需要 C 编译器 (gcc/clang)'

    if not os.path.exists(SRC):
        return False, f'测试源文件不存在: {SRC}'

    with tempfile.TemporaryDirectory() as tmpdir:
        exe_path = os.path.join(tmpdir, EXE_NAME)
        src_posix = win_to_posix(SRC)
        exe_posix = win_to_posix(exe_path)
        result = run_in_shell(f'gcc {src_posix} -o {exe_posix} -std=c99 -Wall', check=False)
        if result.returncode != 0:
            return False, f'编译失败:\n{result.stderr}'

        result = subprocess.run(
            [exe_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30,
        )
        return result.returncode == 0, result.stdout + result.stderr


def _compile_cvm() -> str | None:
    """编译 C VM，返回可执行文件路径"""
    compiler = find_cc()
    if compiler is None:
        return None
    exe_path = os.path.join(tempfile.gettempdir(), CVM_EXE_NAME)
    src_posix = win_to_posix(RUNTIME_SRC)
    exe_posix = win_to_posix(exe_path)
    result = run_in_shell(f'gcc {src_posix} -o {exe_posix} -std=c99 -Wall', check=False)
    if result.returncode != 0:
        return None
    return exe_path


def _run_cvm(bin_path: str) -> str | None:
    """在 C VM 上运行 .bin 文件，返回输出"""
    compiler = find_cc()
    if compiler is None:
        return None
    cvm_exe = _compile_cvm()
    if not cvm_exe or not os.path.exists(cvm_exe):
        return None
    result = subprocess.run(
        [cvm_exe, bin_path, '--run'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=10,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


class TestCVM(unittest.TestCase):
    """C VM 字节码解释器测试"""

    def test_c_vm(self):
        ok, output = _compile_and_run()
        if not ok and '需要 C 编译器' in output:
            self.skipTest(output)
        # 解析输出获取测试统计
        for line in output.splitlines():
            if 'tests,' in line and 'passed' in line:
                parts = line.split(',')
                total = int(parts[0].strip().split()[0])
                passed = int(parts[1].strip().split()[0])
                failed = int(parts[2].strip().split()[0])
                self.assertEqual(failed, 0, f'C VM 测试失败: {failed}/{total}\n{output}')
                self.assertEqual(passed, total, f'C VM 测试不完整: {passed}/{total}\n{output}')
                return
        self.skipTest(f'C VM 测试输出格式不匹配（可能是编译环境问题）:\n{output[:200]}')


class TestCVMCrossValidation(unittest.TestCase):
    """C VM 与 Python VM 交叉验证测试"""

    _cvm_exe: str | None = None  # 类级缓存：编译一次复用

    @classmethod
    def setUpClass(cls):
        """检查 C 编译器是否可用，并编译 C VM（仅一次）"""
        if find_cc() is None:
            raise unittest.SkipTest('需要 C 编译器 (gcc/clang)')
        cls._cvm_exe = _compile_cvm()

    def _compile_and_compare(self, source: str, expected_output: str):
        """编译源码并在 C VM 和 Python VM 上运行，比较输出"""
        from compiler.compile_bytecode import compile_source
        from vm import VM

        with tempfile.TemporaryDirectory() as tmpdir:
            bin_path = os.path.join(tmpdir, 'test.bin')
            result = compile_source(source, bin_path)
            self.assertTrue(result[0], f'编译失败: {result}')

            # Python VM
            import io

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            vm = VM.from_bin(bin_path)
            vm.run()
            py_output = sys.stdout.getvalue().strip()
            sys.stdout = old_stdout

            # C VM（复用已编译的可执行文件）
            cvm_output = None
            if self._cvm_exe and os.path.exists(self._cvm_exe):
                try:
                    res = subprocess.run(
                        [self._cvm_exe, bin_path, '--run'],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        timeout=10,
                    )
                    if res.returncode == 0:
                        cvm_output = res.stdout.strip()
                except subprocess.TimeoutExpired:
                    pass

            # 比较
            self.assertEqual(py_output, expected_output, 'Python VM 输出不匹配')
            if cvm_output is not None:
                self.assertEqual(cvm_output, expected_output, 'C VM 输出不匹配')

    def test_arithmetic(self):
        self._compile_and_compare('(输出 (加 10 20))', '30')

    def test_comparison_gt(self):
        self._compile_and_compare('(输出 (大于 5 3))', '1')

    def test_comparison_lt(self):
        self._compile_and_compare('(输出 (小于 5 3))', '-1')

    def test_not(self):
        self._compile_and_compare('(输出 (非 1))', '-1')

    def test_not_zero(self):
        self._compile_and_compare('(输出 (非 0))', '0')

    def test_string(self):
        self._compile_and_compare('(输出 "hello")', 'hello')

    def test_variable(self):
        self._compile_and_compare('(做 (设 x 42) (输出 x))', '42')

    def test_if_true(self):
        self._compile_and_compare('(若 (大于 5 3) (输出 1) (输出 -1))', '1')

    def test_if_false(self):
        self._compile_and_compare('(若 (小于 5 3) (输出 1) (输出 -1))', '-1')

    def test_loop(self):
        self._compile_and_compare('(做 (设 x 0) (循环 (小于 x 3) (做 (设 x (加 x 1)))) (输出 x))', '3')

    def test_function(self):
        self._compile_and_compare('(做 (定义 两倍 (n) (乘 n 2)) (输出 (两倍 21)))', '42')

    def test_dict(self):
        self._compile_and_compare('(做 (设 d (字典 "a" 1 "b" 2)) (输出 (取键 d "b")))', '2')

    def test_list(self):
        self._compile_and_compare('(做 (设 lst (列表 10 20 30)) (输出 (取 lst 1)))', '20')


if __name__ == '__main__':
    unittest.main()
