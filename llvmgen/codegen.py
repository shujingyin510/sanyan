"""三言 AST → LLVM IR 代码生成器。

本模块是代码生成的公开 API 入口，提供顶层编译函数：
- compile_top_level: 编译 AST 节点列表到 LLVM IR
- compile_program: 编译完整源码，含 import 静态链接
- compile_node: 从 ops_gen 重新导出，保持向后兼容

子模块：
- type_mapping: 类型定义、常量、运行时函数规范
- ir_builder: CodegenContext（模块、构建器、符号表）
- ops_gen: 各 AST 节点的 LLVM IR 编译
"""

from __future__ import annotations

from llvmlite import ir

from llvmgen.ir_builder import CodegenContext
from llvmgen.ops_gen import compile_node
from llvmgen.type_mapping import (
    _INT,
    _NULL,
    _PTR,
    BoxedValue,
    RawValue,
    _is_string_literal,
    _to_int,
    _unquote,
)

# ── AST 预处理 / 归一化 ──


def _merge_if_chain(nodes: list) -> list:
    """规范化：将 再若(elif)/否则(else) 合并到前一个 若 节点中。

    糖解析器输出的 AST 中，再若 和 否则 作为做块中的独立元素存在。
    本函数将它们合并为统一的 若 节点结构。
    """
    result = []
    i = 0
    while i < len(nodes):
        node = nodes[i]
        if isinstance(node, list) and len(node) > 0 and node[0] == '若':
            # 收集后续的 再若 和 否则
            merged = list(node)
            i += 1
            while i < len(nodes):
                nxt = nodes[i]
                if isinstance(nxt, list) and len(nxt) > 0 and nxt[0] == '再若':
                    merged.append(nxt)  # 再若条件 [再若 cond]
                    i += 1
                    if i < len(nodes):
                        nxt_body = nodes[i]
                        if isinstance(nxt_body, list) and len(nxt_body) > 0 and nxt_body[0] in ('做', 'do'):
                            merged.append(nxt_body)  # 再若体
                            i += 1
                elif isinstance(nxt, str) and nxt == '否则':
                    merged.append('否则')
                    i += 1
                    if i < len(nodes):
                        else_body = nodes[i]
                        merged.append(else_body)
                        i += 1
                else:
                    break
            # 递归处理合并后节点内部的 做 块
            merged = _deep_merge(merged)
            result.append(merged)
        elif isinstance(node, list) and len(node) > 0:
            # 递归处理所有列表节点
            result.append(_deep_merge(list(node)))
            i += 1
        else:
            result.append(node)
            i += 1
    return result


def _normalize_fn_format(nodes: list) -> list:
    """将 SugarConverter 的 ['fn', 'name', ['p'], body] 转为标准 ['fn', ['name', 'p'], body]。"""
    result = []
    for node in nodes:
        if isinstance(node, list) and len(node) >= 3 and node[0] == 'fn':
            if isinstance(node[1], str) and isinstance(node[2], list):
                name = node[1]
                params = node[2]
                body = node[3] if len(node) > 3 else []
                result.append(['fn', [name] + params, body])
                continue
        result.append(node)
    return result


def _deep_merge(node):
    """递归对 AST 节点及其所有子节点进行 if-elif-else 合并，并过滤 IoT 关键字。"""
    if isinstance(node, list) and len(node) > 0:
        first = node[0]
        if first in ('做', 'do'):
            # 过滤 IoT 关键字，然后合并
            inner = node[1:]
            inner = _merge_if_chain(inner)
            return [first] + inner
        # 其他节点递归处理子节点
        return [node[0]] + [_deep_merge(c) for c in node[1:]]
    return node


def _resolve_imports(nodes: list, cg: CodegenContext) -> tuple[list, list]:
    """解析 设 var = 导入(\"path\")，编译被导入文件的 定义 到当前模块。
    返回 (处理后的节点列表, 导入的顶层设节点列表)。
    """
    import os

    result = []
    imported_setups = []  # 导入文件中的 设 节点
    for node in nodes:
        if (
            isinstance(node, list)
            and len(node) >= 3
            and node[0] in ('设', 'set')
            and isinstance(node[2], list)
            and node[2][0] in ('导入', 'import')
            and len(node[2]) >= 2
        ):
            path_node = node[2][1]
            if isinstance(path_node, str) and _is_string_literal(path_node):
                path_node = _unquote(path_node)
            path_str = str(path_node)
            search = [path_str, f'stdlib/{path_str}', f'stdlib/{path_str}.san']
            found = None
            for sp in search:
                if os.path.exists(sp):
                    found = sp
                    break
                if not sp.endswith('.san') and os.path.exists(sp + '.san'):
                    found = sp + '.san'
                    break
            if found:
                try:
                    with open(found, 'r', encoding='utf-8') as f:
                        imported_code = f.read()
                    from ops.file_ops import _parse_with_sugar_san
                    from evaluator import SanyanEvaluator

                    tmp_eval = SanyanEvaluator()
                    imported_ast = _parse_with_sugar_san(imported_code, tmp_eval)
                    if imported_ast is None:
                        from sugar import SugarConverter
                        from skin import SkinManager

                        imported_ast = SugarConverter.convert(imported_code, SkinManager('chinese'))
                    if isinstance(imported_ast, list) and len(imported_ast) > 0 and imported_ast[0] in ('做', 'do'):
                        imported_ast = imported_ast[1:]
                    if isinstance(imported_ast, list):
                        # 先处理 设，再处理 定义（确保 定义 内可用全局变量）
                        for inode in imported_ast:
                            if isinstance(inode, list) and len(inode) > 0 and inode[0] in ('设', 'set'):
                                imported_setups.append(inode)
                        for inode in imported_ast:
                            if isinstance(inode, list) and len(inode) > 0 and inode[0] in ('定义', 'define', 'fn'):
                                try:
                                    compile_node(inode, cg)
                                except Exception as _exc:
                                    import sys as _sys2

                                    _name = inode[1] if len(inode) > 1 else '?'
                                    print(f'[import] skip {_name}: {_exc}', file=_sys2.stderr)
                except Exception as _exc2:
                    import sys as _sys3

                    print(f'[import] failed: {_exc2}', file=_sys3.stderr)
            continue
        result.append(node)
    return result, imported_setups


def _make_bootstrap_harness(cg: CodegenContext):
    """为 bootstrap 模块添加 parse_sanyan() ASCII 入口。"""
    cg.begin_function('parse_sanyan', ['source'])
    # 全局变量初始化
    for gname, gval in cg._global_inits:
        if isinstance(gval, (int, float)):
            init_val = cg._box_int(ir.Constant(_INT, int(gval)))
        elif isinstance(gval, str):
            init_val = cg._make_rt_string(gval)
        else:
            # 复杂初始化表达式 → 编译
            if isinstance(gval, list):
                init_val = compile_node(gval, cg)
            else:
                init_val = _NULL
        if init_val is not None:
            cg.builder.store(init_val, cg._globals[gname])
    # 调用 解析(source)
    func = cg._funcs.get('解析')
    if func:
        src = cg.get_var('source')
        result = cg.builder.call(func, [src], name='ast')
        cg.builder.ret(result)
    else:
        cg.builder.ret(_NULL)
    cg.end_function()


# ── 顶层编译入口 ──


def compile_top_level(ast_nodes: list, module_name: str = 'main', module_prefix: str = '') -> CodegenContext:
    cg = CodegenContext(module_name, module_prefix=module_prefix)
    _compile_in_context(ast_nodes, cg)
    return cg


def _compile_in_context(ast_nodes: list, cg: CodegenContext) -> None:
    # 确保顶层是 do 块
    if isinstance(ast_nodes, list) and len(ast_nodes) > 0:
        first = ast_nodes[0]
        if isinstance(first, str) and first not in ('做', 'do'):
            # 单表达式: wrap 为 ['做', node] 防扁平化
            ast_nodes = ['做', ast_nodes]
        elif first not in ('做', 'do'):
            ast_nodes = ['做'] + ast_nodes
    if isinstance(ast_nodes, list) and len(ast_nodes) > 0 and ast_nodes[0] in ('做', 'do'):
        ast_nodes = ast_nodes[1:]

    ast_nodes = _normalize_fn_format(ast_nodes)
    ast_nodes = _merge_if_chain(ast_nodes)

    def collect_and_compile(nodes):
        nodes, imported_setups = _resolve_imports(nodes, cg)
        defs, others = [], []
        for node in nodes:
            if isinstance(node, list) and len(node) > 0 and node[0] in ('定义', 'define', 'fn'):
                defs.append(node)
            else:
                others.append(node)

        for node in others + imported_setups:
            if isinstance(node, list) and len(node) >= 3 and node[0] in ('设', 'set'):
                name = node[1]
                if isinstance(name, str):
                    val = node[2]
                    if isinstance(val, (int, float)):
                        if name.startswith('_'):
                            cg.create_global(name, val)
                        # 数字 — 不预建全局（走 alloca）
                    elif isinstance(val, str):
                        if _is_string_literal(val):
                            pass
                        elif _to_int(val) is not None:
                            if name.startswith('_'):
                                cg.create_global(name, val)
                            # 数字字符串 — 不预建全局
                        else:
                            cg.create_global(name, val)
                            cg._global_inits.append((name, val))
                    else:
                        cg.create_global(name, val)
                        cg._global_inits.append((name, val))

        class _Df:
            def __init__(self, n):
                self.node = n

        deferred: list[_Df] = []
        for node in defs:
            deferred.append(_Df(node))
            if isinstance(node[1], list):
                n, p = node[1][0], node[1][1:]
            elif node[0] == 'fn' and len(node) >= 3:
                n, p = node[1], node[2] if isinstance(node[2], list) else []
            else:
                n = node[1] if isinstance(node[1], str) else str(node[1])
                p = node[2] if len(node) > 2 and isinstance(node[2], list) else []
            cg.begin_function(n, p)
        for d in deferred:
            compile_node(d.node, cg)

        if cg.module.name == 'bootstrap' and '解析' in cg._funcs:
            _make_bootstrap_harness(cg)

        all_other = imported_setups + others
        if cg.module.name != 'bootstrap' and (all_other or cg._global_inits):
            cg.begin_function('main', [])
            for gname, gval in cg._global_inits:
                if isinstance(gval, (int, float)):
                    init_val = cg._box_int(ir.Constant(_INT, int(gval)))
                elif isinstance(gval, str):
                    init_val = cg._make_rt_string(gval)
                else:
                    init_val = _NULL
                cg.builder.store(init_val, cg._globals[gname])
            for node in all_other:
                if isinstance(node, list) and len(node) > 0 and node[0] in ('导入', 'import'):
                    continue
                compile_node(node, cg)
            cg.end_function()
        elif cg.module.name != 'bootstrap':
            cg.begin_function('main', [])
            cg.end_function()

    collect_and_compile(ast_nodes)


def _parse_source(source: str) -> list:
    from llvmgen.compiler import _parse_source as _ps

    return _ps(source)


def _collect_imports(node, collected: set) -> None:
    if isinstance(node, list) and len(node) > 0:
        if node[0] in ('导入', 'import') and len(node) > 1 and isinstance(node[1], str):
            collected.add(node[1])
            return
        for child in node:
            _collect_imports(child, collected)


def _find_module_path(name: str) -> str | None:
    import os

    if len(name) >= 2 and name[0] == '"' and name[-1] == '"':
        name = name[1:-1]

    paths = [name]
    if not name.endswith('.san'):
        paths.append(name + '.san')
    paths.append(os.path.join('stdlib', name if name.endswith('.san') else name + '.san'))

    for p in paths:
        if os.path.exists(p):
            return p
    return None


def compile_program(source: str, module_name: str = 'main') -> 'CodegenContext':
    """编译完整程序，含 import 静态链接。

    递归编译所有 导入 引用的 .san 模块，通过 llvmlite link_modules
    合并到一个 IR 模块中。依赖模块函数名加 san_{module}__ 前缀。
    """
    import os

    ast = _parse_source(source)
    if not isinstance(ast, list):
        raise SyntaxError(f'解析结果不是列表: {type(ast)}')

    imports: set[str] = set()
    _collect_imports(ast, imports)

    cg = compile_top_level(ast, module_name)

    if not imports:
        return cg

    from llvmlite import binding as llvm_bind

    main_mod = llvm_bind.parse_assembly(cg.verify())

    for imp in imports:
        path = _find_module_path(imp)
        if path is None:
            continue
        with open(path, 'r', encoding='utf-8') as f:
            dep_src = f.read()
        dep_ast = _parse_source(dep_src)
        dep_name = os.path.splitext(os.path.basename(path))[0]
        dep_cg = compile_top_level(dep_ast, dep_name, module_prefix=dep_name)
        dep_mod = llvm_bind.parse_assembly(dep_cg.verify())
        llvm_bind.link_modules(dst=main_mod, src=dep_mod)

    cg._linked_ir = str(main_mod)
    return cg
