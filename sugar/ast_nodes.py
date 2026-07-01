"""AST 辅助模块：关键字/运算符映射、优先级表、标识符检测、AST 位置注解。

本模块包含语法分析器使用的常量定义和工具函数：
- KEYWORD_MAP / OP_MAP：从语言皮肤文件构建的关键字与运算符映射
- PREC / RIGHT_ASSOC / PREFIXABLE_OPS：Pratt 优先级与结合性配置
- _is_ident：标识符合法性检测
- annotate_ast：为 AST 节点挂载源码位置信息
"""

from __future__ import annotations
import json
import os
from values import SrcNode


def _build_keyword_map() -> dict[str, str]:
    """从皮肤文件构建关键字映射（仅构建一次）。"""
    maps: dict[str, str] = {}
    for lang_file in ['chinese.json', 'english.json']:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'language', lang_file)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for internal, keyword in data.get('keywords', {}).items():
                if isinstance(keyword, list):
                    for kw in keyword:
                        maps[kw] = internal
                else:
                    maps[keyword] = internal
        except (OSError, json.JSONDecodeError):
            pass
    # 关键字自映射（支持直接使用英文内部名）
    for internal in [
        'set',
        'if',
        'elif',
        'else',
        'loop',
        'for',
        'fn',
        'return',
        'break',
        'continue',
        'try',
        'catch',
        'judge',
        'lambda',
        'in',
        'import',
        'print',
        'load',
        'count',
        'context',
        'write',
        'read',
        'query',
        'export',
        'install',
        'list_packages',
        'load_package',
        'register_device',
    ]:
        maps[internal] = internal
    return maps


def _build_op_map() -> dict[str, str]:
    """从皮肤文件构建运算符映射。"""
    maps: dict[str, str] = {}
    # 符号 → 内部名（皮肤文件只映射内部名→中文，需补全符号反向映射）
    maps['+'] = 'add'
    maps['-'] = 'sub'
    maps['*'] = 'mul'
    maps['/'] = 'div'
    maps['%'] = 'mod'
    maps['^'] = 'pow'
    maps['>'] = 'gt'
    maps['<'] = 'lt'
    maps['>='] = 'gte'
    maps['<='] = 'lte'
    maps['='] = 'eq'
    maps['!='] = 'ne'
    for lang_file in ['chinese.json', 'english.json']:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'language', lang_file)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for internal, op in data.get('operators', {}).items():
                if isinstance(op, list):
                    for o in op:
                        maps[o] = internal
                else:
                    maps[op] = internal
        except (OSError, json.JSONDecodeError):
            pass
    return maps


KEYWORD_MAP = _build_keyword_map()
OP_MAP = _build_op_map()

# Pratt 优先级表：数值越大绑定越紧
# or/and(1) < 比较(2) < 加减(3) < 乘除(4) < 幂(5)
PREC = {
    'and': 1,
    'or': 1,
    'eq': 2,
    'ne': 2,
    'gt': 2,
    'lt': 2,
    'gte': 2,
    'lte': 2,
    'ngt': 2,
    'nlt': 2,
    'add': 3,
    'sub': 3,
    'mul': 4,
    'div': 4,
    'mod': 4,
    'pow': 5,
}
RIGHT_ASSOC = {'pow'}

# 可前缀的操作符（无关键字包装，直接出现在表达式开头）
PREFIXABLE_OPS = {
    'add',
    'sub',
    'mul',
    'div',
    'mod',
    'pow',
    'gt',
    'lt',
    'eq',
    'ne',
    'gte',
    'lte',
    'ngt',
    'nlt',
    'not',
    'and',
    'or',
    'digit',
    'read',
    'import',
    'load',
    'print',
    'query',
    'match',
}
# 单参数前缀操作符（不需要括号包裹参数）
PREFIXABLE_SINGLE_ARG = {'read', 'not', 'digit', 'import', 'load', 'print', 'query'}


def _is_ident(tok: str) -> bool:
    if not tok:
        return False
    if tok[0].isdigit():
        return False
    for c in tok:
        if not (c.isalnum() or c == '_' or c == '.' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf'):
            return False
    return True


def annotate_ast(ast, tokens):
    """后处理：为 AST 列表节点挂载 SrcNode（行/列位置）。

    遍历 AST，对每个列表节点找到其第一个字符串元素，
    在 token 序列中查找匹配位置。使求值器错误信息可溯源到源码位置。
    """
    if not tokens:
        return ast

    # Build quick lookup: first occurrence of each string value
    first_pos = {}
    for tok in tokens:
        if tok.kind != 'COMMENT' and tok.value not in first_pos:
            first_pos[tok.value] = (tok.line, tok.col)

    def _walk(node):
        if isinstance(node, list) and not isinstance(node, SrcNode):
            line, col = 0, 0
            if node and isinstance(node[0], str) and node[0] in first_pos:
                line, col = first_pos[node[0]]
            wrapped = SrcNode(node, line=line, col=col)
            for i, child in enumerate(wrapped):
                wrapped[i] = _walk(child)
            return wrapped
        if isinstance(node, list):
            for i, child in enumerate(node):
                node[i] = _walk(child)
        return node

    return _walk(ast)
