"""编译 llvmgen.san → llvmgen.bin

V5: 辅助函数已内联到 llvmgen.san 源码中，无需注入。
直接解析并编译即可。

旧版本（V4 及以前）需要注入 11 个辅助函数和 6 个全局变量。
新版本（V5）的 llvmgen.san 已包含这些定义，实现完全自举。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sugar.parser import parse_code
from core.evaluator import SanyanEvaluator
from ops.file_ops import clear_cache


def ast_ints_to_str(node):
    """将 AST 中的 Python int 转为字符串（字节码编译器需要）。"""
    if isinstance(node, int):
        return str(node)
    if isinstance(node, list):
        return [ast_ints_to_str(x) for x in node]
    return node


def compile_llvmgen():
    with open('stdlib/llvmgen.san', 'r', encoding='utf-8') as f:
        src = f.read()

    ast, errors = parse_code(src)

    # 修复 export 节点
    fixed_stmts = []
    for stmt in ast[1:]:
        if isinstance(stmt, list) and len(stmt) > 0 and stmt[0] == 'export':
            names = [n for n in stmt[1:] if n != '导出']
            for name in names:
                fixed_stmts.append(['export', name])
        else:
            fixed_stmts.append(stmt)

    # V5: 无需注入，辅助函数已内联到源码
    full_ast = ast_ints_to_str(['do'] + fixed_stmts)

    print('llvmgen.san V5 自举编译（无注入）')
    print(f'语句数: {len(fixed_stmts)}')

    clear_cache()
    e = SanyanEvaluator(max_loop_steps=500000)
    compiler = e.eval(['import', 'stdlib/bytecode_compiler.san'])
    result = compiler.call(e, ['编译字节码', full_ast, 'stdlib/llvmgen.bin', {}])
    ok, cs, vc = result
    size = os.path.getsize('stdlib/llvmgen.bin')
    print(f'llvmgen.bin: {size} 字节, cs={cs}, vc={vc}')
    return ok


if __name__ == '__main__':
    compile_llvmgen()
