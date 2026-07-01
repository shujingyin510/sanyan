"""三言 —— 中文三进制编程语言（主入口）"""

import sys
import os
import subprocess

from evaluator import SanyanEvaluator
from sugar import SugarConverter
from ternary_core import TritValue
from skin import SkinManager
from values import SanyanError


def _compile_ir_to_exe(ir_text: str, suffix: str, gcc_env: dict | None = None) -> str:
    """将 LLVM IR 文本编译为原生可执行文件，返回 exe 路径。"""
    import subprocess

    out_name = 'sanyan_out'
    out_exe = os.path.join('build', out_name + f'_{suffix}.exe')
    os.makedirs('build', exist_ok=True)
    ir_path = os.path.join('build', out_name + f'_{suffix}.ll')
    obj_path = os.path.join('build', out_name + f'_{suffix}.o')

    with open(ir_path, 'w', encoding='utf-8') as f:
        f.write(ir_text)
    print(f'[{suffix}] LLVM IR → {ir_path} ({len(ir_text)} bytes)')

    # 优先使用 llc（无 Python 依赖）
    from utils.compiler_tools import find_llc

    obj_ok = False
    llc = find_llc()
    if llc:
        try:
            subprocess.run([llc, '-filetype=obj', ir_path, '-o', obj_path], check=True, timeout=30)
            obj_ok = True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    if not obj_ok:
        # 回退: llvmlite
        try:
            from llvmlite import binding as llvm_binding

            llvm_binding.initialize_all_targets()
            llvm_binding.initialize_native_asmprinter()
            target = llvm_binding.Target.from_default_triple()
            tm = target.create_target_machine(reloc='static', codemodel='large')
            asm = tm.emit_assembly(llvm_binding.parse_assembly(ir_text))
            asm_path = os.path.join('build', out_name + f'_{suffix}.s')
            with open(asm_path, 'w') as f:
                f.write(asm)
            print(f'[{suffix}] ASM → {asm_path}')
        except Exception as e:
            raise RuntimeError(f'无法编译 LLVM IR: {e}\nIR 文件: {ir_path}')

    print(f'[{suffix}] OBJ → {obj_path}')

    if gcc_env is None:
        gcc_env = os.environ.copy()
    gcc = os.environ.get('GCC', 'gcc')
    if 'GCC_PATH' in os.environ:
        gcc_env['PATH'] = os.environ['GCC_PATH'] + os.pathsep + gcc_env.get('PATH', '')
    sc_o = os.path.join('build', 'syscall.o')
    subprocess.run(
        [gcc, '-c', 'llvmgen/syscall.c', '-o', sc_o, '-std=c99', '-O2', '-nostartfiles'],
        check=True,
        env=gcc_env,
    )
    subprocess.run([gcc, '-c', obj_path, '-o', obj_path], check=True, env=gcc_env)
    subprocess.run(
        [
            gcc,
            obj_path,
            sc_o,
            '-o',
            out_exe,
            '-nostartfiles',
            '-e',
            'main',
            '-lkernel32',
            '-lgcc',
            '-fno-stack-check',
            '-fno-stack-protector',
        ],
        check=True,
        env=gcc_env,
    )
    print(f'[{suffix}] EXE → {out_exe}')
    return out_exe


def _parse_file(code_str):
    """解析源码为 AST：先 Sugar 后 S-表达式。返回 (ast, None) 或 (None, error_msg)。"""

    skin_mgr = SkinManager('chinese')
    try:
        return SugarConverter.convert(code_str, skin_mgr), None
    except SyntaxError as e:
        from lexer import tokenize
        from parser import parse

        try:
            tokens = tokenize(code_str)
            return parse(tokens), str(e)
        except SyntaxError as e2:
            return None, f'{e2}\n  (sugar 语法解析也失败: {e})'


def _run_evaluator(code, profiling):
    """Python 求值器模式：解析 → 求值 → 返回 (env, result, ast)。"""

    skin_mgr = SkinManager('chinese')
    env = SanyanEvaluator(skin_manager=skin_mgr)
    env._source = code  # 设置源码用于错误信息显示
    if profiling:
        env.profile_start()

    ast, sugar_error = _parse_file(code)
    if ast is None:
        print(f'语法错误: {sugar_error}')
        sys.exit(1)

    try:
        result = env.eval(ast)
    except (SanyanError, SyntaxError, RecursionError) as e:
        import traceback

        traceback.print_exc()
        print(f'执行错误: {e}')
        sys.exit(1)

    if profiling:
        print(env.profile_report())
    return env, result, ast


def _auto_print_result(ast, result, env):
    """如果 AST 没有显式输出语句，自动打印最终结果。"""
    if result is None:
        return
    _output_op_names = {'print', '输出', 'debug', '调试', 'query', '查'}
    if skin_mgr := getattr(env, 'skin_manager', None):
        for internal in ('print', 'debug', 'query'):
            kw = skin_mgr.get_keyword(internal) or skin_mgr.get_op(internal)
            if kw:
                _output_op_names.add(kw)
                if isinstance(kw, list):
                    _output_op_names.update(kw)

    def _has_output_like(node):
        if isinstance(node, list) and len(node) > 0:
            if node[0] in _output_op_names:
                return True
            for child in node[1:]:
                if _has_output_like(child):
                    return True
        return False

    if not _has_output_like(ast):
        if isinstance(result, TritValue):
            if result.is_float():
                print(f'结果: {result.to_float()}')
            else:
                print(f'结果: {result.to_int()}')
        else:
            print(f'结果: {result}')


def _run_native(code, mode, filepath):
    """原生编译模式（--san 或 --pycc）。返回 exit code。"""
    if mode == 'pycc':
        from skin import SkinManager
        from sugar import SugarConverter
        from llvmgen.codegen import compile_top_level

        skin_mgr = SkinManager('chinese')
        ast = SugarConverter.convert(code, skin_mgr)
        cg = compile_top_level(ast)
        out_exe = _compile_ir_to_exe(str(cg.module), 'pycc')
    else:
        from llvmgen.compiler import self_hosted_compile

        ir_text = self_hosted_compile(code)
        out_exe = _compile_ir_to_exe(ir_text, 'san')

    result = subprocess.run([out_exe], capture_output=True, text=True)
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, end='', file=sys.stderr)
    sys.exit(result.returncode)


def main():
    """三言入口：根据标志分派到不同运行模式。
    --eval: Python 求值器    --vm: 字节码 VM
    --profile: 性能剖析    --san/--pycc: 原生编译
    默认: 字节码编译 + VM 执行"""
    args = sys.argv[1:]

    if '--ast-json' in args:
        idx = args.index('--ast-json')
        if idx + 1 >= len(args):
            print('错误: --ast-json 需要文件路径')
            sys.exit(1)
        filepath = args[idx + 1]
        from lexer import tokenize
        from parser import parse
        import json

        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        tokens = tokenize(code)
        ast = parse(tokens)

        def _ast_to_json(node):
            return [_ast_to_json(n) for n in node] if isinstance(node, list) else node

        print(json.dumps(_ast_to_json(ast), ensure_ascii=False, indent=2))
        sys.exit(0)

    profiling = '--profile' in args
    use_eval = '--eval' in args
    use_san = '--san' in args
    use_pycc = '--pycc' in args
    positional = [a for a in args if not a.startswith('--')]

    if not positional:
        print(__doc__)
        sys.exit(0)

    filepath = positional[0]
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
    except FileNotFoundError:
        print(f'错误: 文件不存在 - {filepath}')
        sys.exit(1)

    if use_pycc and not profiling:
        _run_native(code, 'pycc', filepath)
    if use_san and not profiling:
        _run_native(code, 'san', filepath)
    if not code.strip():
        sys.exit(0)

    from preprocess import preprocess_includes

    code = preprocess_includes(code)

    # 字节码缓存 + VM 执行（默认模式）
    if not use_eval and not profiling:
        bin_path = os.path.join('build', os.path.basename(filepath).replace('.san', '.bin'))
        if not os.path.exists(bin_path) or os.path.getmtime(bin_path) < os.path.getmtime(filepath):
            os.makedirs('build', exist_ok=True)
            from compile_bytecode import compile_san

            try:
                compile_san(filepath, bin_path)
            except Exception:
                use_eval = True  # 编译失败回退求值器

        if not use_eval:
            from vm import VM as SanyanVM

            try:
                SanyanVM.from_bin(bin_path)
                sys.exit(0)
            except Exception:
                use_eval = True  # VM 执行失败也回退

    # Python 求值器模式
    env, result, ast = _run_evaluator(code, profiling)

    # 保存字节码缓存（加速下次运行）
    bin_path = os.path.join('build', os.path.basename(filepath).replace('.san', '.bin'))
    os.makedirs('build', exist_ok=True)
    try:
        from compile_bytecode import compile_san

        compile_san(filepath, bin_path)
    except (SanyanError, SyntaxError, OSError):
        pass

    _auto_print_result(ast, result, env)


if __name__ == '__main__':
    main()
