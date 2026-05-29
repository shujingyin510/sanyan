"""语法分析器：将 token 列表解析为 AST（嵌套列表）

支持错误恢复：
- 未闭合的 '('：EOF 时返回已解析的部分列表
- 多余的 ')'：跳过并继续解析
- 空表达式 '()'：返回 None
"""

from typing import Optional, Union


def parse(tokens: list) -> Optional[Union[list, str]]:
    if not tokens:
        return None

    def _parse_inner(tokens_list: list) -> Optional[Union[list, str]]:
        if not tokens_list:
            return None
        token: str = tokens_list.pop(0)
        if token == '(':
            L: list = []
            while tokens_list and tokens_list[0] != ')':
                child = _parse_inner(tokens_list)
                if child is not None:
                    L.append(child)
            if not tokens_list:
                return L if L else None
            tokens_list.pop(0)
            return L if L else None
        elif token == ')':
            return None
        else:
            return token

    return _parse_inner(tokens)
