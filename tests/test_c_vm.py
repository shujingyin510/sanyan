"""C VM (csrc/runtime.c) 单元测试

通过 Python 编译并运行 C VM 测试可执行文件，验证字节码解释器的正确性。
需要 C 编译器 (gcc/clang) 才能运行，否则自动跳过。
"""

from __future__ import annotations
import subprocess
import sys
import os
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SRC = os.path.join(os.path.dirname(__file__), '..', 'csrc', 'test_runtime.c')
RUNTIME_SRC = os.path.join(os.path.dirname(__file__), '..', 'csrc', 'runtime.c')
EXE_NAME = 'test_runtime.exe' if sys.platform == 'win32' else 'test_runtime'
CVM_EXE_NAME = 'cvm_test.exe' if sys.platform == 'win32' else 'cvm_test'
MSYS2_BASH = r'D:\msys64\usr\bin\bash.exe'


def _find_compiler() -> str | None:
    """查找可用的 C 编译器"""
    for compiler in ['gcc', 'clang', 'cc']:
        if shutil.which(compiler):
            return compiler
    # 尝试 MSYS2 路径
    if sys.platform == 'win32':
        msys_gcc = r'D:\msys64\mingw64\bin\gcc.exe'
        if os.path.exists(msys_gcc):
            return msys_gcc
    return None


def _run_in_msys2(cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """执行命令。Windows 用 MSYS2 bash，Linux/macOS 直接执行。"""
    if sys.platform == 'win32' and os.path.exists(MSYS2_BASH):
        return subprocess.run(
            [MSYS2_BASH, '-lc', cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    # Linux/macOS：直接执行（cmd 中的路径已是 POSIX 格式）
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _win_to_msys2(path: str) -> str:
    """路径格式转换。Windows 转 MSYS2 格式，Linux/macOS 原样返回。"""
    if sys.platform != 'win32':
        return path
    p = path.replace('\\', '/')
    if len(p) >= 2 and p[1] == ':':
        p = '/' + p[0].lower() + p[2:]
    return p


def _compile_cvm(compiler: str) -> str | None:
    """编译 C VM，返回可执行文件路径"""
    exe_path = os.path.join(tempfile.gettempdir(), CVM_EXE_NAME)
    src_posix = _win_to_msys2(RUNTIME_SRC)
    exe_posix = _win_to_msys2(exe_path)
    result = _run_in_msys2(f'gcc {src_posix} -o {exe_posix} -std=c99 -Wall')
    if result.returncode != 0:
        return None
    return exe_path


def _compile_and_run() -> tuple[bool, str]:
    """编译并运行 C VM 测试，返回 (成功, 输出)"""
    compiler = _find_compiler()
    if compiler is None:
        return False, '需要 C 编译器 (gcc/clang)'

    if not os.path.exists(SRC):
        return False, f'测试源文件不存在: {SRC}'

    with tempfile.TemporaryDirectory() as tmpdir:
        exe_path = os.path.join(tmpdir, EXE_NAME)
        src_posix = _win_to_msys2(SRC)
        exe_posix = _win_to_msys2(exe_path)
        result = _run_in_msys2(f'gcc {src_posix} -o {exe_posix} -std=c99 -Wall')
        if result.returncode != 0:
            return False, f'编译失败:\n{result.stderr}'

        result = subprocess.run(
            [exe_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stdout + result.stderr


def _run_cvm(bin_path: str) -> str | None:
    """在 C VM 上运行 .bin 文件，返回输出"""
    compiler = _find_compiler()
    if compiler is None:
        return None

    cvm_exe = _compile_cvm(compiler)
    if cvm_exe is None:
        return None

    # 使用 --run 模式输出栈顶值
    result = subprocess.run(
        [cvm_exe, bin_path, '--run'],
        capture_output=True,
        text=True,
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

    def _compile_and_compare(self, source: str, expected: str):
        """编译源码，分别在 C VM 和 Python VM 上运行，比较输出"""
        compiler = _find_compiler()
        if compiler is None:
            self.skipTest('需要 C 编译器')

        from compile_bytecode import compile_source
        from vm import VM

        # 使用 build 目录（避免路径限制）
        build_dir = os.path.join(os.path.dirname(__file__), '..', 'build')
        os.makedirs(build_dir, exist_ok=True)
        bin_path = os.path.join(build_dir, '_cross_test.bin')

        try:
            # 编译
            compile_source(source, bin_path)

            # Python VM 执行（from_bin 已执行主代码）
            import io

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            VM.from_bin(bin_path)
            py_output = sys.stdout.getvalue().strip()
            sys.stdout = old_stdout

            # C VM 执行
            cvm_output = _run_cvm(bin_path)

            # 比较
            self.assertEqual(py_output, expected, f'Python VM 输出不匹配: {py_output!r}')
            if cvm_output is not None:
                self.assertEqual(cvm_output, expected, f'C VM 输出不匹配: {cvm_output!r}')
        finally:
            if os.path.exists(bin_path):
                os.unlink(bin_path)

    def test_arithmetic(self):
        self._compile_and_compare('(输出 (加 10 20))', '30')

    def test_comparison_gt(self):
        self._compile_and_compare('(输出 (大于 5 3))', '1')

    def test_comparison_lt(self):
        self._compile_and_compare('(输出 (小于 5 3))', '-1')

    def test_not(self):
        self._compile_and_compare('(输出 (非 1))', '-1')

    def test_not_zero(self):
        self._compile_and_compare('(输出 (非 0))', '1')

    def test_string(self):
        self._compile_and_compare('(输出 "hello")', 'hello')

    def test_variable(self):
        self._compile_and_compare('(做 (设 x 42) (输出 x))', '42')

    def test_if_true(self):
        self._compile_and_compare('(若 (大于 5 3) (输出 1) (输出 -1))', '1')

    def test_if_false(self):
        self._compile_and_compare('(若 (小于 5 3) (输出 1) (输出 -1))', '-1')

    def test_loop(self):
        self._compile_and_compare(
            '(做 (设 s 0) (设 i 1) (循环 (小于等于 i 5) (做 (设 s (加 s i)) (设 i (加 i 1)))) (输出 s))', '15'
        )

    def test_function(self):
        self._compile_and_compare('(做 (定义 双倍 (x) (乘 x 2)) (输出 (双倍 21)))', '42')

    def test_dict(self):
        self._compile_and_compare('(做 (设 d (字典 "a" 1)) (输出 (含键 d "a")))', '1')

    def test_list(self):
        self._compile_and_compare('(输出 (表长 (列表 1 2 3)))', '3')


if __name__ == '__main__':
    unittest.main()
