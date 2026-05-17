"""语法分析器：将 token 列表解析为 AST（嵌套列表）"""

from typing import Optional, Union


def parse(tokens: list) -> Optional[list]:
    if not tokens:
        return None

    left_count = tokens.count('(')
    right_count = tokens.count(')')
    if left_count != right_count:
        raise SyntaxError('括号不匹配')

    def _parse_inner(tokens_list: list) -> Optional[Union[list, str]]:
        if not tokens_list:
            return None
        token = tokens_list.pop(0)
        if token == '(':
            L = []
            while tokens_list and tokens_list[0] != ')':
                L.append(_parse_inner(tokens_list))
            if not tokens_list:
                raise SyntaxError("括号不匹配：缺少右括号 ')'")
            tokens_list.pop(0)
            return L
        elif token == ')':
            raise SyntaxError("多余的右括号 ')'")
        else:
            return token

    return _parse_inner(tokens)
