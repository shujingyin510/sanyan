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
from values import SanyanSyntaxError, SanyanRuntimeError

COMPILER_MAX_LOOP = 100000

# ── 常量折叠优化 ──
_CONST_OPS = {
    'add': lambda a, b: a + b,
    '加': lambda a, b: a + b,
    'sub': lambda a, b: a - b,
    '减': lambda a, b: a - b,
    'mul': lambda a, b: a * b,
    '乘': lambda a, b: a * b,
    'div': lambda a, b: a // b if b != 0 else 0,
    '除': lambda a, b: a // b if b != 0 else 0,
    'mod': lambda a, b: a % b if b != 0 else 0,
    '余': lambda a, b: a % b if b != 0 else 0,
    'eq': lambda a, b: 1 if a == b else -1,
    '等于': lambda a, b: 1 if a == b else -1,
}


def _fold_constants(node):
    """递归常量折叠：将 ['add', 1, 2] 替换为 3。仅处理纯常量子树。"""
    if not isinstance(node, list) or len(node) == 0:
        return node
    op = node[0]
    # 先递归折叠子节点
    folded = [op] + [_fold_constants(a) for a in node[1:]]
    # 检查是否所有参数都是常量（op 必须是字符串，跳过嵌套列表如参数定义）
    if isinstance(op, str) and op in _CONST_OPS:
        args = folded[1:]
        if all(isinstance(a, (int, float)) for a in args) and len(args) == 2:
            try:
                return _CONST_OPS[op](args[0], args[1])
            except (ZeroDivisionError, TypeError):
                pass
    return folded


def compile_source(source: str, output_path: str, vars_table: dict | None = None) -> list:
    """编译源码字符串为 .bin 文件。返回 [成功, 代码大小, 变量数]。"""
    from preprocess import preprocess_includes

    if vars_table is None:
        vars_table = {}

    # 预处理 #include 指令
    source = preprocess_includes(source)

    # 将 __exports__ 从变量表中分离（避免被当作变量引用）
    export_names = vars_table.pop('__exports__', []) if isinstance(vars_table, dict) else []

    # 解析源码为 AST
    # 检测 S-表达式输入（以 ( 开头且括号平衡），直接用 S-表达式解析器
    ast = None
    sugar_ast = None
    is_sexpr = source.strip().startswith('(') and source.count('(') == source.count(')')

    if not is_sexpr:
        # 1. 尝试 sugar 解析器
        try:
            sugar_result, errors = sugar_parse(source)
            has_syntax_err = any(isinstance(e, str) and '行' in e and ('：' in e or ':' in e) for e in errors)
            if sugar_result and not has_syntax_err:
                if isinstance(sugar_result, list) and len(sugar_result) > 0 and sugar_result[0] == 'do':
                    sugar_ast = sugar_result
                else:
                    sugar_ast = ['do', sugar_result]
        except (SyntaxError, Exception):
            pass

    # 2. 如果 sugar 解析失败或跳过，尝试 S-表达式解析器
    if not sugar_ast:
        try:
            tokens = tokenize(source)
            s_expr_ast = parse(tokens)
            if s_expr_ast is not None:
                if isinstance(s_expr_ast, list) and len(s_expr_ast) > 0 and s_expr_ast[0] == '做':
                    # S-表达式用 (做 ...) 作为顶层包装
                    sugar_ast = ['do'] + s_expr_ast[1:]
                elif isinstance(s_expr_ast, list):
                    sugar_ast = ['do', s_expr_ast]
                else:
                    sugar_ast = ['do', s_expr_ast]
        except Exception:
            pass

    if not sugar_ast:
        raise SanyanSyntaxError('解析失败，请检查语法（支持 sugar 和 S-表达式两种语法）')

    ast = sugar_ast
    # 自动提取 sugar AST 中的 (export ...) / (导出 ...) 节点
    if not export_names:
        fixed = []
        for s in ast[1:]:
            if isinstance(s, list) and s[0] == 'export':
                for n in s[1:]:
                    if n != '导出':
                        export_names.append(n)
            else:
                fixed.append(s)
        ast = ['do'] + fixed

    # 将 __exports__ 导出名添加到 AST
    if export_names and isinstance(ast, list) and len(ast) > 0 and isinstance(ast[0], str):
        for name in export_names:
            ast.append(['export', name])

    # 常量折叠优化：递归合并常量子树
    ast = _fold_constants(ast)

    # 加载编译器
    e = SanyanEvaluator(max_loop_steps=COMPILER_MAX_LOOP)
    clear_cache()
    compiler = e.eval(['import', 'stdlib/bytecode_compiler.san'])
    if compiler is None:
        raise SanyanRuntimeError('加载 bytecode_compiler.san 失败')

    result = compiler.call(e, ['编译字节码', ast, output_path, vars_table])
    return result  # type: ignore[no-any-return]


def compile_san(source_path: str, output_path: str | None = None) -> bytes:
    """读取 .san 源码文件，编译为 .bin。返回 .bin 内容。"""
    if not output_path:
        output_path = source_path.replace('.san', '.bin')

    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()

    result = compile_source(source, output_path)
    success, size, vars_count = result
    if not success:
        raise SanyanRuntimeError(f'编译 {source_path} 失败')
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
    output_path = (
        args[2]
        if len(args) > 2 and args[1] == '-o'
        else os.path.join('build', os.path.basename(input_path.replace('.san', '.bin')))
    )

    data = compile_san(input_path, output_path)
    ver = data[4]
    sz = data[6] | (data[7] << 8) | (data[8] << 16) | (data[9] << 24)
    print(f'  SAN0 v{ver}, {sz} 字节, 文件 {len(data)} 字节')

    if run_mode:
        run_bin(output_path)


if __name__ == '__main__':
    main()
