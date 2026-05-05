"""
类 C 大括号语法 → 三言 S‑表达式 AST 转换器
支持：中英运算符（中缀/前缀）、连续赋值、否则若/再若、错误位置、中文引号、负数数字、原文块
"""
from typing import List


class SugarConverter:
    CN_OPS = {'大于', '小于', '等于', '不等于', '大于等于', '小于等于',
              '加', '减', '乘', '除', '余', '幂'}

    @staticmethod
    def tokenize(code: str) -> List[str]:
        tokens = []
        i, n = 0, len(code)
        while i < n:
            c = code[i]
            if c in (' ', '\t', '\n', '\r'):
                i += 1; continue
            # 多字符符号运算符
            if c == '>' and i+1 < n and code[i+1] == '=':
                tokens.append('>='); i += 2; continue
            if c == '<' and i+1 < n and code[i+1] == '=':
                tokens.append('<='); i += 2; continue
            if c == '=' and i+1 < n and code[i+1] == '=':
                tokens.append('=='); i += 2; continue
            if c == '!' and i+1 < n and code[i+1] == '=':
                tokens.append('!='); i += 2; continue
            # 注释
            if c == '/' and i+1 < n and code[i+1] == '/':
                i += 2
                while i < n and code[i] != '\n': i += 1
                continue
            if c == '#':
                i += 1
                while i < n and code[i] != '\n': i += 1
                continue
            # 单字符符号
            if c == '{':    tokens.append('{'); i += 1; continue
            if c == '}':    tokens.append('}'); i += 1; continue
            if c in ('(', '（'): tokens.append('('); i += 1; continue
            if c in (')', '）'): tokens.append(')'); i += 1; continue
            if c in (';', '；'): tokens.append(';'); i += 1; continue
            if c in (',', '，'): tokens.append(','); i += 1; continue
            if c == '=':    tokens.append('='); i += 1; continue
            if c == '>':    tokens.append('>'); i += 1; continue
            if c == '<':    tokens.append('<'); i += 1; continue
            if c == '+':    tokens.append('+'); i += 1; continue
            # 处理减号/负号：如果后面是数字，合并为负数token
            if c == '-':
                # 判断是否应该合并为负数token
                if i+1 < n and code[i+1].isdigit():
                    # 前一个字符是分隔类符号，或者当前位置是开头
                    if i == 0 or code[i-1] in (' ', '\t', '\n', '(', '（', ',', '，', '=', '{', '[', ':', '：'):
                        i += 1
                        start = i
                        while i < n and code[i].isdigit(): i += 1
                        tokens.append('-' + code[start:i])
                        continue
                tokens.append('-')
                i += 1
                continue
            if c == '*':    tokens.append('*'); i += 1; continue
            if c == '/':    tokens.append('/'); i += 1; continue
            if c == '%':    tokens.append('%'); i += 1; continue
            if c == '^':    tokens.append('^'); i += 1; continue
            if c == '.':    tokens.append('.'); i += 1; continue
            # 字符串（中英文引号）
            if c in ('"', '\u201c', '\u2018'):
                quote = c
                end_quote = '"' if quote == '"' else ('\u201d' if quote == '\u201c' else '\u2019')
                j = i + 1
                while j < n and code[j] != end_quote:
                    if code[j] == '\\': j += 1
                    j += 1
                if j < n: j += 1
                tokens.append(code[i:j]); i = j; continue
            # 标识符 / 数字 / 中文运算符 / 原文块
            if c.isalpha() or c == '_' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf':
                start = i
                while i < n and (code[i].isalnum() or code[i] == '_' or
                                 '\u4e00' <= code[i] <= '\u9fff' or
                                 '\u3400' <= code[i] <= '\u4dbf' or
                                 code[i] == '.'):
                    i += 1
                word = code[start:i]
                # 检测是否为“原文{...}”块
                if word == '原文' and i < n and code[i] == '{':
                    i += 1  # 跳过 {
                    content_start = i
                    brace_depth = 1
                    while i < n and brace_depth > 0:
                        if code[i] == '{': brace_depth += 1
                        elif code[i] == '}': brace_depth -= 1
                        i += 1
                    inner = code[content_start:i-1]   # 去掉最后那个 }
                    # 生成特殊 token，标记为原文
                    tokens.append(f'原文{{{inner}}}')
                    continue
                if word in SugarConverter.CN_OPS:
                    tokens.append(word)
                else:
                    tokens.append(word)
                continue
            if c.isdigit():
                start = i
                while i < n and code[i].isdigit(): i += 1
                tokens.append(code[start:i]); continue
            if c == '：': tokens.append('：'); i += 1; continue
            i += 1
        return tokens

    @classmethod
    def convert(cls, code: str):
        tokens = cls.tokenize(code)
        parser = _Parser(tokens)
        return parser.parse_program()


class _Parser:
    PREC = {
        '==': 1, '!=': 1, '>': 1, '<': 1, '>=': 1, '<=': 1,
        '大于': 1, '小于': 1, '等于': 1, '不等于': 1, '大于等于': 1, '小于等于': 1,
        '+': 2, '-': 2,
        '加': 2, '减': 2,
        '*': 3, '/': 3, '%': 3,
        '乘': 3, '除': 3, '余': 3,
        '^': 4, '幂': 4,
    }
    RIGHT_ASSOC = {'^', '幂'}
    OP_MAP = {
        '>': '大于', '<': '小于', '>=': '大于等于', '<=': '小于等于',
        '==': '等于', '!=': '不等于',
        '+': '加', '-': '减', '*': '乘', '/': '除', '%': '余', '^': '幂',
        '大于': '大于', '小于': '小于', '等于': '等于', '不等于': '不等于',
        '大于等于': '大于等于', '小于等于': '小于等于',
        '加': '加', '减': '减', '乘': '乘', '除': '除', '余': '余', '幂': '幂',
    }
    PREFIXABLE_OPS = {
        '幂', '加', '减', '乘', '除', '余',
        '大于', '小于', '等于', '不等于', '大于等于', '小于等于',
        '非', '且', '或', '取位'
    }

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.elif_depth = 0
        self.max_elif_depth = 50

    def _err(self, msg):
        start = max(0, self.pos - 2)
        end = min(len(self.tokens), self.pos + 3)
        ctx = ' '.join(self.tokens[start:end])
        return SyntaxError(f"{msg} （位置 {self.pos}，上下文: '{ctx}'）")

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self, expected=None):
        if self.pos >= len(self.tokens):
            if expected: raise self._err(f"期待 {expected}，但已到结尾")
            return None
        tok = self.tokens[self.pos]
        if expected and tok != expected:
            raise self._err(f"期待 {expected}，但得到 {tok}")
        self.pos += 1
        return tok

    def parse_program(self):
        stmts = []
        while self.pos < len(self.tokens):
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        return ['做'] + stmts if len(stmts) > 1 else (stmts[0] if stmts else [])

    def parse_statement(self):
        tok = self.peek()
        if tok is None: return None
        if tok == '若': return self.parse_if()
        if tok == '循环': return self.parse_loop()
        if tok == '遍历': return self.parse_traversal()
        if tok == '定义': return self.parse_definition()
        if tok == '做': return self.parse_do_block()
        if tok in ('否则', '再若'):
            raise self._err(f"{tok} 不能单独作为语句，需跟在「若」之后")
        stmt = self.parse_simple_statement()
        if self.peek() == ';':
            self.consume(';')
        return stmt

    def parse_simple_statement(self):
        tok = self.peek()
        if tok == '设':
            self.consume('设')
            var = self.consume()
            if self.peek() == '=':
                self.consume('=')
                value = self.parse_expression()
                return ['设', var, value]
            raise self._err("设定语句格式: 设 变量 = 表达式")
        elif tok == '输出':
            self.consume('输出')
            self.consume('(')
            expr = self.parse_expression()
            self.consume(')')
            return ['输出', expr]
        elif tok == '查':
            self.consume('查')
            return ['查', self.parse_expression()]
        elif tok == '置':
            self.consume('置')
            if self.peek() == '(': return self.parse_set_batch()
            obj = self.parse_expression()
            if isinstance(obj, str) and '.' in obj:
                return ['置', obj]
            elif self.peek() == '=':
                self.consume('=')
                return ['置', obj, self.parse_expression()]
            raise self._err("置 语句格式: 置 对象.状态 或 置 对象 = 状态")
        elif tok == '读':
            self.consume('读')
            return ['读', self.consume()]
        elif tok == '加载':
            self.consume('加载')
            return ['加载', self.parse_expression()]
        elif tok == '输入':
            self.consume('输入')
            self.consume('(')
            prompt = self.parse_expression() if self.peek() != ')' else None
            self.consume(')')
            return ['输入', prompt] if prompt else ['输入']
        elif tok == '调试':
            self.consume('调试')
            args = []
            if self.peek() == '(':
                self.consume('(')
                while self.peek() != ')':
                    args.append(self.parse_expression())
                    if self.peek() == ',': self.consume(',')
                self.consume(')')
            return ['调试'] + args
        # ── 新增匿名函数 ──
        elif tok == 'λ' or tok == '函数':
            self.consume(tok)
            self.consume('(')
            params = []
            while self.peek() != ')':
                params.append(self.consume())
                if self.peek() == ',':
                    self.consume(',')
            self.consume(')')
            body = self.parse_block()
            return ['函数', params] + body
        # ── 原有末尾处理（省略号不变）──
        else:
            if self.pos + 2 < len(self.tokens) and self.tokens[self.pos+1] == '=':
                var = self.consume()
                self.consume('=')
                value = self.parse_expression()
                return ['设', var, value]
            expr = self.parse_expression()
            if isinstance(expr, list) and len(expr) > 0 and isinstance(expr[0], str):
                return expr
            return expr

    def parse_set_batch(self):
        self.consume('(')
        items = []
        while self.peek() != ')':
            items.append(self.consume())
        self.consume(')')
        return ['置', items]

    def parse_expression(self, min_prec=0):
        lhs = self.parse_primary()
        while True:
            op = self.peek()
            if op not in self.PREC or self.PREC[op] < min_prec:
                break
            next_min = self.PREC[op] + (0 if op in self.RIGHT_ASSOC else 1)
            self.consume(op)
            rhs = self.parse_expression(next_min)
            internal_op = self.OP_MAP[op]
            lhs = [internal_op, lhs, rhs]
        return lhs

    def parse_primary(self):
        tok = self.peek()
        if tok is None:
            raise self._err("表达式不完整")
        if tok == '(':
            self.consume('(')
            expr = self.parse_expression()
            self.consume(')')
            return expr
        # 字符串（引号开头）
        if tok and tok[0] in ('"', '\u201c', '\u2018') and len(tok) >= 2:
            self.consume()
            return tok[1:-1]
        # 原文块：以 '原文{' 开头的 token
        if isinstance(tok, str) and tok.startswith('原文{') and tok.endswith('}'):
            self.consume()
            inner = tok[3:-1]
            return inner
        # 数字（包含负数）
        if tok.isdigit() or (tok.startswith('-') and tok[1:].isdigit()):
            self.consume()
            return int(tok)

        # 标识符或关键字
        if tok.isalpha() or tok[0] == '_' or '\u4e00' <= tok[0] <= '\u9fff':
            # ── 匿名函数：函数(参数...) { 体 } 或 λ(...) {...} ──
            if tok in ('函数', 'λ'):
                # 提前看下一个 token 是不是 '('
                if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1] == '(':
                    self.consume(tok)       # 吃掉 函数 或 λ
                    self.consume('(')
                    params = []
                    while self.peek() != ')':
                        params.append(self.consume())
                        if self.peek() == ',':
                            self.consume(',')
                    self.consume(')')
                    body = self.parse_block()
                    return [tok, params] + body

            # 普通标识符
            self.consume()
            # 函数调用：标识符后面紧跟 '('
            if self.peek() == '(':
                func = tok
                self.consume('(')
                args = []
                while self.peek() != ')':
                    args.append(self.parse_expression())
                    if self.peek() == ',':
                        self.consume(',')
                self.consume(')')
                return [func] + args
            # 前缀操作符（如 幂 1 a）
            if tok in self.PREFIXABLE_OPS:
                saved_pos = self.pos
                args = []
                while (self.peek() is not None and
                       self.peek() not in (';', '}', ')', ',') and
                       self.peek() not in self.PREC):
                    args.append(self.parse_primary())
                if not args:
                    # 没有收集到参数，可能作为函数参数传递，直接返回标识符
                    return tok
                return [tok] + args
            return tok
        raise self._err(f"未知的表达式元素: {tok}")

    def parse_block(self):
        self.consume('{')
        stmts = []
        while self.peek() != '}':
            stmts.append(self.parse_statement())
        self.consume('}')
        return stmts

    def parse_if(self):
        self.consume('若')
        self.consume('(')
        cond = self.parse_expression()
        self.consume(')')
        true_body = self.parse_block()

        while True:
            nxt = self.peek()
            if nxt == '否则':
                self.consume('否则')
                if self.peek() == '若':
                    self.consume('若')
                    self.consume('(')
                    elif_cond = self.parse_expression()
                    self.consume(')')
                    elif_body = self.parse_block()
                    return ['若', cond, ['做'] + true_body,
                            ['若', elif_cond, ['做'] + elif_body, self._parse_elif_tail()]]
                else:
                    false_body = self.parse_block()
                    return ['若', cond, ['做'] + true_body, ['做'] + false_body]
            elif nxt == '再若':
                self.consume('再若')
                self.consume('(')
                elif_cond = self.parse_expression()
                self.consume(')')
                elif_body = self.parse_block()
                false_part = self._parse_elif_tail()
                if false_part is not None:
                    return ['若', cond, ['做'] + true_body,
                            ['若', elif_cond, ['做'] + elif_body, false_part]]
                else:
                    return ['若', cond, ['做'] + true_body,
                            ['若', elif_cond, ['做'] + elif_body]]
            else:
                return ['若', cond, ['做'] + true_body]

    def _parse_elif_tail(self):
        self.elif_depth += 1
        if self.elif_depth > self.max_elif_depth:
            raise self._err("否则若/再若 嵌套层数过多")
        try:
            while True:
                nxt = self.peek()
                if nxt == '否则':
                    self.consume('否则')
                    if self.peek() == '若':
                        self.consume('若')
                        self.consume('(')
                        cond = self.parse_expression()
                        self.consume(')')
                        body = self.parse_block()
                        return ['若', cond, ['做'] + body, self._parse_elif_tail()]
                    else:
                        false_body = self.parse_block()
                        return ['做'] + false_body
                elif nxt == '再若':
                    self.consume('再若')
                    self.consume('(')
                    cond = self.parse_expression()
                    self.consume(')')
                    body = self.parse_block()
                    false_part = self._parse_elif_tail()
                    if false_part is not None:
                        return ['若', cond, ['做'] + body, false_part]
                    else:
                        return ['若', cond, ['做'] + body]
                else:
                    return None
        finally:
            self.elif_depth -= 1

    def parse_loop(self):
        self.consume('循环')
        self.consume('(')
        cond = self.parse_expression()
        self.consume(')')
        body = self.parse_block()
        return ['循环', cond] + body

    def parse_traversal(self):
        self.consume('遍历')
        var = self.consume()
        self.consume('从')
        start = self.parse_expression()
        self.consume('到')
        end = self.parse_expression()
        body = self.parse_block()
        return ['遍历', var, start, end] + body

    def parse_definition(self):
        self.consume('定义')
        name = self.consume()
        self.consume('(')
        params = []
        while self.peek() != ')':
            params.append(self.consume())
            if self.peek() == ',': self.consume(',')
        self.consume(')')
        body = self.parse_block()
        return ['定义', name, params] + body

    def parse_do_block(self):
        self.consume('做')
        return ['做'] + self.parse_block()