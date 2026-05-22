"""三言字节码编译器 — Python 包装

编译 .san → .bin，支持 sugar 语法和 S-表达式。
用法:
    python compile_bytecode.py input.san [-o output.bin] [--run]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer import tokenize
from parser import parse
from evaluator import SanyanEvaluator
from sugar.parser import parse_code as sugar_parse
from ops.file_ops import clear_cache


def compile_source(source: str, output_path: str, vars_table: dict = None) -> list:
    """编译源码字符串为 .bin 文件。返回 [成功, 代码大小, 变量数]。"""
    if vars_table is None:
        vars_table = {}

    # 将 __exports__ 从变量表中分离（避免被当作变量引用）
    export_names = vars_table.pop('__exports__', []) if isinstance(vars_table, dict) else []

    # 先试 sugar 语法解析
    try:
        ast, errors = sugar_parse(source)
        if ast and not any(e for e in errors if '语法' in e.lower() or 'syntax' in e.lower()):
            if isinstance(ast, list) and len(ast) > 0 and ast[0] == 'do':
                sugar_ast = ast
            else:
                sugar_ast = ['do', ast]
        else:
            sugar_ast = None
    except SyntaxError:
        sugar_ast = None

    if sugar_ast:
        ast = sugar_ast
    else:
        # S-表达式降级
        wrapped = '(do\n' + source + '\n)'
        tokens = tokenize(wrapped)
        ast = parse(tokens)
        if ast is None:
            raise SyntaxError('解析失败')

    # 将 __exports__ 导出名添加到 AST
    if export_names and isinstance(ast, list) and len(ast) > 0 and isinstance(ast[0], str):
        for name in export_names:
            ast.append(['export', name])

    # 加载编译器
    e = SanyanEvaluator(max_loop_steps=100000)
    clear_cache()
    compiler = e.eval(['import', 'stdlib/bytecode_compiler.san'])
    if compiler is None:
        raise RuntimeError('加载 bytecode_compiler.san 失败')

    result = compiler.call(e, ['编译字节码', ast, output_path, vars_table])
    return result


def compile_san(source_path: str, output_path: str = None) -> bytes:
    """读取 .san 源码文件，编译为 .bin。返回 .bin 内容。"""
    if not output_path:
        output_path = source_path.replace('.san', '.bin')

    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()

    result = compile_source(source, output_path)
    success, size, vars_count = result
    print(f'✓ 编译 {source_path} → {output_path}: {size} 字节, {vars_count} 变量')

    with open(output_path, 'rb') as f:
        return f.read()


def run_bin(bin_path: str) -> None:
    """执行编译后的 .bin 文件。"""
    from vm import VM
    vm = VM.from_bin(bin_path)
    print(f'▶ 运行 {bin_path}: {len(vm.code)} 字节代码, {len(vm.vars)} 变量')
    vm.run()
    print('✓ 执行完毕')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    args = sys.argv[1:]
    run_mode = '--run' in args
    args = [a for a in args if not a.startswith('--')]

    input_path = args[0]
    output_path = args[2] if len(args) > 2 and args[1] == '-o' else \
        input_path.replace('.san', '.bin')

    data = compile_san(input_path, output_path)
    magic = data[:4]
    ver = data[4]
    sz = data[6] | (data[7] << 8)
    print(f'  SAN0 v{ver}, {sz} 字节, 文件 {len(data)} 字节')

    if run_mode:
        run_bin(output_path)


if __name__ == '__main__':
    main()
