"""糖语法转换器：类 C 语法 -> S-表达式 AST

重构版本：拆分为 lexer + parser + errors 模块。
保留 SugarConverter.convert() 接口以保持向后兼容。
"""
from sugar.parser import parse_code
from sugar.lexer import tokenize
from sugar.errors import SugarErrorReporter


class SugarConverter:
    @staticmethod
    def convert(code: str, skin_mgr=None) -> list:
        """将糖语法代码转换为 S-表达式 AST。

        优先使用新解析器，失败时回退到旧解析器。
        """
        try:
            ast = parse_code(code, skin_mgr)
            return ast
        except SyntaxError:
            # 回退到旧解析器
            from sugar.sugar_old import SugarConverter as OldConverter
            return OldConverter.convert(code, skin_mgr)

    @staticmethod
    def tokenize(code: str, skin_mgr=None) -> list:
        """词法分析，返回 token 列表。"""
        return tokenize(code)
