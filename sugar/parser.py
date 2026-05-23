"""Pratt 语法分析器：运算符优先级、错误恢复

Pratt 解析用「前缀/中缀」统一处理所有表达式：
- 前缀（null_denotation）: 字面量、标识符、括号、前缀操作符
- 中缀（left_denotation）: 二元操作符、函数调用、索引
- 优先级（PREC）控制结合性，避免手写左递归
"""

from __future__ import annotations
import json
import os
from typing import Optional, Any
from sugar.lexer import Token, tokenize
from sugar.errors import SugarErrorReporter
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


class _Parser:
    """Pratt 解析器：将 token 流 → AST。

    核心流程：
    1. parse_program → parse_statement 循环（语句级分派）
    2. parse_expression → parse_primary（表达式级 Pratt 循环）
    3. parse_primary 处理字面量/标识符/前缀操作/lambda/调用/索引
    """

    def __init__(self, tokens: list[Token], reporter: SugarErrorReporter, source: str = '') -> None:
        self.tokens = tokens
        self.pos = 0
        self.reporter = reporter
        self.source = source
        self._comments: list[str] = []

    def _node(self, items: list, tok: Optional[Token] = None) -> SrcNode:
        if tok is None:
            tok = self.tokens[max(0, min(self.pos - 1, len(self.tokens) - 1))] if self.tokens else Token('', '', 0, 0)
        return SrcNode(items, line=tok.line, col=tok.col)

    def _wrap(self, items):
        """Wrap list returns with SrcNode when they are plain lists."""
        if isinstance(items, list) and not isinstance(items, SrcNode):
            tok = self.peek() or (self.tokens[-1] if self.tokens else Token('', '', 0, 0))
            return SrcNode(items, line=tok.line, col=tok.col)
        return items

    def _skip_comments(self) -> None:
        while self.pos < len(self.tokens) and self.tokens[self.pos].kind == 'COMMENT':
            self._comments.append(self.tokens[self.pos].value)
            self.pos += 1

    def peek(self) -> Optional[Token]:
        self._skip_comments()
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self) -> Optional[Token]:
        self._skip_comments()
        tok = self.peek()
        if tok:
            self.pos += 1
        return tok

    def _kw(self, tok: Optional[Token]) -> str:
        if tok is None:
            return ''
        return KEYWORD_MAP.get(tok.value, tok.value)

    def _op(self, tok: Optional[Token]) -> str:
        if tok is None:
            return ''
        return OP_MAP.get(tok.value, tok.value)

    def _expect(self, kind: str) -> Optional[Token]:
        tok = self.peek()
        if tok is None:
            self.reporter.error(self.tokens[-1].line if self.tokens else 1, 1, f"期望 '{kind}'，但已到文件末尾")
            return None
        if tok.value != kind:
            self.reporter.error(tok.line, tok.col, f"期望 '{kind}'，但得到 '{tok.value}'")
            return None
        return self.advance()

    def parse_program(self) -> Any:
        """入口：解析整个程序（多语句列表）。

        空程序返回 None，单语句直接返回节点，多语句用 'do' 包装。
        解析失败的语句通过跳过一个 token 恢复（错误恢复策略）。
        """
        stmts = []
        while self.peek():
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
            else:
                # 错误恢复：跳过一个 token 继续
                self.advance()
        if not stmts:
            return None
        return ['do'] + stmts if len(stmts) > 1 else stmts[0]

    def parse_statement(self) -> Any:
        """分派语句解析：根据首 token 的关键字类型 dispatch。

        支持：赋值、set、write、if、loop、for、fn、return、
        break、continue、try、judge、context、export、register_device。
        非关键字开头则回退到表达式语句。
        """
        tok = self.peek()
        if tok is None:
            return None
        kw = self._kw(tok)

        # 裸赋值（无关键字，形如 `x = 1`）
        if _is_ident(tok.value) and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].value == '=':
            var_name = self.advance()
            self.advance()  # skip '='
            expr = self.parse_expression()
            if self.peek() and self.peek().value == ';':
                self.advance()
            return ['set', var_name.value, expr]

        if kw == 'set':
            self.advance()
            var_name = self.advance()
            if self.peek() and self.peek().value == '=':
                self.advance()
            expr = self.parse_expression()
            if self.peek() and self.peek().value == ';':
                self.advance()
            return ['set', var_name.value, expr]

        if kw == 'write':
            # 检查是否是函数调用风格 置(对象, 值)
            next_tok = self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
            if next_tok and next_tok.value == '(':
                # 退回到表达式解析
                self.pos -= 1
                expr = self.parse_expression()
                return expr
            self.advance()
            target = self.advance()
            if self.peek() and self.peek().value == '=':
                self.advance()
            value = self.parse_expression()
            if self.peek() and self.peek().value == ';':
                self.advance()
            return ['write', target.value, value]

        if kw == 'if':
            return self.parse_if()

        if kw == 'loop':
            self.advance()
            cond = self.parse_expression()
            body = self.parse_block()
            return ['loop', cond, body]

        if kw == 'for':
            self.advance()
            var = self.advance()
            next_tok = self.peek()
            next_kw = self._kw(next_tok)
            if next_kw == 'from':
                self.advance()
                start_val = self.parse_expression()
                if self.peek() and self._kw(self.peek()) == 'to':
                    self.advance()
                end_val = self.parse_expression()
                body = self.parse_block()
                return ['for', var.value, start_val, end_val, body]
            else:
                if next_kw == 'in':
                    self.advance()
                lst = self.parse_expression()
                body = self.parse_block()
                return ['forin', var.value, lst, body]

        if kw == 'fn':
            self.advance()
            name = self.advance()
            params = []
            param_types = {}
            if self.peek() and self.peek().value == '(':
                self.advance()
                while self.peek() and self.peek().value != ')':
                    p = self.advance()
                    if self.peek() and self.peek().value == ':':
                        self.advance()
                        t = self.advance()
                        param_types[p.value] = t.value
                    params.append(p.value)
                    if self.peek() and self.peek().value == ',':
                        self.advance()
                self._expect(')')
            return_type = None
            if self.peek() and self.peek().value == '->':
                self.advance()
                return_type = self.advance().value
            if return_type:
                param_types['__return__'] = return_type
            body = self.parse_block()
            if param_types:
                return ['fn', name.value, params, param_types, body]
            return ['fn', name.value, params, body]

        if kw == 'return':
            self.advance()
            expr = self.parse_expression()
            if self.peek() and self.peek().value == ';':
                self.advance()
            return ['return', expr]

        if kw == 'break':
            self.advance()
            if self.peek() and self.peek().value == ';':
                self.advance()
            return ['break']

        if kw == 'continue':
            self.advance()
            if self.peek() and self.peek().value == ';':
                self.advance()
            return ['continue']

        if kw == 'try':
            self.advance()
            try_body = self.parse_block()
            # 验证下一个 token 是 '捕获' 或 'catch'
            catch_tok = self.peek()
            if catch_tok:
                catch_kw = KEYWORD_MAP.get(catch_tok.value, catch_tok.value)
                if catch_kw != 'catch':
                    raise SyntaxError(f"行 {catch_tok.line}: 期望 'catch'，但得到 '{catch_tok.value}'")
            self.advance()
            err_var = '_'
            if self.peek() and self.peek().value == '(':
                self.advance()
                err_var_tok = self.advance()
                err_var = err_var_tok.value if err_var_tok else '_'
                self._expect(')')
            catch_body = self.parse_block()
            if not isinstance(catch_body, list) or (
                isinstance(catch_body, list) and len(catch_body) > 0 and catch_body[0] != 'do'
            ):
                catch_body_list = [catch_body]
            else:
                catch_body_list = (
                    catch_body[1:]
                    if isinstance(catch_body, list) and len(catch_body) > 0 and catch_body[0] == 'do'
                    else [catch_body]
                )
            return ['try', try_body, ['捕获', err_var] + catch_body_list]

        if kw == 'judge':
            self.advance()
            val = self.parse_expression()
            self._expect('{')
            cases = []
            while self.peek() and self.peek().value != '}':
                cases.append(self.parse_expression())
                cases.append(self.parse_block())
            self._expect('}')
            return ['judge', val] + cases

        if kw == 'context':
            self.advance()
            obj = self.parse_expression()
            body = self.parse_block()
            return ['context', obj, body]

        if kw == 'export':
            self.advance()
            names = []
            while self.peek() and self.peek().value not in (';', '{', '}'):
                name_tok = self.advance()
                names.append(name_tok.value)
                if self.peek() and self.peek().value == ',':
                    self.advance()
            if self.peek() and self.peek().value == ';':
                self.advance()
            return ['export'] + names

        if kw == 'register_device':
            self.advance()
            name_tok = self.advance()
            name = name_tok.value if name_tok else ''
            # 跳过 '为' / 'as'
            if self.peek() and self.peek().value in ('为', 'as'):
                self.advance()
            # 读取设备类型和参数
            type_tok = self.advance()
            device_type = type_tok.value if type_tok else 'mock'
            params = []
            if self.peek() and self.peek().value == '(':
                self.advance()
                while self.peek() and self.peek().value != ')':
                    params.append(self.parse_expression())
                    if self.peek() and self.peek().value == ',':
                        self.advance()
                self._expect(')')
            return ['register_device', name, device_type] + params

        # 表达式语句
        expr = self.parse_expression()
        if self.peek() and self.peek().value == ';':
            self.advance()
        return expr

    def parse_if(self, advance_kw: bool = True) -> Any:
        if advance_kw:
            self.advance()  # consume 'if'/'elif' keyword
        cond = self.parse_expression()
        then_body = self.parse_block()
        else_body = None
        if self.peek() and self._kw(self.peek()) == 'elif':
            self.advance()  # consume 'elif'
            else_body = self.parse_if(advance_kw=False)
        elif self.peek() and self._kw(self.peek()) == 'else':
            self.advance()
            else_body = self.parse_block()
        return ['if', cond, then_body, else_body] if else_body else ['if', cond, then_body]

    def parse_block(self) -> Any:
        tok = self.peek()
        if tok and tok.value == '{':
            self.advance()
            stmts = []
            while self.peek() and self.peek().value != '}':
                s = self.parse_statement()
                if s is not None:
                    stmts.append(s)
            self._expect('}')
            return ['do'] + stmts if len(stmts) != 1 else stmts[0]
        else:
            return self.parse_statement()

    def parse_expression(self, precedence: int = 0) -> Any:
        """Pratt 核心：表达式解析（中缀循环）。

        - 先调用 parse_primary 获取「左值」（前缀 nud）
        - 循环检查下一个 token 是否为中缀操作符（led）
        - 若当前操作符优先级 >= precedence 则继续结合
        - 右结合（RIGHT_ASSOC）维持同级优先级不递增
        """
        left = self.parse_primary()
        while True:
            tok = self.peek()
            if tok is None:
                break
            op = self._op(tok)
            if op not in PREC or PREC[op] < precedence:
                break
            self.advance()
            next_prec = PREC[op] + (0 if op in RIGHT_ASSOC else 1)
            right = self.parse_expression(next_prec)
            left = [op, left, right]
        return left

    def parse_primary(self) -> Any:
        """Pratt 前缀（nud）分派：字面量、括号、前缀操作、lambda、调用、索引。

        按优先级依次检查：
        1. 括号表达式 (...)
        2. 点号属性访问 obj.attr
        3. 列表推导式/字面量 [...]
        4. 前缀操作符（read/not/digit 等）
        5. lambda 表达式
        6. 字符串/数字字面量
        7. 函数调用 name(...) 或容器索引 name[...]
        8. 纯标识符
        """
        tok = self.advance()
        if tok is None:
            return None

        if tok.value == '(':
            expr = self.parse_expression()
            self._expect(')')
            return expr

        # 点号属性访问
        if self.peek() and self.peek().value == '.':
            self.advance()
            attr = self.advance()
            return f'{tok.value}.{attr.value if attr else ""}'

        # 列表推导式 / 列表字面量
        if tok.value == '[':
            saved_pos = self.pos
            try:
                inner_expr = self.parse_expression()
            except SyntaxError:
                inner_expr = None
                self.pos = saved_pos

            if inner_expr is not None and self.peek() and self._kw(self.peek()) == 'for':
                self.advance()
                var = self.advance()
                if self.peek() and self._kw(self.peek()) == 'in':
                    self.advance()
                lst = self.parse_expression()
                cond = None
                if self.peek() and self._kw(self.peek()) == 'if':
                    self.advance()
                    cond = self.parse_expression()
                self._expect(']')
                filter_node = ['filter', ['lambda', [var.value], cond], lst] if cond else lst
                return ['map', ['lambda', [var.value], [inner_expr]], filter_node]

            # 普通列表
            self.pos = saved_pos
            items = []
            while self.peek() and self.peek().value != ']':
                items.append(self.parse_expression())
                if self.peek() and self.peek().value == ',':
                    self.advance()
            self._expect(']')
            return ['list'] + items

        # 前缀操作符
        kw = KEYWORD_MAP.get(tok.value, OP_MAP.get(tok.value, tok.value))
        if kw in PREFIXABLE_OPS:
            if kw in PREFIXABLE_SINGLE_ARG:
                return [kw, self.parse_expression(10)]
            # 多参数前缀操作符需要括号
            self._expect('(')
            args = []
            while self.peek() and self.peek().value != ')':
                args.append(self.parse_expression())
                if self.peek() and self.peek().value == ',':
                    self.advance()
            self._expect(')')
            return [kw] + args

        # lambda
        if kw == 'lambda':
            self._expect('(')
            params = []
            while self.peek() and self.peek().value != ')':
                p = self.advance()
                if self.peek() and self.peek().value == ':':
                    self.advance()
                    self.advance()
                params.append(p.value)
                if self.peek() and self.peek().value == ',':
                    self.advance()
            self._expect(')')
            body = self.parse_block()
            return ['lambda', params, body]

        # 字符串字面量
        if tok.kind == 'STRING':
            return tok.value

        # 数字字面量
        if tok.kind == 'NUMBER':
            return tok.value

        # 函数调用: name(args)
        if self.peek() and self.peek().value == '(':
            self.advance()
            args = []
            while self.peek() and self.peek().value != ')':
                args.append(self.parse_expression())
                if self.peek() and self.peek().value == ',':
                    self.advance()
            self._expect(')')
            return [tok.value] + args

        # 容器索引: name[idx]
        if self.peek() and self.peek().value == '[':
            self.advance()
            idx = self.parse_expression()
            self._expect(']')
            return ['get', tok.value, idx]

        # 标识符
        return tok.value


def _annotate_ast(ast, tokens):
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


def parse_tokens(tokens: list[Token], reporter: SugarErrorReporter, source: str = '') -> Any:
    parser = _Parser(tokens, reporter, source)
    ast = parser.parse_program()
    ast = _annotate_ast(ast, tokens)
    return ast, parser._comments


def parse_code(code: str, skin_mgr=None) -> tuple[Any, list[str]]:
    reporter = SugarErrorReporter(code)
    tokens = tokenize(code)

    # 应用皮肤映射
    if skin_mgr:
        for tok in tokens:
            if tok.kind == 'WORD':
                internal_kw = skin_mgr.get_internal_keyword(tok.value)
                internal_op = skin_mgr.get_internal_op(tok.value)
                if internal_kw:
                    tok.value = internal_kw
                elif internal_op:
                    tok.value = internal_op

    ast, comments = parse_tokens(tokens, reporter, code)
    reporter.raise_if_any()
    return ast, comments
