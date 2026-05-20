"""LLVM 原生编译测试（需要 C 编译器）

若无 C 编译器，测试自动跳过 (skip)。
安装 gcc/clang 后即可运行。
"""

import sys
import os
import subprocess
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llvmgen.compiler import compile_source


def _find_cc() -> str | None:
    """查找可用的 C 编译器 (gcc/clang/cc/MSYS2 gcc)。"""
    candidates = ['gcc', 'clang', 'cc']
    for cc in candidates:
        try:
            r = subprocess.run([cc, '--version'], capture_output=True, timeout=5)
            if r.returncode == 0:
                return cc
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    # MSYS2 gcc on Windows
    msys2_paths = [
        r'C:\msys64\mingw64\bin\gcc.exe',
        r'C:\msys64\ucrt64\bin\gcc.exe',
        r'C:\msys32\mingw32\bin\gcc.exe',
    ]
    for p in msys2_paths:
        if os.path.exists(p):
            return p
    return None


@unittest.skipIf(_find_cc() is None, '需要 C 编译器 (gcc/clang)')
class TestLlvmNativeCompile(unittest.TestCase):
    """验证 LLVM IR 可被 C 编译器成功编译并链接运行时"""

    def _cc(self) -> str:
        cc = _find_cc()
        assert cc is not None
        return cc

    def test_compile_simple_program(self):
        """编译一个最小程序并运行"""
        code = '输出(加(1, 2))'
        ir_text, cg = compile_source(code, 'test_simple')

        with tempfile.TemporaryDirectory() as tmp:
            ir_path = os.path.join(tmp, 'test_simple.ll')
            obj_path = os.path.join(tmp, 'test_simple.o')
            rt_dir = os.path.join(os.path.dirname(__file__), '..', 'llvmgen')
            rt_src = os.path.join(rt_dir, 'runtime.c')
            rt_obj = os.path.join(tmp, 'runtime.o')
            exe_path = os.path.join(tmp, 'test_simple.exe')

            with open(ir_path, 'w') as f:
                f.write(ir_text)

            cc = self._cc()
            subprocess.run([cc, '-c', rt_src, '-o', rt_obj, '-std=c99', '-O2'], check=True)
            subprocess.run([cc, '-c', ir_path, '-o', obj_path], check=True)
            subprocess.run([cc, obj_path, rt_obj, '-o', exe_path], check=True)

            self.assertTrue(os.path.exists(exe_path), '可执行文件未生成')
            result = subprocess.run([exe_path], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0)

    def test_compile_bootstrap_sexpr(self):
        """编译 S 表达式 _bootstrap.san 并验证 parse_sanyan() 存在"""
        bp_path = os.path.join(os.path.dirname(__file__), '..', 'stdlib', '_bootstrap.san')
        with open(bp_path, 'r') as f:
            source = f.read()

        ir_text, cg = compile_source(source, 'bootstrap')
        # 验证 IR 包含 parse_sanyan 入口
        self.assertIn('parse_sanyan', ir_text)
        self.assertIn('词法分析', ir_text)

        with tempfile.TemporaryDirectory() as tmp:
            ir_path = os.path.join(tmp, 'bootstrap.ll')
            obj_path = os.path.join(tmp, 'bootstrap.o')
            with open(ir_path, 'w') as f:
                f.write(ir_text)

            cc = self._cc()
            subprocess.run([cc, '-c', ir_path, '-o', obj_path], check=True)
            self.assertTrue(os.path.exists(obj_path), 'bootstrap.o 未生成')

    def test_compile_dp_harness(self):
        """编译 dp.c + bootstrap.o + runtime.o 完整管线"""
        bp_path = os.path.join(os.path.dirname(__file__), '..', 'stdlib', '_bootstrap.san')
        with open(bp_path, 'r') as f:
            source = f.read()

        ir_text, cg = compile_source(source, 'bootstrap')
        dp_c_path = os.path.join(os.path.dirname(__file__), '..', 'dp.c')

        with tempfile.TemporaryDirectory() as tmp:
            rt_dir = os.path.join(os.path.dirname(__file__), '..', 'llvmgen')
            rt_src = os.path.join(rt_dir, 'runtime.c')
            ir_path = os.path.join(tmp, 'bootstrap.ll')
            obj_path = os.path.join(tmp, 'bootstrap.o')
            rt_obj = os.path.join(tmp, 'runtime.o')
            dp_obj = os.path.join(tmp, 'dp.o')
            exe_path = os.path.join(tmp, 'dp.exe')

            with open(ir_path, 'w') as f:
                f.write(ir_text)

            cc = self._cc()
            subprocess.run([cc, '-c', rt_src, '-o', rt_obj, '-std=c99', '-O2'], check=True)
            subprocess.run([cc, '-c', ir_path, '-o', obj_path], check=True)
            subprocess.run([cc, '-c', dp_c_path, '-o', dp_obj, '-std=c99'], check=True)
            subprocess.run([cc, dp_obj, obj_path, rt_obj, '-o', exe_path], check=True)

            self.assertTrue(os.path.exists(exe_path), 'dp.exe 未生成')
            result = subprocess.run([exe_path], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, f'dp 返回码 {result.returncode}')
            self.assertIn('OK', result.stdout.decode('utf-8', errors='replace'))


if __name__ == '__main__':
    unittest.main()
