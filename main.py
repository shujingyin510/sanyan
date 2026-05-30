"""三言 —— 中文三进制编程语言（主入口）"""

import sys
import os
import subprocess
from repl import demo, repl

from sanyan import __version__ as VERSION
from evaluator import SanyanEvaluator
from sugar import SugarConverter
from ternary_core import TritValue
from skin import SkinManager


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
    obj_ok = False
    for llc in ['llc', 'llc.exe', r'D:\msys64\ucrt64\bin\llc.exe', r'D:\msys64\mingw64\bin\llc.exe']:
        try:
            subprocess.run([llc, '-filetype=obj', ir_path, '-o', obj_path], check=True, timeout=30)
            obj_ok = True
            break
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue

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


def main():
    args = sys.argv[1:]

    # --ast-json 标志：输出 AST JSON 并退出
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
            if isinstance(node, list):
                return [_ast_to_json(n) for n in node]
            return node

        print(json.dumps(_ast_to_json(ast), ensure_ascii=False, indent=2))
        sys.exit(0)

    # --profile 标志
    profiling = '--profile' in args
    # --eval 标志：使用 Python 求值器（调试模式，较慢）
    use_eval = '--eval' in args
    # --vm 标志：保留向后兼容，等同于默认行为
    use_vm = '--vm' in args
    # --san 标志：使用自举编译器（sugar.san + llvmgen.san）生成原生可执行文件
    use_san = '--san' in args
    # --pycc 标志：使用 Python codegen（SugarConverter 解析 + Python LLVM codegen）生成原生可执行文件
    use_pycc = '--pycc' in args
    positional = [a for a in args if not a.startswith('--')]

    if positional:
        filepath = positional[0]
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
        except FileNotFoundError:
            print(f'错误: 文件不存在 - {filepath}')
            sys.exit(1)
        except UnicodeDecodeError:
            print(f'错误: 文件编码不是UTF-8 - {filepath}')
            sys.exit(1)

        if use_pycc and not profiling:
            # ── Python 原生编译路径：SugarConverter 解析 + Python codegen 生成 IR → 原生可执行文件 ──
            skin_mgr = SkinManager('chinese')
            ast = SugarConverter.convert(code, skin_mgr)
            from llvmgen.codegen import compile_top_level

            cg = compile_top_level(ast)
            out_exe = _compile_ir_to_exe(str(cg.module), 'pycc')
            result = subprocess.run([out_exe], capture_output=True, text=True)
            print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            sys.exit(result.returncode)

        if use_san and not profiling:
            # ── 自举编译路径：sugar.san 解析 + llvmgen.san 生成 IR → 原生可执行文件 ──
            from llvmgen.compiler import self_hosted_compile

            ir_text = self_hosted_compile(code)
            out_exe = _compile_ir_to_exe(ir_text, 'san')
            result = subprocess.run([out_exe], capture_output=True, text=True)
            print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            sys.exit(result.returncode)

        if not code.strip():
            sys.exit(0)

        from preprocess import preprocess_includes

        code = preprocess_includes(code)

        # ── 字节码缓存检查（默认模式，--eval 时跳过）──
        bin_path = os.path.join('build', os.path.basename(filepath).replace('.san', '.bin'))
        if not use_eval and not profiling:
            if not os.path.exists(bin_path) or os.path.getmtime(bin_path) < os.path.getmtime(filepath):
                os.makedirs('build', exist_ok=True)
                from compile_bytecode import compile_san

                compile_san(filepath, bin_path)
            from vm import VM as SanyanVM

            SanyanVM.from_bin(bin_path)
            sys.exit(0)

        # ── Python 求值器模式（--eval 或 --profile）──

        skin_mgr = SkinManager('chinese')
        env: SanyanEvaluator = SanyanEvaluator(skin_manager=skin_mgr)
        if profiling:
            env.profile_start()

        ast = None
        sugar_error = None
        try:
            ast = SugarConverter.convert(code, skin_mgr)
        except SyntaxError as e:
            sugar_error = str(e)

        if ast is None:
            from lexer import tokenize
            from parser import parse

            try:
                tokens = tokenize(code)
                ast = parse(tokens)
            except SyntaxError as e:
                msg = str(e)
                if sugar_error:
                    msg = f'{msg}\n  (sugar 语法解析也失败: {sugar_error})'
                print(f'语法错误: {msg}')
                import traceback

                traceback.print_exc()
                sys.exit(1)

        try:
            result = env.eval(ast)
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f'执行错误: {e}')
            sys.exit(1)

        # ── 保存字节码缓存 ──
        os.makedirs('build', exist_ok=True)
        try:
            from compile_bytecode import compile_san

            compile_san(filepath, bin_path)
        except Exception:
            pass

        if profiling:
            print(env.profile_report())

        if result is not None:

            def _has_output_like(node):
                if isinstance(node, list) and len(node) > 0:
                    if node[0] in ('print', 'concat', 'query', 'debug', '输出', '连接', '查', '调试'):
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
        sys.exit(0)
    else:
        print(f'欢迎来到「三言 v{VERSION}」—— 母语可定制的三进制编程语言')
        print('=' * 50)
        demo(SkinManager('chinese'))
        repl()


if __name__ == '__main__':
    main()
