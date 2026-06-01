"""Pratt 语法分析器：运算符优先级、错误恢复

Pratt 解析用「前缀/中缀」统一处理所有表达式：
- 前缀（null_denotation）: 字面量、标识符、括号、前缀操作符
- 中缀（left_denotation）: 二元操作符、函数调用、索引
- 优先级（PREC）控制结合性，避免手写左递归
"""

from __future__ import annotations
from typing import Optional, Any
from values import SanyanSyntaxError
from sugar.tokenizer import Token, tokenize
from sugar.errors import SugarErrorReporter
from sugar.ast_nodes import (
    KEYWORD_MAP,
    OP_MAP,
    PREC,
    RIGHT_ASSOC,
    PREFIXABLE_OPS,
    PREFIXABLE_SINGLE_ARG,
    _is_ident,
    annotate_ast,
)


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

    def _node(self, items: list, tok: Optional[Token] = None):
        from values import SrcNode

        if tok is None:
            tok = self.tokens[max(0, min(self.pos - 1, len(self.tokens) - 1))] if self.tokens else Token('', '', 0, 0)
        return SrcNode(items, line=tok.line, col=tok.col)

    def _wrap(self, items):
        """Wrap list returns with SrcNode when they are plain lists."""
        from values import SrcNode

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
        """分派语句解析：字典调度简单分支 + if-elif 复杂分支。"""
        tok = self.peek()
        if tok is None:
            return None
        kw = self._kw(tok)

        # 裸赋值（无关键字，形如 `x = 1`）
        if _is_ident(tok.value) and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].value == '=':
            var_name = self.advance()
            self.advance()
            expr = self.parse_expression()
            if self.peek() and self.peek().value == ';':
                self.advance()
            return ['set', var_name.value, expr]

        # 简单分支调度
        simple = {
            'set': lambda: self._parse_set(),
            'loop': lambda: self._parse_loop(),
            'return': lambda: self._parse_return(),
            'break': lambda: self._parse_break_continue('break'),
            'continue': lambda: self._parse_break_continue('continue'),
            'context': lambda: self._parse_context(),
            'export': lambda: self._parse_export(),
            'import': lambda: self._parse_import(),
        }
        if kw in simple:
            return simple[kw]()

        # 复杂分支保留 if-elif
        if kw == 'write':
            return self._parse_write()
        if kw == 'if':
            return self.parse_if()
        if kw == 'for':
            return self._parse_for()
        if kw == 'fn':
            return self._parse_fn()
        if kw == 'try':
            return self._parse_try()
        if kw == 'judge':
            return self._parse_judge()
        if kw == 'register_device':
            return self._parse_register_device()

        # 表达式语句
        expr = self.parse_expression()
        if self.peek() and self.peek().value == ';':
            self.advance()
        return expr

    # ── 语句解析辅助方法（被 parse_statement 字典 dispatch 调用）──

    def _parse_set(self):
        self.advance()
        var_name = self.advance()
        if self.peek() and self.peek().value == '=':
            self.advance()
        expr = self.parse_expression()
        if self.peek() and self.peek().value == ';':
            self.advance()
        return ['set', var_name.value, expr]

    def _parse_loop(self):
        self.advance()
        cond = self.parse_expression()
        body = self.parse_block()
        return ['loop', cond, body]

    def _parse_return(self):
        self.advance()
        expr = self.parse_expression()
        if self.peek() and self.peek().value == ';':
            self.advance()
        return ['return', expr]

    def _parse_break_continue(self, kind):
        self.advance()
        if self.peek() and self.peek().value == ';':
            self.advance()
        return [kind]

    def _parse_context(self):
        self.advance()
        obj = self.parse_expression()
        body = self.parse_block()
        return ['context', obj, body]

    def _parse_export(self):
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

    def _parse_import(self):
        self.advance()
        path = self.parse_expression()
        if self.peek() and self.peek().value in ('为', 'as'):
            self.advance()
            alias = self.advance()
            return ['import', path, '为', alias.value if alias else '']
        return ['import', path]

    def _parse_write(self):
        next_tok = self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
        if next_tok and next_tok.value == '(':
            self.pos -= 1
            return self.parse_expression()
        self.advance()
        target = self.advance()
        if self.peek() and self.peek().value == '=':
            self.advance()
        value = self.parse_expression()
        if self.peek() and self.peek().value == ';':
            self.advance()
        return ['write', target.value, value]

    def _parse_for(self):
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

    def _parse_fn(self):
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

    def _parse_try(self):
        self.advance()
        try_body = self.parse_block()
        if self.peek() and self._kw(self.peek()) == 'catch':
            self.advance()
            err_var = self.advance()
            catch_body = self.parse_block()
            if isinstance(catch_body, list) and len(catch_body) > 0 and catch_body[0] == 'do':
                catch_body_list = catch_body[1:] if len(catch_body) > 1 else [TritValue(0)]
            else:
                catch_body_list = (
                    [catch_body]
                    if isinstance(catch_body, list) and len(catch_body) > 0 and catch_body[0] == 'do'
                    else [catch_body]
                )
            return ['try', try_body, ['捕获', err_var.value] + catch_body_list]

    def _parse_judge(self):
        self.advance()
        val = self.parse_expression()
        self._expect('{')
        cases = []
        while self.peek() and self.peek().value != '}':
            cases.append(self.parse_expression())
            cases.append(self.parse_block())
        self._expect('}')
        return ['judge', val] + cases

    def _parse_register_device(self):
        self.advance()
        name_tok = self.advance()
        name = name_tok.value if name_tok else ''
        if self.peek() and self.peek().value in ('为', 'as'):
            self.advance()
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
            except SanyanSyntaxError:
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

        # lambda（仅当后跟 ( 时才作为 lambda 关键字，否则降级为标识符）
        if kw == 'lambda' and self.peek() and self.peek().value == '(':
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


def parse_tokens(tokens: list[Token], reporter: SugarErrorReporter, source: str = '') -> Any:
    parser = _Parser(tokens, reporter, source)
    ast = parser.parse_program()
    ast = annotate_ast(ast, tokens)
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
