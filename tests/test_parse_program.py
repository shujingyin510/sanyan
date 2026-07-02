"""core/parser.parse_program：解析全部顶层形式。

根因回归守护：parse() 只取第一个顶层形式（REPL 单表达式语义），文件级入口曾误用它，
多顶层表达式的 .san 第一条之后全部静默丢失、两引擎丢法还不同（差分验证器抓到的首个真分歧）。
"""

import pytest

from core.lexer import tokenize
from core.parser import parse, parse_program
from core.values import SanyanSyntaxError


def test_single_form_matches_parse():
    code = '(输出 (加 1 2))'
    assert parse_program(tokenize(code)) == [parse(tokenize(code))]


def test_multiple_forms_all_parsed():
    forms = parse_program(tokenize('(设 x 10)\n(输出 (加 x 5))'))
    assert len(forms) == 2
    assert forms[0][0] == '设' and forms[1][0] == '输出'


def test_parse_keeps_first_only_semantics():
    # parse 的既有语义不变（REPL 单表达式）：多形式时仍只取第一个
    ast = parse(tokenize('(输出 1)\n(输出 2)'))
    assert isinstance(ast, list) and ast[0] == '输出' and '2' not in str(ast)


def test_unbalanced_raises():
    with pytest.raises(SanyanSyntaxError):
        parse_program(tokenize('(输出 1'))


def test_empty_tokens():
    assert parse_program([]) == []
    assert parse([]) is None
