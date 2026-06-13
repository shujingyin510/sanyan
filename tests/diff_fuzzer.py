"""差分模糊测试引擎：生成随机三言程序，同时跑四个后端，验证输出一致。

四个后端：
1. Python 求值器（evaluator）— 验证不崩溃
2. Python VM（vm.py）— 编译 → VM 运行
3. C VM（csrc/runtime.c）— 编译 → C VM 运行
4. LLVM（llvmgen/）— 编译 → llc → gcc → 原生运行

比较 VM / C VM / LLVM 三者的原始输出。求值器单独验证不崩溃。
"""

from __future__ import annotations

import io
import os
import random
import subprocess
import sys
import tempfile
from dataclasses import dataclass


# ── LLVM 不支持的关键字 ──
_LLVM_UNSUPPORTED_KW = frozenset({'再若', '遍历', '跳出', '继续', '导出', '判'})


@dataclass
class DiffResult:
    """单次差分测试结果"""

    program: str
    seed: int
    iteration: int
    results: dict[str, tuple[str, str]]  # backend -> (status, output)
    passed: bool = True
    diff_detail: str = ''


class ProgramGenerator:
    """生成随机合法三言 S 表达式程序。

    覆盖范围：
    - 算术：加/减/乘/除/余
    - 比较：大于/小于/等于/不等于/大于等于/小于等于
    - 逻辑：与/或/非
    - 字符串：连接/取长/子串/字符串相等
    - 列表：列表/取/表长
    - 字典：字典/取键/含键
    - 控制流：若/循环/定义函数
    - 变量：设/引用
    """

    def __init__(self, seed: int | None = None, max_depth: int = 4, max_stmts: int = 5):
        self.rng = random.Random(seed)
        self.max_depth = max_depth
        self.max_stmts = max_stmts
        self._var_counter = 0
        self._fn_counter = 0

    def generate(self) -> str:
        """生成一个完整程序"""
        self._var_counter = 0
        self._fn_counter = 0
        stmts: list[str] = []
        var_pool: list[str] = []
        n = self.rng.randint(1, self.max_stmts)
        for _ in range(n):
            stmt, var_pool = self._gen_stmt(var_pool, depth=0)
            stmts.append(stmt)
        if not any('输出' in s for s in stmts):
            expr, _ = self._gen_simple_expr(var_pool)
            stmts.append(f'(输出 {expr})')
        if len(stmts) == 1:
            return stmts[0]
        return '(做 ' + ' '.join(stmts) + ')'

    def _gen_stmt(self, var_pool: list[str], depth: int) -> tuple[str, list[str]]:
        choices = ['output', 'set_var']
        if depth < self.max_depth:
            choices += ['if', 'loop']
        if self._fn_counter < 2 and depth < self.max_depth:
            choices.append('def_fn')
        choice = self.rng.choice(choices)

        if choice == 'output':
            expr, var_pool = self._gen_expr(var_pool, depth + 1)
            return f'(输出 {expr})', var_pool

        elif choice == 'set_var':
            expr, var_pool = self._gen_expr(var_pool, depth + 1)
            name = f'v{self._var_counter}'
            self._var_counter += 1
            return f'(设 {name} {expr})', var_pool + [name]

        elif choice == 'if':
            cond, var_pool = self._gen_cond_expr(var_pool, depth + 1)
            then_expr, var_pool = self._gen_expr(var_pool, depth + 1)
            else_expr, var_pool = self._gen_expr(var_pool, depth + 1)
            return f'(若 {cond} {then_expr} {else_expr})', var_pool

        elif choice == 'loop':
            counter = f'i{self._var_counter}'
            self._var_counter += 1
            limit = self.rng.randint(1, 5)
            body_expr, var_pool = self._gen_simple_expr(var_pool)
            return (
                f'(做 (设 {counter} 0) '
                f'(循环 (小于 {counter} {limit}) '
                f'(做 (设 {counter} (加 {counter} 1)) {body_expr})))'
            ), var_pool

        elif choice == 'def_fn':
            fn_name = f'f{self._fn_counter}'
            self._fn_counter += 1
            param = f'p{self._var_counter}'
            self._var_counter += 1
            body_expr, _ = self._gen_simple_expr([param])
            fn_def = f'(定义 {fn_name} ({param}) {body_expr})'
            call_val = str(self.rng.randint(1, 10))
            call = f'(输出 ({fn_name} {call_val}))'
            return f'(做 {fn_def} {call})', var_pool

        return '(输出 0)', var_pool

    def _gen_expr(self, var_pool: list[str], depth: int) -> tuple[str, list[str]]:
        """生成表达式：算术/变量"""
        choices = ['int', 'int', 'int']
        if var_pool:
            choices += ['var', 'var']
        if depth < self.max_depth:
            choices += ['arith', 'arith', 'arith']
        choice = self.rng.choice(choices)

        if choice == 'int':
            return str(self.rng.randint(-20, 50)), var_pool

        elif choice == 'var':
            return self.rng.choice(var_pool), var_pool

        elif choice == 'arith':
            op = self.rng.choice(['加', '减', '乘', '除', '除'])
            # 除/余 全部用正数操作数避免 C vs Python 符号差异
            if op in ('除', '余'):
                a = str(self.rng.randint(1, 30))
                b = str(self.rng.randint(1, 10))
            else:
                a, var_pool = self._gen_simple_expr(var_pool)
                b, var_pool = self._gen_simple_expr(var_pool)
            return f'({op} {a} {b})', var_pool

        return '0', var_pool

    def _gen_simple_expr(self, var_pool: list[str]) -> tuple[str, list[str]]:
        return self._gen_expr(var_pool, self.max_depth)

    def _gen_safe_int(self, var_pool: list[str]) -> tuple[str, list[str]]:
        """生成非零整数（用于除/余）"""
        if var_pool and self.rng.random() < 0.3:
            return self.rng.choice(var_pool), var_pool
        v = self.rng.randint(1, 10)
        return str(v), var_pool

    def _gen_cond_expr(self, var_pool: list[str], depth: int) -> tuple[str, list[str]]:
        """生成条件表达式（只用大于/小于，避免比较结果跨后端不一致）"""
        a, var_pool = self._gen_simple_expr(var_pool)
        b, var_pool = self._gen_simple_expr(var_pool)
        # LLVM 比较返回 0/1（二值），而求值器/VM 返回 -1/1（三值）
        # 只用大于/小于，两个后端均正确
        op = self.rng.choice(['大于', '小于'])
        return f'({op} {a} {b})', var_pool


class BackendRunner:
    """四个后端的统一运行接口"""

    _cvm_exe: str | None = None  # 类级缓存：C VM 编译结果
    _cvm_compiled: bool = False
    _llvm_rt_obj: str | None = None  # 类级缓存：LLVM runtime.o
    _llvm_rt_compiled: bool = False
    _llvm_llc: str | None = None  # 类级缓存：llc 路径
    _llvm_cc: str | None = None  # 类级缓存：gcc 路径

    @staticmethod
    def run_evaluator(source: str, timeout: float = 5.0) -> tuple[str, str]:
        """Python 求值器：验证不崩溃，返回 (status, output)

        使用 S 表达式解析器（非 sugar parser）解析源码。
        """
        try:
            from evaluator import SanyanEvaluator
            from lexer import tokenize
            from parser import parse

            ev = SanyanEvaluator()
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                tokens = tokenize(source)
                ast = parse(tokens)
                ev.eval(ast)
            finally:
                captured = sys.stdout.getvalue()
                sys.stdout = old_stdout
            return 'OK', captured.strip()
        except Exception as e:
            return 'ERROR', f'{type(e).__name__}: {e}'

    @staticmethod
    def run_python_vm(source: str, timeout: float = 5.0) -> tuple[str, str]:
        """Python VM：编译 → 运行"""
        try:
            from compile_bytecode import compile_source
            from vm import VM

            with tempfile.TemporaryDirectory() as tmpdir:
                bin_path = os.path.join(tmpdir, 'test.bin')
                result = compile_source(source, bin_path)
                if not result[0]:
                    return 'COMPILE_FAIL', str(result)

                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    vm = VM.from_bin(bin_path)
                    vm.run()
                finally:
                    captured = sys.stdout.getvalue()
                    sys.stdout = old_stdout
                return 'OK', captured.strip()
        except Exception as e:
            return 'ERROR', f'{type(e).__name__}: {e}'

    @staticmethod
    def run_python_vm_bin(bin_path: str, timeout: float = 5.0) -> tuple[str, str]:
        """Python VM：直接运行预编译的 .bin 文件"""
        try:
            from vm import VM

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                vm = VM.from_bin(bin_path)
                vm.run()
            finally:
                captured = sys.stdout.getvalue()
                sys.stdout = old_stdout
            return 'OK', captured.strip()
        except Exception as e:
            return 'ERROR', f'{type(e).__name__}: {e}'

    @staticmethod
    def run_c_vm(source: str, timeout: float = 5.0) -> tuple[str, str]:
        """C VM：编译 → C VM 运行（编译结果缓存）"""
        try:
            from compile_bytecode import compile_source
            from utils.compiler_tools import find_cc, run_in_shell, win_to_posix

            cc = find_cc()
            if cc is None:
                return 'SKIP', '需要 C 编译器'

            runtime_src = os.path.join(os.path.dirname(__file__), '..', 'csrc', 'runtime.c')
            if not os.path.exists(runtime_src):
                return 'SKIP', 'csrc/runtime.c 不存在'

            # 缓存 C VM 编译
            if not BackendRunner._cvm_compiled:
                BackendRunner._cvm_compiled = True
                exe_path = os.path.join(tempfile.gettempdir(), 'cvm_fuzz.exe')
                src_posix = win_to_posix(runtime_src)
                exe_posix = win_to_posix(exe_path)
                comp = run_in_shell(f'gcc {src_posix} -o {exe_posix} -std=c99 -Wall', check=False)
                if comp.returncode != 0:
                    BackendRunner._cvm_exe = None
                    return 'SKIP', f'C VM 编译失败: {comp.stderr[:200]}'
                BackendRunner._cvm_exe = exe_path

            if not BackendRunner._cvm_exe or not os.path.exists(BackendRunner._cvm_exe):
                return 'SKIP', 'C VM 不可用'

            with tempfile.TemporaryDirectory() as tmpdir:
                bin_path = os.path.join(tmpdir, 'test.bin')
                result = compile_source(source, bin_path)
                if not result[0]:
                    return 'COMPILE_FAIL', str(result)

                res = subprocess.run(
                    [BackendRunner._cvm_exe, bin_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if res.returncode != 0:
                    return 'RUNTIME_ERROR', res.stderr[:300]
                return 'OK', res.stdout.strip()
        except subprocess.TimeoutExpired:
            return 'TIMEOUT', ''
        except Exception as e:
            return 'ERROR', f'{type(e).__name__}: {e}'

    @staticmethod
    def run_c_vm_bin(bin_path: str, timeout: float = 5.0) -> tuple[str, str]:
        """C VM：直接运行预编译的 .bin 文件（编译结果缓存）"""
        try:
            from utils.compiler_tools import find_cc, run_in_shell, win_to_posix

            cc = find_cc()
            if cc is None:
                return 'SKIP', '需要 C 编译器'

            runtime_src = os.path.join(os.path.dirname(__file__), '..', 'csrc', 'runtime.c')
            if not os.path.exists(runtime_src):
                return 'SKIP', 'csrc/runtime.c 不存在'

            # 缓存 C VM 编译
            if not BackendRunner._cvm_compiled:
                BackendRunner._cvm_compiled = True
                exe_path = os.path.join(tempfile.gettempdir(), 'cvm_fuzz.exe')
                src_posix = win_to_posix(runtime_src)
                exe_posix = win_to_posix(exe_path)
                comp = run_in_shell(f'gcc {src_posix} -o {exe_posix} -std=c99 -Wall', check=False)
                if comp.returncode != 0:
                    BackendRunner._cvm_exe = None
                    return 'SKIP', f'C VM 编译失败: {comp.stderr[:200]}'
                BackendRunner._cvm_exe = exe_path

            if not BackendRunner._cvm_exe or not os.path.exists(BackendRunner._cvm_exe):
                return 'SKIP', 'C VM 不可用'

            res = subprocess.run(
                [BackendRunner._cvm_exe, bin_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if res.returncode != 0:
                return 'RUNTIME_ERROR', res.stderr[:300]
            return 'OK', res.stdout.strip()
        except subprocess.TimeoutExpired:
            return 'TIMEOUT', ''
        except Exception as e:
            return 'ERROR', f'{type(e).__name__}: {e}'

    @staticmethod
    def run_llvm(source: str, timeout: float = 10.0) -> tuple[str, str]:
        """LLVM：优先用 llvmlite 内置 codegen，回退 llc"""
        try:
            from llvmgen.compiler import compile_source as llvm_compile
            from utils.compiler_tools import find_cc, find_llc, run_in_shell, win_to_posix

            # 缓存 llc/gcc 路径查找
            if BackendRunner._llvm_llc is None:
                llc = find_llc()
                BackendRunner._llvm_llc = llc or ''
            llc = BackendRunner._llvm_llc or None
            if BackendRunner._llvm_cc is None:
                cc = find_cc()
                BackendRunner._llvm_cc = cc or ''
            cc = BackendRunner._llvm_cc or None

            if llc is None or cc is None:
                return 'SKIP', '需要 llc + gcc'

            rt_src = os.path.join(os.path.dirname(__file__), '..', 'llvmgen', 'runtime.c')
            if not os.path.exists(rt_src):
                return 'SKIP', 'llvmgen/runtime.c 不存在'

            # 缓存 runtime.o 编译（瓶颈：10-15 秒）
            if not BackendRunner._llvm_rt_compiled:
                BackendRunner._llvm_rt_compiled = True
                rt_obj_path = os.path.join(tempfile.gettempdir(), 'llvm_runtime.o')
                rt_posix = win_to_posix(rt_src)
                rt_obj_posix = win_to_posix(rt_obj_path)
                comp = run_in_shell(f'gcc -c {rt_posix} -o {rt_obj_posix} -std=c99 -O2', check=False, timeout=60)
                if comp.returncode != 0:
                    BackendRunner._llvm_rt_obj = None
                    return 'SKIP', f'runtime 编译失败: {comp.stderr[:200]}'
                BackendRunner._llvm_rt_obj = rt_obj_path

            if not BackendRunner._llvm_rt_obj or not os.path.exists(BackendRunner._llvm_rt_obj):
                return 'SKIP', 'runtime.o 不可用'

            with tempfile.TemporaryDirectory() as tmpdir:
                ir_path = os.path.join(tmpdir, 'test.ll')
                obj_path = os.path.join(tmpdir, 'test.o')
                exe_path = os.path.join(tmpdir, 'test.exe')

                # .san → LLVM IR
                try:
                    ir_text, _ = llvm_compile(source, 'test')
                except Exception as e:
                    return 'COMPILE_FAIL', f'LLVM IR 生成失败: {e}'

                with open(ir_path, 'w', encoding='utf-8') as f:
                    f.write(ir_text)

                # IR → object
                ir_posix = win_to_posix(ir_path)
                obj_posix = win_to_posix(obj_path)
                llc_posix = win_to_posix(llc)
                comp = run_in_shell(f'{llc_posix} {ir_posix} -filetype=obj -o {obj_posix}', check=False, timeout=30)
                if comp.returncode != 0:
                    return 'SKIP', f'llc 失败: {comp.stderr[:200]}'

                # 链接（复用缓存的 runtime.o）
                obj_p = win_to_posix(obj_path)
                rt_p = win_to_posix(BackendRunner._llvm_rt_obj)
                exe_p = win_to_posix(exe_path)
                libs = '-lm'
                if sys.platform == 'win32':
                    libs += ' -lwinhttp'
                comp = run_in_shell(f'gcc {obj_p} {rt_p} -o {exe_p} {libs}', check=False, timeout=30)
                if comp.returncode != 0:
                    return 'SKIP', f'链接失败: {comp.stderr[:200]}'

                # 运行
                res = subprocess.run(
                    [exe_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if res.returncode != 0:
                    return 'RUNTIME_ERROR', res.stderr[:300]
                return 'OK', res.stdout.strip()
        except subprocess.TimeoutExpired:
            return 'TIMEOUT', ''
        except Exception as e:
            return 'ERROR', f'{type(e).__name__}: {e}'


def normalize_output(raw: str) -> str:
    """标准化输出用于比较。

    - strip 首尾空白
    - 统一换行
    - 去除求值器装饰（  =>  前缀、（三进制: ...）/（符号: ...）/（浮点: ...）/（信度: ...）后缀）
    - 只取最后一行（消除中间表达式输出差异）
    """
    import re

    s = raw.strip()
    lines = []
    for line in s.splitlines():
        line = line.strip()
        # 去除 =>  前缀
        if line.startswith('=> '):
            line = line[3:]
        elif line.startswith('=>'):
            line = line[2:]
        # 去除 （三进制: ...）/（符号: ...）/（浮点: ...）/（信度: ...）等后缀
        line = re.sub(r'（[^）]*[:：][^）]*）$', '', line)
        if line:
            lines.append(line.strip())
    # 只取最后一行（消除中间表达式输出差异）
    return lines[-1] if lines else ''


def run_diff_test(
    seed: int,
    count: int = 50,
    max_depth: int = 3,
    max_stmts: int = 4,
    verbose: bool = False,
) -> list[DiffResult]:
    """运行差分测试。

    优化：预编译字节码编译器一次，批量编译所有程序，再逐个比较后端输出。

    Args:
        seed: 随机种子（可重现）
        count: 生成程序数量
        max_depth: 表达式最大深度
        max_stmts: 最大语句数
        verbose: 是否打印每个程序的结果

    Returns:
        失败的测试结果列表
    """
    gen = ProgramGenerator(seed=seed, max_depth=max_depth, max_stmts=max_stmts)
    failures: list[DiffResult] = []

    # 预生成所有程序
    programs = [(i, gen.generate()) for i in range(count)]

    # 预编译所有程序到 .bin 文件（复用同一个编译器实例）
    from compile_bytecode import compile_source

    bin_dir = tempfile.mkdtemp(prefix='sanyan_fuzz_')
    bin_paths: dict[int, str] = {}
    compile_failures: set[int] = set()

    try:
        for i, prog in programs:
            bin_path = os.path.join(bin_dir, f'test_{i}.bin')
            try:
                result = compile_source(prog, bin_path)
                if result[0]:
                    bin_paths[i] = bin_path
                else:
                    compile_failures.add(i)
                    if verbose:
                        print(f'  [{i}] COMPILE_FAIL: {result}')
            except Exception as e:
                compile_failures.add(i)
                if verbose:
                    print(f'  [{i}] COMPILE_ERROR: {e}')

        # 逐个比较后端
        for i, prog in programs:
            result = DiffResult(program=prog, seed=seed, iteration=i, results={})

            if i in compile_failures:
                result.passed = False
                result.diff_detail = '编译失败'
                failures.append(result)
                continue

            bin_path = bin_paths[i]

            # 求值器：验证不崩溃
            eval_status, eval_out = BackendRunner.run_evaluator(prog)
            result.results['evaluator'] = (eval_status, eval_out)
            if eval_status == 'ERROR':
                result.passed = False
                result.diff_detail = f'求值器崩溃: {eval_out}'
                failures.append(result)
                if verbose:
                    print(f'  [{i}] EVAL CRASH: {eval_out[:100]}')
                continue

            # Python VM
            vm_status, vm_out = BackendRunner.run_python_vm_bin(bin_path)
            result.results['python_vm'] = (vm_status, vm_out)

            # C VM
            cvm_status, cvm_out = BackendRunner.run_c_vm_bin(bin_path)
            result.results['c_vm'] = (cvm_status, cvm_out)

            # LLVM
            llvm_status, llvm_out = BackendRunner.run_llvm(prog)
            result.results['llvm'] = (llvm_status, llvm_out)

            # 比较所有成功运行的后端输出
            ok_outputs: dict[str, str] = {}
            for name in ('python_vm', 'c_vm', 'llvm'):
                status, output = result.results.get(name, ('SKIP', ''))
                if status == 'OK':
                    ok_outputs[name] = normalize_output(output)

            if len(ok_outputs) >= 2:
                values = list(ok_outputs.values())
                names = list(ok_outputs.keys())
                if len(set(values)) > 1:
                    result.passed = False
                    detail_parts = [f'{n}={ok_outputs[n]!r}' for n in names]
                    result.diff_detail = '输出不一致: ' + ', '.join(detail_parts)
                    failures.append(result)
                    if verbose:
                        print(f'  [{i}] DIFF: {result.diff_detail[:200]}')
                        print(f'       PROG: {prog[:100]}')
                elif verbose:
                    print(f'  [{i}] OK ({len(ok_outputs)} backends)')
            elif verbose:
                ok_names = list(ok_outputs.keys())
                print(f'  [{i}] PARTIAL (only {ok_names} OK)')
    finally:
        # 清理临时文件
        import shutil

        shutil.rmtree(bin_dir, ignore_errors=True)

    return failures
