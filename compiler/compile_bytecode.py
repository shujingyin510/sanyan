"""三言字节码编译器 — Python 包装

编译 .san → .bin，支持 sugar 语法和 S-表达式。
用法:
    python compile_bytecode.py input.san [-o output.bin] [--run]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.lexer import tokenize
from core.parser import parse_program
from core.evaluator import SanyanEvaluator
from sugar.parser import parse_code as sugar_parse
from ops.file_ops import clear_cache
from core.values import SanyanSyntaxError, SanyanRuntimeError

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


_FFI_OPS = ('py导入', 'py取', 'py调', 'py项', 'py列', 'py释', 'c载入', 'c调', 'c释')

# 网络算子：字节码/种子 VM 的 65-opcode ISA 无网络指令，运行时也无外呼通道。
# 含 ASCII 别名（registry 同名注册，绕过检测会落到深层未知算子错误——不许静默）。
_NET_OPS = (
    'http读',
    'http写',
    'http请求',
    '三态Web服务器',
    '三态路由',
    '三态监听',
    'http_get',
    'http_post',
    'http_request',
    'ternary_web_server',
    'ternary_web_route',
    'ternary_web_listen',
)


# 能力约束算子：约束栈是求值器实例运行时特性（挂 _cap_stack），字节码/种子 VM 无此运行时。
_CONSTRAINT_OPS = ('任务', '约束', '能否')


def _find_op(node, ops) -> str | None:
    """在 AST 里找算子位（列表头）上的指定操作名；找不到返回 None。"""
    if isinstance(node, list) and node:
        if isinstance(node[0], str) and node[0] in ops:
            return node[0]
        for child in node:
            hit = _find_op(child, ops)
            if hit:
                return hit
    return None


def compile_source(source: str, output_path: str, vars_table: dict | None = None) -> list:
    """编译源码字符串为 .bin 文件。返回 [成功, 代码大小, 变量数]。"""
    from core.preprocess import preprocess_includes

    if vars_table is None:
        vars_table = {}

    # 预处理 #include 指令
    source = preprocess_includes(source)

    # 将 __exports__ 从变量表中分离（避免被当作变量引用）
    export_names = vars_table.pop('__exports__', []) if isinstance(vars_table, dict) else []

    # 解析源码为 AST
    # 检测 S-表达式输入（以 ( 开头且括号平衡），直接用 S-表达式解析器
    ast: list | None = None
    sugar_ast: list | None = None
    is_sexpr = (source.strip().startswith('(') and source.count('(') == source.count(')')) or (
        source.strip().startswith('\uff08') and source.count('\uff08') == source.count('\uff09')
    )

    sugar_error = None
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
            elif has_syntax_err:
                # 保留 sugar 解析器的错误信息（带行号）
                sugar_error = errors[0] if errors else None
        except (SyntaxError, Exception) as exc:
            sugar_error = str(exc)

    # 2. 如果 sugar 解析失败或跳过，尝试 S-表达式解析器
    if not sugar_ast:
        try:
            # parse_program：取**全部**顶层形式（parse 只取第一个，会静默丢后续语句）
            tokens = tokenize(source)
            forms = parse_program(tokens, source)  # 传递源码用于错误位置定位
            if forms:
                first = forms[0]
                if len(forms) == 1 and isinstance(first, list) and len(first) > 0 and first[0] == '做':
                    # S-表达式用 (做 ...) 作为顶层包装
                    sugar_ast = ['do'] + first[1:]
                elif len(forms) == 1:
                    sugar_ast = ['do', first]
                else:
                    sugar_ast = ['do'] + forms
        except SanyanSyntaxError as exc2:
            sugar_error = str(exc2)
        except Exception:
            pass

    if not sugar_ast:
        if sugar_error:
            raise SanyanSyntaxError(sugar_error)
        raise SanyanSyntaxError('解析失败，请检查语法（支持 sugar 和 S-表达式两种语法）')

    ast = sugar_ast
    # FFI 后端矩阵（docs/ffi_plan.md §1）：Python 桥是**进程内**运行时能力，字节码 VM/
    # LLVM 后端没有这个运行时——编译期显式报错，绝不静默吞掉（只查算子位/表头，
    # 字符串数据里出现 "py导入" 不误伤）。repl 主流程捕获此错并回退求值器（带打印）。
    ffi_op = _find_op(ast, _FFI_OPS)
    if ffi_op:
        raise SanyanSyntaxError(
            f'{ffi_op} 仅解释器路径支持（--eval）——FFI 是进程内 Python 桥，'
            f'字节码/LLVM 后端无此运行时（docs/ffi_plan.md §1 后端矩阵）'
        )
    # 网络后端矩阵（同 FFI 惯例，绝不静默）：字节码/种子 VM 无网络运行时；
    # http读/http写 另有 LLVM 原生路径（WinHTTP）。repl 捕获此错回退求值器。
    net_op = _find_op(ast, _NET_OPS)
    if net_op:
        raise SanyanSyntaxError(
            f'{net_op} 仅解释器路径支持（--eval）——字节码/种子 VM 无网络运行时；'
            f'http读/http写 另可走 LLVM 原生路径（WinHTTP），见 docs/manual.md 网络算子小节'
        )
    # 能力约束后端矩阵（同上惯例）：约束栈是求值器实例运行时特性，字节码/种子 VM 无此运行时。
    cap_op = _find_op(ast, _CONSTRAINT_OPS)
    if cap_op:
        raise SanyanSyntaxError(
            f'{cap_op} 仅解释器路径支持（--eval）——能力约束栈是求值器运行时特性，'
            f'字节码/种子 VM 无此运行时（约束-方向研究 §D5 后端矩阵）'
        )
    # 自动提取 sugar AST 中的 (export ...) / (导出 ...) 节点
    if not export_names:
        fixed = []
        for s in ast[1:]:
            if isinstance(s, list) and s and s[0] == 'export':
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
    print(f'[OK] 编译 {source_path} → {output_path}: {size} 字节, {vars_count} 变量')

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
