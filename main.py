"""三言 —— 中文三进制编程语言（主入口）"""

import sys
import os
from repl import demo, repl
import tomllib

with open('pyproject.toml', 'rb') as f:
    VERSION = tomllib.load(f)['project']['version']
from evaluator import SanyanEvaluator
from sugar import SugarConverter
from ternary_core import TritValue
from skin import SkinManager


def main():
    args = sys.argv[1:]

    # --ast-json 标志：输出 AST JSON 并退出
    if '--ast-json' in args:
        idx = args.index('--ast-json')
        if idx + 1 >= len(args):
            print('错误: --ast-json 需要文件路径')
            sys.exit(1)
        filepath = args[idx + 1]
        from ast_json import ast_from_file, ast_to_json

        ast = ast_from_file(filepath)
        import json

        print(json.dumps(ast_to_json(ast), ensure_ascii=False, indent=2))
        sys.exit(0)

    # --profile 标志
    profiling = '--profile' in args
    # --vm 标志：使用字节码 VM 执行（更快，但部分复杂程序可能不兼容）
    use_vm = '--vm' in args
    # --san 标志：使用自举编译器（sugar.san + llvmgen.san）生成原生可执行文件
    use_san = '--san' in args
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

        if use_san and not profiling:
            # ── 自举编译路径：sugar.san 解析 + llvmgen.san 生成 IR → 原生可执行文件 ──
            from llvmgen.compiler import self_hosted_compile
            import tempfile, subprocess

            ir_text = self_hosted_compile(code)
            out_name = os.path.splitext(os.path.basename(filepath))[0]
            out_exe = os.path.join('build', out_name + '_san.exe')

            os.makedirs('build', exist_ok=True)
            ir_path = os.path.join('build', out_name + '_san.ll')
            asm_path = os.path.join('build', out_name + '_san.s')

            with open(ir_path, 'w', encoding='utf-8') as f:
                f.write(ir_text)
            print(f'[san] LLVM IR → {ir_path}')

            # llvmlite → asm
            from llvmlite import binding as llvm_binding
            llvm_binding.initialize_all_targets()
            llvm_binding.initialize_native_asmprinter()

            # 合并 runtime.ll + 用户 IR（字符串拼接，移除用户模块头）
            runtime_ll_path = os.path.join('llvmgen', 'runtime.ll')
            if os.path.exists(runtime_ll_path):
                with open(runtime_ll_path, encoding='utf-8') as f:
                    runtime_ir = f.read()
                # 移除用户 IR 的 target triple 和 declare（runtime.ll 已提供）
                user_lines = ir_text.split('\n')
                filtered = []
                skip = False
                for line in user_lines:
                    if 'target triple' in line or 'ModuleID' in line:
                        continue
                    if line.startswith('declare ') and ('@rt_print_int' in line or '@rt_print_str' in line):
                        continue
                    filtered.append(line)
                combined_ir = runtime_ir + '\n' + '\n'.join(filtered)
            else:
                combined_ir = ir_text

            target = llvm_binding.Target.from_default_triple()
            tm = target.create_target_machine(reloc='static', codemodel='large')
            asm = tm.emit_assembly(llvm_binding.parse_assembly(combined_ir))
            with open(asm_path, 'w') as f:
                f.write(asm)
            print(f'[san] ASM → {asm_path}')

            # GCC → exe (零 stdio: -nostartfiles -e main -lkernel32)
            import subprocess as sp
            sc_o = os.path.join('build', 'syscall.o')
            sp.run(['gcc', '-c', 'llvmgen/syscall.c', '-o', sc_o, '-std=c99', '-O2', '-nostartfiles'], check=True)
            sp.run(['gcc', '-c', asm_path, '-o', asm_path.replace('.s', '.o')], check=True)
            sp.run(['gcc', asm_path.replace('.s', '.o'), sc_o, '-o', out_exe,
                     '-nostartfiles', '-e', 'main', '-lkernel32', '-lgcc'], check=True)
            print(f'[san] EXE → {out_exe}')

            result = sp.run([out_exe], capture_output=True, text=True)
            print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            sys.exit(result.returncode)

        if not code.strip():
            sys.exit(0)

        from preprocess import preprocess_includes

        code = preprocess_includes(code)

        # ── 字节码缓存检查（仅 --vm 模式）──
        bin_path = os.path.join('build', os.path.basename(filepath).replace('.san', '.bin'))
        if use_vm and not profiling:
            if not os.path.exists(bin_path) or os.path.getmtime(bin_path) < os.path.getmtime(filepath):
                os.makedirs('build', exist_ok=True)
                from compile_bytecode import compile_san

                compile_san(filepath, bin_path)
            from vm import VM as SanyanVM

            SanyanVM.from_bin(bin_path)
            sys.exit(0)

        skin_mgr = SkinManager('chinese')
        env = SanyanEvaluator(skin_manager=skin_mgr)
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
