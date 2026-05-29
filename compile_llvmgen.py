"""编译 llvmgen.san → llvmgen.bin

注入必要的辅助函数（计数器、状态管理、函数名映射），
然后用字节码编译器编译为 .bin。

薄包装辅助函数（查找/前缀/包含等）已移除——llvmgen.san 直接使用
内置操作（查找/前缀/包含/字符串包含/含键/置键/取长/取/表长/
列表合/字列/切片），无需额外注入。
死桩（转义LLVM字符串/不以终止指令结尾/最后一行/是否为数字字符串/是终止指令）
已移除——llvmgen.san 自身已定义完整实现。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sugar.parser import parse_code
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache


def make_fn(name, params, body_stmts):
    """构造 ['fn', name, params, body] AST 节点。"""
    if len(body_stmts) == 1:
        body = body_stmts[0]
    else:
        body = ['do'] + body_stmts
    return ['fn', name, params, body]


# ── 辅助函数定义（仅保留必需的计数器、状态管理、函数名映射）──

HELPERS = [
    # 计数器：新寄存器ID — 返回当前值并自增
    make_fn(
        '新寄存器ID',
        [],
        [
            ['set', '_reg_id', ['add', '_reg_id', 1]],
            ['return', '_reg_id'],
        ],
    ),
    # 计数器：新标签ID — 返回当前值并自增
    make_fn(
        '新标签ID',
        [],
        [
            ['set', '_label_id', ['add', '_label_id', 1]],
            ['return', '_label_id'],
        ],
    ),
    # 新寄存器 (reg) → [f"%{reg+1}", reg+1]
    make_fn(
        '新寄存器',
        ['reg'],
        [
            ['set', 'new_id', ['新寄存器ID']],
            ['return', ['列表', ['连接', '"%"', ['字符串', 'new_id']], 'new_id']],
        ],
    ),
    # 新标签 (prefix) → f"{prefix}{id}"
    make_fn(
        '新标签',
        ['prefix'],
        [
            ['set', 'lid', ['新标签ID']],
            ['return', ['连接', 'prefix', ['字符串', 'lid']]],
        ],
    ),
    # 循环进栈 (hdr) — 存储到全局变量
    make_fn(
        '循环进栈',
        ['hdr'],
        [
            ['set', '_loop_stack', ['列表合', '_loop_stack', ['列表', 'hdr']]],
            ['return', 0],
        ],
    ),
    # 循环出栈 () — 弹出
    make_fn(
        '循环出栈',
        [],
        [
            ['set', 'llen', ['表长', '_loop_stack']],
            ['if', ['大于', 'llen', 0], ['set', '_loop_stack', ['切片', '_loop_stack', 0, ['减', 'llen', 1]]]],
            ['return', 0],
        ],
    ),
    # 取合并标签 () → _merge_label
    make_fn(
        '取合并标签',
        [],
        [
            ['return', '_merge_label'],
        ],
    ),
    # 进入合并上下文 (label)
    make_fn(
        '进入合并上下文',
        ['label'],
        [
            ['set', '_merge_label', 'label'],
            ['return', 0],
        ],
    ),
    # 退出合并上下文 ()
    make_fn(
        '退出合并上下文',
        [],
        [
            ['set', '_merge_label', '""'],
            ['return', 0],
        ],
    ),
    # 注册函数名 (name) → ascii name
    make_fn(
        '注册函数名',
        ['name'],
        [
            ['set', '_fn_counter', ['add', '_fn_counter', 1]],
            ['set', 'aname', ['连接', '"_fn"', ['字符串', '_fn_counter']]],
            ['置键', '_fn_map', 'name', 'aname'],
            ['return', 'aname'],
        ],
    ),
    # 取函数名 (name) → mapped name or original
    make_fn(
        '取函数名',
        ['name'],
        [
            ['if', ['含键', '_fn_map', 'name'], ['return', ['取键', '_fn_map', 'name']]],
            ['return', 'name'],
        ],
    ),
]

# 全局变量初始化
GLOBAL_INITS = [
    ['set', '_reg_id', 0],
    ['set', '_label_id', 0],
    ['set', '_fn_counter', 0],
    ['set', '_fn_map', ['字典']],
    ['set', '_loop_stack', ['列表']],
    ['set', '_merge_label', '""'],
]


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

    # 注入：辅助函数（fn定义会跳过执行）+ 全局变量初始化 + 原始语句
    injected = HELPERS + GLOBAL_INITS + fixed_stmts
    full_ast = ast_ints_to_str(['do'] + injected)

    print(f'注入 {len(GLOBAL_INITS)} 个全局变量, {len(HELPERS)} 个辅助函数')
    print(f'原始语句: {len(fixed_stmts)}, 总语句: {len(injected)}')

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
