"""三言源码格式化器 — 类似 black/prettier"""

from __future__ import annotations
import sys

_INTERNAL_TO_DISPLAY = {
    'if': '若',
    'else': '否则',
    'elif': '再若',
    'for': '遍历',
    'loop': '循环',
    'forin': '遍历',
    'fn': '定义',
    'set': '设',
    'print': '输出',
    'return': '返回',
    'break': '跳出',
    'continue': '继续',
    'try': '尝试',
    'catch': '捕获',
    'do': '做',
    'query': '查',
    'context': '对',
    'judge': '判',
    'add': '加',
    'sub': '减',
    'mul': '乘',
    'div': '除',
    'mod': '余',
    'pow': '幂',
    'eq': '等于',
    'neq': '不等于',
    'gt': '大于',
    'gte': '大于等于',
    'lt': '小于',
    'lte': '小于等于',
    'ngt': '不大于',
    'nlt': '不小于',
    'and': '且',
    'or': '或',
    'not': '非',
}

_BINARY_OPS = {
    'add',
    'sub',
    'mul',
    'div',
    'mod',
    'pow',
    'eq',
    'neq',
    'gt',
    'gte',
    'lt',
    'lte',
    'ngt',
    'nlt',
    'and',
    'or',
    '同',
}

# 非二元操作但需要显示中文的
_EXTRA_DISPLAY = {
    'random': '随机数',
    'random_state': '随机态',
    'concat': '连接',
    'length': '取长',
    'substring': '子串',
    'replace': '替换',
    'split': '分割',
    'find': '查找',
    'trim': '去空白',
    'upper': '大写',
    'lower': '小写',
    'starts': '前缀',
    'ends': '后缀',
    'sort': '排序',
    'reverse': '反转',
    'contains': '包含',
    'unique': '去重',
    'slice': '切片',
    'sum': '求和',
    'merge': '合并',
    'list': '列表',
    'get': '取',
    'set_elem': '置元素',
    'list_join': '列表合',
    'list_len': '表长',
    'array': '数组',
    'arr_len': '组长',
    'dict': '字典',
    'get_key': '取键',
    'set_key': '置键',
    'has_key': '含键',
    'count': '计数',
    'map': '映射',
    'filter': '过滤',
    'reduce': '归并',
    'apply': '应用',
    'abs': '绝对值',
    'max': '最大值',
    'min': '最小值',
    'sqrt': '平方根',
    'sin': '正弦',
    'cos': '余弦',
    'tan': '正切',
    'log': '对数',
    'log10': '常用对数',
    'floor': '向下取整',
    'ceil': '向上取整',
    'round': '四舍五入',
    'ternary': '三进制',
    'time': '当前时间',
    'sleep': '等待',
    'wait': '等待',
    'read_file': '读文件',
    'write_file': '写文件',
    'is_number': '是数字',
    'is_string': '是字符串',
    'str_equals': '字符串相等',
    'to_json': '转JSON',
    'from_json': '解析JSON',
    'read': '读取',
    'write': '写入',
    'register_device': '注册设备',
    'import': '导入',
    'export': '导出',
    'load': '加载',
    'input': '输入',
    'debug': '调试',
    'install': '安装',
    'list_packages': '包列表',
    'load_package': '加载包',
    'ter': '三进制',
}

_PRECEDENCE = {
    'pow': 40,
    'mul': 30,
    'div': 30,
    'mod': 30,
    'add': 20,
    'sub': 20,
    'eq': 10,
    'neq': 10,
    'gt': 10,
    'gte': 10,
    'lt': 10,
    'lte': 10,
    'ngt': 10,
    'nlt': 10,
    'and': 5,
    'or': 5,
}


def _kw(name):
    return _INTERNAL_TO_DISPLAY.get(name) or _EXTRA_DISPLAY.get(name, name)


def _needs_parens(node, parent_prec, is_right=False):
    if not isinstance(node, list) or not node:
        return False
    prec = _PRECEDENCE.get(node[0], 0)
    if prec == 0:
        return False
    if is_right:
        return prec <= parent_prec
    return prec < parent_prec


def _fmt_expr(node, parent_prec=0, is_right=False):
    if isinstance(node, str):
        return node
    if isinstance(node, (int, float)):
        return str(node)
    if isinstance(node, list):
        if not node:
            return '[]'
        head = node[0]
        if head in _BINARY_OPS:
            prec = _PRECEDENCE.get(head, 0)
            left = _fmt_expr(node[1], prec)
            right = _fmt_expr(node[2], prec, True)
            result = f'{left} {_kw(head)} {right}'
            if parent_prec > 0 and _needs_parens(node, parent_prec, is_right):
                result = f'({result})'
            return result
        if head == 'not':
            inner = _fmt_expr(node[1], 0)
            result = f'非({inner})'
            if parent_prec > 0:
                result = f'({result})'
            return result
        name = _kw(head)
        args = ', '.join(_fmt_expr(a, 0) for a in node[1:])
        return f'{name}({args})'
    return str(node)


def _fmt_body(node, indent):
    if isinstance(node, list):
        if node and node[0] == 'do':
            if len(node) == 1:
                return ''
            return '\n'.join(_fmt_stmt(s, indent) for s in node[1:])
    return _fmt_stmt(node, indent)


def _fmt_if(node, indent):
    indent_str = '    ' * indent
    parts = []
    cur = node
    first = True
    while isinstance(cur, list) and cur[0] == 'if':
        cond = _fmt_expr(cur[1], 0)
        body = _fmt_body(cur[2], indent + 1)
        if first:
            parts.append(f'若 ({cond}) {{\n{body}\n{indent_str}}}')
            first = False
        else:
            parts.append(f' 再若 ({cond}) {{\n{body}\n{indent_str}}}')
        if len(cur) > 3 and cur[3] is not None:
            nxt = cur[3]
            if isinstance(nxt, list) and nxt[0] == 'if':
                cur = nxt
                continue
            else_body = _fmt_body(nxt, indent + 1)
            parts.append(f' 否则 {{\n{else_body}\n{indent_str}}}')
            break
        else:
            break
    return indent_str + ''.join(parts)


def _fmt_stmt(node, indent=0):
    indent_str = '    ' * indent
    if isinstance(node, str):
        return indent_str + node
    if isinstance(node, (int, float)):
        return indent_str + str(node)
    if isinstance(node, list):
        if not node:
            return indent_str + '[]'
        head = node[0]
        if head == 'do':
            if len(node) == 1:
                return indent_str + '{}'
            return '\n'.join(_fmt_stmt(s, indent) for s in node[1:])
        if head == 'if':
            return _fmt_if(node, indent)
        if head in ('for', 'forin'):
            if head == 'for':
                var = node[1]
                start = _fmt_expr(node[2], 0)
                end = _fmt_expr(node[3], 0)
                body = _fmt_body(node[4], indent + 1)
                return f'{indent_str}遍历 {var} 从 {start} 到 {end} {{\n{body}\n{indent_str}}}'
            var = node[1]
            container = _fmt_expr(node[2], 0)
            body = _fmt_body(node[3], indent + 1)
            return f'{indent_str}遍历 {var} 在 {container} {{\n{body}\n{indent_str}}}'
        if head == 'loop':
            cond = _fmt_expr(node[1], 0)
            body = _fmt_body(node[2], indent + 1) if len(node) > 2 else ''
            return f'{indent_str}循环 ({cond}) {{\n{body}\n{indent_str}}}'
        if head == 'fn':
            name = node[1]
            params = []
            param_strs = []
            idx = 4 if (len(node) > 3 and isinstance(node[3], dict)) else 3
            param_types = node[3] if idx == 4 else {}
            params = node[2]
            for p in params:
                if p in param_types:
                    param_strs.append(f'{p}: {param_types[p]}')
                else:
                    param_strs.append(p)
            body = ''
            if idx < len(node):
                body = _fmt_body(node[idx], indent + 1)
            return f'{indent_str}定义 {name}({", ".join(param_strs)}) {{\n{body}\n{indent_str}}}'
        if head == 'set':
            var = node[1]
            val = _fmt_expr(node[2], 0) if len(node) > 2 else ''
            if val.startswith('"') or val.startswith('\u201c') or (val and val[0].isalnum()):
                return f'{indent_str}设 {var} = {val}'
            return f'{indent_str}设 {var} = {val}'
        if head == 'return':
            if len(node) > 1:
                return f'{indent_str}返回({_fmt_expr(node[1], 0)})'
            return f'{indent_str}返回()'
        if head == 'break':
            return f'{indent_str}跳出'
        if head == 'continue':
            return f'{indent_str}继续'
        if head == 'print':
            return f'{indent_str}输出({_fmt_expr(node[1], 0)})'
        if head == 'query':
            return f'{indent_str}查({_fmt_expr(node[1], 0)})'
        if head == 'try':
            try_body = _fmt_body(node[1], indent + 1) if len(node) > 1 else ''
            var = node[2] if (len(node) > 2 and isinstance(node[2], str) and node[2] not in ('do',)) else None
            catch_idx = 3 if var else 2
            if var:
                catch_body = _fmt_body(node[catch_idx], indent + 1) if len(node) > catch_idx else ''
                return f'{indent_str}尝试 {{\n{try_body}\n{indent_str}}} 捕获 ({var}) {{\n{catch_body}\n{indent_str}}}'
            catch_body = _fmt_body(node[2], indent + 1) if len(node) > 2 else ''
            return f'{indent_str}尝试 {{\n{try_body}\n{indent_str}}} 捕获 {{\n{catch_body}\n{indent_str}}}'
        if head == 'judge':
            val = _fmt_expr(node[1], 0)
            branches = node[2] if len(node) > 2 else {}
            result = f'{indent_str}判 {val} {{\n'
            for k, display in [('true', '真'), ('maybe', '可能'), ('false', '假')]:
                if k in branches:
                    b = _fmt_body(branches[k], indent + 2)
                    result += f'{indent_str}    {display} {{\n{b}\n{indent_str}    }}\n'
            result += f'{indent_str}}}'
            return result
        # Fallback: function call
        name = _kw(head)
        args = ', '.join(_fmt_expr(a, 0) for a in node[1:])
        return f'{indent_str}{name}({args})'
    return indent_str + str(node)


def _reinsert_inline_comments(formatted: str, source: str) -> str:
    """从原始源码中重新插入注释（包括行内和纯注释行）。"""
    inline_map: dict[str, list[str]] = {}
    standalone: list[str] = []
    for src_line in source.split('\n'):
        # 跳过 #include 预处理行
        stripped = src_line.strip()
        if stripped.startswith('#include'):
            continue
        for marker in ('//', '／／'):
            idx = stripped.find(marker)
            if idx >= 0:
                comment = stripped[idx:]
                code_part = stripped[:idx].rstrip()
                if code_part:
                    norm = code_part.replace(' ', '').replace('\t', '')
                    inline_map.setdefault(norm, []).append(comment)
                else:
                    standalone.append(comment)
                break
    if not inline_map and not standalone:
        return formatted
    ambiguous = {k for k, v in inline_map.items() if len(v) > 1}
    lines = formatted.split('\n')
    for i, fmt_line in enumerate(lines):
        norm = fmt_line.replace(' ', '').replace('\t', '')
        if norm in inline_map and norm not in ambiguous:
            lines[i] = fmt_line.rstrip() + '  ' + inline_map[norm][0]
    if standalone:
        lines = standalone + lines
    return '\n'.join(lines)


def format_code(ast, source=None):
    """将 AST 格式化为漂亮的源码。

    Args:
        ast: 解析后的 AST
        source: 原始源码（用于恢复行内注释）
    """
    result = _fmt_stmt(ast, 0) + '\n'
    if source:
        result = _reinsert_inline_comments(result, source)
    return result


def format_file(filepath: str, in_place: bool = False) -> str:
    """格式化 .san 文件。"""
    from preprocess import preprocess_includes
    from skin import SkinManager
    from sugar import SugarConverter
    from lexer import tokenize
    from parser import parse

    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    original = code
    code = preprocess_includes(code)

    skin_mgr = SkinManager('chinese')
    ast = None
    try:
        ast = SugarConverter.convert(code, skin_mgr)
    except SyntaxError:
        pass

    if ast is None:
        tokens = tokenize(code)
        if tokens:
            ast = parse(tokens)
    if ast is None:
        raise ValueError('无法解析文件')

    formatted = format_code(ast, source=original)
    if in_place:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(formatted)
    return formatted


def main():
    import argparse

    parser = argparse.ArgumentParser(description='三言源码格式化器')
    parser.add_argument('file', nargs='?', help='.san 文件路径')
    parser.add_argument('-i', '--in-place', action='store_true', help='直接修改文件')
    parser.add_argument('--check', action='store_true', help='只检查格式（不修改），不合法时退出码 1')
    parser.add_argument('--ast-json', action='store_true', help='同时输出 AST JSON')
    args = parser.parse_args()

    if not args.file:
        # REPL 模式：从 stdin 读取
        code = sys.stdin.read()
        from sugar import SugarConverter
        from skin import SkinManager
        from lexer import tokenize
        from parser import parse

        skin_mgr = SkinManager('chinese')
        ast = None
        try:
            ast = SugarConverter.convert(code, skin_mgr)
        except SyntaxError:
            pass
        if ast is None:
            tokens = tokenize(code)
            if tokens:
            ast = parse(tokens)  # type: ignore[assignment]
        if ast is None:
            print('解析失败', file=sys.stderr)
            sys.exit(1)
        print(format_code(ast, source=code))
        return

    formatted = format_file(args.file, in_place=args.in_place)
    if args.check:
        with open(args.file, 'r', encoding='utf-8') as f:
            original = f.read()
        if original != formatted:
            print(f'{args.file}: 格式不正确')
            sys.exit(1)
        print(f'{args.file}: 格式正确')
    elif not args.in_place:
        print(formatted)


if __name__ == '__main__':
    main()
