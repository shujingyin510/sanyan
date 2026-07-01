"""糖语法转换器：类 C 语法 -> S-表达式 AST

拆分为 tokenizer + ast_nodes + parser + errors 模块。
"""

from __future__ import annotations
from sugar.parser import parse_code
from sugar.tokenizer import tokenize

_last_comments: list[str] = []


class SugarConverter:
    @staticmethod
    def convert(code: str, skin_mgr=None) -> list:
        global _last_comments
        if skin_mgr is None:
            from core.skin import SkinManager

            skin_mgr = SkinManager('chinese')
        ast, _last_comments = parse_code(code, skin_mgr)
        return ast

    @staticmethod
    def tokenize(code: str, skin_mgr=None) -> list:
        return tokenize(code)

    @staticmethod
    def get_last_comments() -> list[str]:
        return _last_comments
