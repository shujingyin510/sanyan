"""语法分析器：将 token 列表解析为 AST（嵌套列表）

基于递归下降解析，支持：
- 行号/列号追踪（通过原始源码回溯）
- 索引遍历（替代 O(n²) pop(0)）
- 明确的错误信息 + 位置定位
- 未闭合 '('、多余 ')' 的错误恢复
"""

from typing import Optional, Union

from values import SanyanSyntaxError


def _find_position(source: str, token_index: int, tokens: list) -> tuple[int, int]:
    """根据 token 索引在源码中查找位置。"""
    line = 1
    col = 1
    found = 0
    i = 0
    while i < len(source) and found <= token_index:
        c = source[i]
        if c == '\n':
            line += 1
            col = 1
            i += 1
            continue
        if c in (' ', '\t', '\r', '\u3000'):
            col += 1
            i += 1
            continue
        # 注释跳过
        if c == '/' and i + 1 < len(source) and source[i + 1] == '/':
            while i < len(source) and source[i] != '\n':
                i += 1
            continue
        if c == '\uff0f' and i + 1 < len(source) and source[i + 1] == '\uff0f':
            while i < len(source) and source[i] != '\n':
                i += 1
            continue
        # 字符串跳过
        if c in ('"', "'", '\u201c', '\u2018'):
            quote = c
            end_q = {'"': '"', "'": "'", '\u201c': '\u201d', '\u2018': '\u2019'}[quote]
            i += 1
            col += 1
            while i < len(source) and source[i] != end_q:
                if source[i] == '\\':
                    i += 1
                if source[i] == '\n':
                    line += 1
                    col = 1
                else:
                    col += 1
                i += 1
            if i < len(source):
                i += 1
                col += 1
            found += 1
            continue
        # 全角映射
        if c in ('（', '）', '；', '，', '：'):
            col += 1
            found += 1
            i += 1
            continue
        if c in ('(', ')'):
            col += 1
            found += 1
            i += 1
            continue
        # 普通 token
        token_start = i
        while i < len(source) and source[i] not in (
            ' ',
            '\n',
            '\t',
            '\r',
            '\u3000',
            '(',
            ')',
            '（',
            '）',
            '；',
            '，',
            '：',
            '"',
            "'",
            '\u201c',
            '\u2018',
        ):
            if source[i] == '/' and i + 1 < len(source) and source[i + 1] == '/':
                break
            if source[i] == '\uff0f' and i + 1 < len(source) and source[i + 1] == '\uff0f':
                break
            col += 1
            i += 1
        if found == token_index:
            return line, col - (i - token_start) if i > token_start else col
        found += 1
    return line, col


def parse(tokens: list, source: str = '') -> Optional[Union[list, str]]:
    """将 token 列表解析为 AST。可选 source 参数用于错误位置定位。"""
    if not tokens:
        return None

    pos = 0  # 当前 token 索引（替代 pop(0)）

    def _next() -> Optional[str]:
        nonlocal pos
        if pos >= len(tokens):
            return None
        tok = tokens[pos]
        pos += 1
        return tok

    def _peek() -> Optional[str]:
        if pos >= len(tokens):
            return None
        return tokens[pos]

    def _error(msg: str) -> str:
        """生成带位置的错误信息。"""
        if source:
            line, col = _find_position(source, max(0, pos - 1), tokens)
            return f'第{line}行第{col}列: {msg}'
        return msg

    def _parse_inner() -> Optional[Union[list, str]]:
        nonlocal pos
        token = _next()
        if token is None:
            return None
        if token == '(':
            L: list = []
            while _peek() is not None and _peek() != ')':
                child = _parse_inner()
                if child is not None:
                    L.append(child)
            if _peek() is None:
                raise SanyanSyntaxError(_error("未闭合的 '(' —— 缺少 ')'"))
            _next()  # 跳过 ')'
            return L if L else None
        elif token == ')':
            raise SanyanSyntaxError(_error("意外的 ')' —— 括号不匹配"))
        else:
            return token

    try:
        return _parse_inner()
    except SanyanSyntaxError:
        raise
    except Exception as e:
        raise SanyanSyntaxError(_error(f'解析错误: {e}')) from e
