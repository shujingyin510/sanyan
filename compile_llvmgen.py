"""编译 llvmgen.san → llvmgen.bin

注入必要的辅助函数（替代 Python 注册的命令），
然后用字节码编译器编译为 .bin。
"""

import sys, os

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


# ── 辅助函数定义 ──────────────────────────────────────────────

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
    # 查找 (s, sub) → index or -1
    make_fn(
        '查找',
        ['s', 'sub'],
        [
            ['set', 'slen', ['取长', 's']],
            ['set', 'sublen', ['取长', 'sub']],
            ['set', 'i', 0],
            [
                'loop',
                ['小于', 'i', ['加', ['减', 'slen', 'sublen'], 1]],
                [
                    'do',
                    ['if', ['等于', ['子串', 's', 'i', 'sublen'], 'sub'], ['return', 'i']],
                    ['set', 'i', ['加', 'i', 1]],
                ],
            ],
            ['return', -1],
        ],
    ),
    # 前缀 (s, prefix) → 真/假
    make_fn(
        '前缀',
        ['s', 'prefix'],
        [
            ['return', ['等于', ['子串', 's', 0, ['取长', 'prefix']], 'prefix']],
        ],
    ),
    # 包含 (lst, item) → 真/假
    make_fn(
        '包含',
        ['lst', 'item'],
        [
            ['set', 'i', 0],
            ['set', 'llen', ['表长', 'lst']],
            [
                'loop',
                ['小于', 'i', 'llen'],
                ['do', ['if', ['等于', ['取', 'lst', 'i'], 'item'], ['return', 1]], ['set', 'i', ['加', 'i', 1]]],
            ],
            ['return', -1],
        ],
    ),
    # 字符串包含 (s, sub) → 真/假
    make_fn(
        '字符串包含',
        ['s', 'sub'],
        [
            ['return', ['大于等于', ['查找', 's', 'sub'], 0]],
        ],
    ),
    # 查键 (d, key, fallback) → value or fallback
    make_fn(
        '查键',
        ['d', 'key', 'fallback'],
        [
            ['if', ['含键', 'd', 'key'], ['return', ['取键', 'd', 'key']]],
            ['return', 'fallback'],
        ],
    ),
    # 存变量 (d, key, value) — 设置字典键
    make_fn(
        '存变量',
        ['d', 'key', 'value'],
        [
            ['置键', 'd', 'key', 'value'],
            ['return', 0],
        ],
    ),
    # 取字长 (s) → UTF-8 字节长度（近似：用字符长度 * 平均字节）
    make_fn(
        '取字长',
        ['s'],
        [
            ['return', ['取长', 's']],
        ],
    ),
    # 列表取 (lst, idx) → safe get
    make_fn(
        '列表取',
        ['lst', 'idx'],
        [
            ['if', ['小于', 'idx', ['表长', 'lst']], ['return', ['取', 'lst', 'idx']]],
            ['return', '""'],
        ],
    ),
    # 列表取长 (lst) → length
    make_fn(
        '列表取长',
        ['lst'],
        [
            ['return', ['表长', 'lst']],
        ],
    ),
    # 列表追加 (lst, item) → lst with item appended
    make_fn(
        '列表追加',
        ['lst', 'item'],
        [
            ['return', ['列表合', 'lst', ['列表', 'item']]],
        ],
    ),
    # 字典取长 (d) → key count
    make_fn(
        '字典取长',
        ['d'],
        [
            ['return', ['表长', ['字列', 'd']]],
        ],
    ),
    # 字典键列表 (d) → key list
    make_fn(
        '字典键列表',
        ['d'],
        [
            ['return', ['字列', 'd']],
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
    # 转义LLVM字符串 (s) → escaped string（简化版）
    make_fn(
        '转义LLVM字符串',
        ['s'],
        [
            ['return', 's'],
        ],
    ),
    # 是终止指令 (line) → 真/假
    make_fn(
        '是终止指令',
        ['line'],
        [
            ['set', 'trimmed', 'line'],  # 近似 trim
            ['if', ['字符串包含', 'trimmed', '"ret "'], ['return', 1]],
            ['if', ['字符串包含', 'trimmed', '"br "'], ['return', 1]],
            ['if', ['字符串包含', 'trimmed', '"unreachable"'], ['return', 1]],
            ['return', -1],
        ],
    ),
    # 不以终止指令结尾 (text) → 真/假（简化版：总是返回真）
    make_fn(
        '不以终止指令结尾',
        ['text'],
        [
            ['return', 1],
        ],
    ),
    # 最后一行 (text) → last non-empty line（简化版）
    make_fn(
        '最后一行',
        ['text'],
        [
            ['return', 'text'],
        ],
    ),
    # 是否为数字字符串 (s) → 真/假（简化版：检查首字符）
    make_fn(
        '是否为数字字符串',
        ['s'],
        [
            ['if', ['等于', ['取长', 's'], 0], ['return', -1]],
            ['set', 'c', ['字符码', ['子串', 's', 0, 1]]],
            ['if', ['小于', 'c', 48], ['return', -1]],
            ['if', ['大于', 'c', 57], ['return', -1]],
            ['return', 1],
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
