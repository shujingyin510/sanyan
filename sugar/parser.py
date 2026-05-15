"""Pratt 语法分析器：运算符优先级、错误恢复"""
from __future__ import annotations
from typing import Optional, Any
from sugar.lexer import Token, tokenize
from sugar.errors import SugarErrorReporter


# 关键字映射
KEYWORD_MAP = {
    '设': 'set', '若': 'if', '再若': 'elif', '否则': 'else',
    '循环': 'loop', '遍历': 'for', '定义': 'fn', '返回': 'return',
    '跳出': 'break', '继续': 'continue', '尝试': 'try', '捕获': 'catch',
    '判': 'judge', '函数': 'lambda', 'λ': 'lambda', '在': 'in',
    '导入': 'import', '输出': 'print', '加载': 'load', '计数': 'count',
    '对': 'context', '置': 'write', '读': 'read', '查': 'query',
    '从': 'from', '到': 'to', '导出': 'export',
    '注册设备': 'register_device',
    'set': 'set', 'if': 'if', 'elif': 'elif', 'else': 'else',
    'loop': 'loop', 'for': 'for', 'fn': 'fn', 'return': 'return',
    'break': 'break', 'continue': 'continue', 'try': 'try', 'catch': 'catch',
    'judge': 'judge', 'lambda': 'lambda', 'in': 'in', 'import': 'import',
    'print': 'print', 'load': 'load', 'count': 'count', 'context': 'context',
    'write': 'write', 'read': 'read', 'query': 'query',
}

# 运算符映射
OP_MAP = {
    '大于': 'gt', '小于': 'lt', '等于': 'eq', '不等于': 'ne',
    '大于等于': 'gte', '小于等于': 'lte', '不大于': 'ngt', '不小于': 'nlt',
    '加': 'add', '减': 'sub', '乘': 'mul', '除': 'div', '余': 'mod', '幂': 'pow',
    '且': 'and', '或': 'or', '非': 'not', '取位': 'digit',
    '>': 'gt', '<': 'lt', '==': 'eq', '!=': 'ne', '>=': 'gte', '<=': 'lte',
    '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'mod', '^': 'pow',
    '!>': 'ngt', '!<': 'nlt',
}

# 运算符优先级
PREC = {
    'and': 1, 'or': 1,
    'eq': 2, 'ne': 2, 'gt': 2, 'lt': 2, 'gte': 2, 'lte': 2, 'ngt': 2, 'nlt': 2,
    'add': 3, 'sub': 3,
    'mul': 4, 'div': 4, 'mod': 4,
    'pow': 5,
}
RIGHT_ASSOC = {'pow'}

# 可前缀的操作符
PREFIXABLE_OPS = {
    'add', 'sub', 'mul', 'div', 'mod', 'pow',
    'gt', 'lt', 'eq', 'ne', 'gte', 'lte', 'ngt', 'nlt',
    'not', 'and', 'or', 'digit', 'read', 'import', 'load', 'print', 'query',
}
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
    def __init__(self, tokens: list[Token], reporter: SugarErrorReporter, source: str = "") -> None:
        self.tokens = tokens
        self.pos = 0
        self.reporter = reporter
        self.source = source

    def peek(self) -> Optional[Token]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self) -> Optional[Token]:
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
        tok = self.peek()
        if tok is None:
            return None
        kw = self._kw(tok)

        # 裸赋值
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
            if self.peek() and self.peek().value == '(':
                self.advance()
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
            if not isinstance(catch_body, list) or (isinstance(catch_body, list) and len(catch_body) > 0 and catch_body[0] != 'do'):
                catch_body_list = [catch_body]
            else:
                catch_body_list = catch_body[1:] if isinstance(catch_body, list) and len(catch_body) > 0 and catch_body[0] == 'do' else [catch_body]
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

    def parse_if(self) -> Any:
        self.advance()
        cond = self.parse_expression()
        then_body = self.parse_block()
        else_body = None
        if self.peek() and self._kw(self.peek()) == 'elif':
            self.advance()
            else_body = self.parse_if()
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
            return f"{tok.value}.{attr.value if attr else ''}"

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


def parse_tokens(tokens: list[Token], reporter: SugarErrorReporter, source: str = "") -> Any:
    parser = _Parser(tokens, reporter, source)
    return parser.parse_program()


def parse_code(code: str, skin_mgr=None) -> Any:
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

    ast = parse_tokens(tokens, reporter, code)
    reporter.raise_if_any()
    return ast
