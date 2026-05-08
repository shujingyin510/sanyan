"""
类 C 大括号语法 → 三言 S‑表达式 AST 转换器
支持：中英运算符、全角符号、国际皮肤、模板插值、三态分支判
"""
from typing import List


class SugarConverter:
    @staticmethod
    def tokenize(code: str) -> List[str]:
        # 全局替换全角空格为半角空格，彻底解决中文输入法问题
        code = code.replace('\u3000', ' ')
        tokens = []
        current = ''
        i = 0
        length = len(code)

        fullwidth_map = {
            '（': '(', '）': ')', '，': ',', '；': ';', '＝': '=', '＞': '>', '＜': '<',
            '＋': '+', '－': '-', '＊': '*', '／': '/', '％': '%', '＾': '^',
            '！': '!', '｛': '{', '｝': '}', '：': ':', '。': '.',
        }

        while i < length:
            c = code[i]
            # 跳过所有空白（半角、全角空格、制表等）
            if c in (' ', '\t', '\n', '\r', '\u3000'):
                if current:
                    tokens.append(current)
                    current = ''
                i += 1
                continue

            # 全角符号转换（字符串内部不会执行到这里，因为字符串已单独处理并跳过）
            if c in fullwidth_map:
                c = fullwidth_map[c]

            # 字符串处理（中英文引号）
            if c in ('"', '\u201c', '\u2018'):
                if current:
                    tokens.append(current)
                    current = ''
                quote = c
                end_quote = '"' if quote == '"' else ('\u201d' if quote == '\u201c' else '\u2019')
                j = i + 1
                while j < length and code[j] != end_quote:
                    if code[j] == '\\':
                        j += 1
                    j += 1
                if j < length:
                    j += 1
                tokens.append(code[i:j])
                i = j
                continue

            # 注释处理
            if c == '/' and i+1 < length and code[i+1] == '/':
                if current:
                    tokens.append(current)
                    current = ''
                i += 2
                while i < length and code[i] != '\n':
                    i += 1
                continue
            if c == '#':
                if current:
                    tokens.append(current)
                    current = ''
                i += 1
                while i < length and code[i] != '\n':
                    i += 1
                continue

            # 单字符符号
            if c in ('{', '}', '(', ')', ';', ',', '=', '>', '<', '+', '-', '*', '/', '%', '^', '.'):
                if current:
                    tokens.append(current)
                    current = ''
                # 多字符操作符
                if c == '>' and i+1 < length and code[i+1] == '=':
                    tokens.append('>='); i += 2; continue
                if c == '<' and i+1 < length and code[i+1] == '=':
                    tokens.append('<='); i += 2; continue
                if c == '=' and i+1 < length and code[i+1] == '=':
                    tokens.append('=='); i += 2; continue
                if c == '!' and i+1 < length and code[i+1] == '=':
                    tokens.append('!='); i += 2; continue
                if c == '-' and i+1 < length and code[i+1].isdigit():
                    # 负数
                    if i == 0 or code[i-1] in (' ', '\t', '\n', '(', '（', ',', '，', '=', '{', '[', ':', '：'):
                        i += 1
                        start = i
                        while i < length and code[i].isdigit():
                            i += 1
                        tokens.append('-' + code[start:i])
                        continue
                tokens.append(c)
                i += 1
                continue

            # 标识符、数字、中文关键字
            if c.isalpha() or c == '_' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf':
                start = i
                while i < length and (code[i].isalnum() or code[i] == '_' or
                                      '\u4e00' <= code[i] <= '\u9fff' or
                                      '\u3400' <= code[i] <= '\u4dbf' or
                                      code[i] == '.'):
                    i += 1
                word = code[start:i]
                if word == '原文' and i < length and code[i] == '{':
                    i += 1
                    content_start = i
                    brace_depth = 1
                    while i < length and brace_depth > 0:
                        if code[i] == '{': brace_depth += 1
                        elif code[i] == '}': brace_depth -= 1
                        i += 1
                    inner = code[content_start:i-1]
                    tokens.append(f'原文{{{inner}}}')
                    continue
                if word == '模板' and i < length and code[i] == '{':
                    template_tokens, new_i = SugarConverter._parse_template(code, i+1)
                    tokens.extend(template_tokens)
                    i = new_i
                    continue
                tokens.append(word)
                continue

            if c.isdigit():
                start = i
                while i < length and code[i].isdigit():
                    i += 1
                tokens.append(code[start:i])
                continue

            i += 1

        if current:
            tokens.append(current)
        return tokens

    @staticmethod
    def _parse_template(code: str, start: int):
        i = start
        parts = []
        current_text = []
        while i < len(code):
            ch = code[i]
            if ch == '}':
                if current_text:
                    parts.append(''.join(current_text))
                    current_text = []
                i += 1
                break
            elif ch == '$' and i+1 < len(code) and code[i+1] == '{':
                if current_text:
                    parts.append(''.join(current_text))
                    current_text = []
                i += 2
                expr_tokens, new_i = SugarConverter._parse_expr_until_brace(code, i)
                parts.append(expr_tokens)
                i = new_i
            else:
                current_text.append(ch)
                i += 1
        if current_text:
            parts.append(''.join(current_text))
        tokens = ['concat', '(']
        for idx, part in enumerate(parts):
            if idx % 2 == 0:
                tokens.append(f'"{part}"')
            else:
                tokens.extend(part)
            if idx < len(parts) - 1:
                tokens.append(',')
        tokens.append(')')
        return tokens, i

    @staticmethod
    def _parse_expr_until_brace(code: str, start: int):
        i = start
        brace_depth = 1
        expr_chars = []
        while i < len(code) and brace_depth > 0:
            ch = code[i]
            if ch == '{':
                brace_depth += 1
                expr_chars.append('{')
                i += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    i += 1
                    break
                else:
                    expr_chars.append('}')
                    i += 1
            elif ch == '"':
                j = i + 1
                while j < len(code) and code[j] != '"':
                    if code[j] == '\\': j += 1
                    j += 1
                expr_chars.extend(code[i:j+1])
                i = j + 1
            else:
                expr_chars.append(ch)
                i += 1
        expr_str = ''.join(expr_chars)
        expr_tokens = SugarConverter.tokenize(expr_str)
        return expr_tokens, i

    @classmethod
    def convert(cls, code: str, skin_manager=None):
        tokens = cls.tokenize(code)
        parser = _Parser(tokens, skin_manager)
        return parser.parse_program()


class _Parser:
    @staticmethod
    def _is_ident(tok):
        if not tok or tok[0].isdigit():
            return False
        for c in tok:
            if c.isalnum() or c == '_' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf':
                continue
            return False
        return True

    def __init__(self, tokens, skin_manager=None):
        self.tokens = tokens
        self.pos = 0
        self.elif_depth = 0
        self.max_elif_depth = 50
        self.skin = skin_manager

        # 操作符映射
        self.OP_MAP = {}
        if self.skin:
            for intern, name in self.skin.skin_data.get('operators', {}).items():
                self.OP_MAP[name] = intern
            self.OP_MAP.update({
                '>': 'gt', '<': 'lt', '==': 'eq', '!=': 'ne', '>=': 'gte', '<=': 'lte',
                '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'mod', '^': 'pow'
            })
        else:
            self.OP_MAP = {
                '大于': 'gt', '小于': 'lt', '等于': 'eq', '不等于': 'ne',
                '大于等于': 'gte', '小于等于': 'lte',
                '加': 'add', '减': 'sub', '乘': 'mul', '除': 'div', '余': 'mod', '幂': 'pow',
                '且': 'and', '或': 'or', '非': 'not', '取位': 'digit',
                '>': 'gt', '<': 'lt', '==': 'eq', '!=': 'ne', '>=': 'gte', '<=': 'lte',
                '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'mod', '^': 'pow'
            }

        # 优先级（包含逻辑运算符）
        self.PREC = {
            'and': 1, 'or': 1,           # 逻辑最低
            'eq': 2, 'ne': 2, 'gt': 2, 'lt': 2, 'gte': 2, 'lte': 2,  # 比较
            'add': 3, 'sub': 3,           # 加减
            'mul': 4, 'div': 4, 'mod': 4, # 乘除取余
            'pow': 5,                     # 幂最高
        }
        self.RIGHT_ASSOC = {'pow'}

        self.PREFIXABLE_OPS = {
            'add', 'sub', 'mul', 'div', 'mod', 'pow',
            'gt', 'lt', 'eq', 'ne', 'gte', 'lte',
            'not', 'and', 'or', 'digit', 'read'
        }
        self.PREFIXABLE_OPS_SINGLE_ARG = {'read', 'not', 'digit'}

        # 关键字反向映射
        self.KEYWORD_REVERSE = {}
        if self.skin:
            for intern, name in self.skin.skin_data.get('keywords', {}).items():
                self.KEYWORD_REVERSE[name] = intern
        else:
            self.KEYWORD_REVERSE = {
                '设': 'set', '若': 'if', '再若': 'elif', '否则': 'else',
                '循环': 'loop', '遍历': 'for', '定义': 'fn',
                '输出': 'print', '查': 'query', '置': 'write', '读': 'read',
                '加载': 'load', '输入': 'input', '调试': 'debug',
                '等待': 'sleep', '读文件': 'read_file', '写文件': 'write_file',
                '是数字': 'is_number', '是字符串': 'is_string', '字符串相等': 'str_equals',
                'λ': 'lambda', '函数': 'lambda', '尝试': 'try', '捕获': 'catch',
                '返回': 'return', '对': 'context', '应用': 'apply',
                '映射': 'map', '过滤': 'filter', '归并': 'reduce',
                '判': 'judge', '随机态': 'random_state', '随机数': 'random',
                '绝对值': 'abs', '最大值': 'max', '最小值': 'min', '平方根': 'sqrt',
                '连接': 'concat', '取长': 'length',
                '列表': 'list', '列表合': 'list_concat', '表长': 'list_len', '字列': 'str_to_list',
                '数组': 'array', '组长': 'array_len', '数组列': 'array_to_list',
                '取': 'get', '置元素': 'set_element',
                '字典': 'dict', '取键': 'get_key', '置键': 'set_key',
                '同': 'same', '取位': 'digit', '当前时间': 'time',
                '做': 'do',
                '跳出': 'break'
            }

    def _err(self, msg):
        start = max(0, self.pos - 2)
        end = min(len(self.tokens), self.pos + 3)
        ctx = ' '.join(self.tokens[start:end])
        return SyntaxError(f"{msg} （位置 {self.pos}，上下文: '{ctx}'）")

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self, expected=None):
        if self.pos >= len(self.tokens):
            if expected:
                raise self._err(f"期待 {expected}，但已到结尾")
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
        return ['do'] + stmts if len(stmts) > 1 else (stmts[0] if stmts else [])

    def parse_statement(self):
        tok = self.peek()
        if tok is None:
            return None
        # 单独分号视为空语句，跳过
        if tok == ';':
            self.consume(';')
            return None
        if tok == '尝试':
            return self.parse_try()
        internal = self.KEYWORD_REVERSE.get(tok)
        if internal:
            if internal == 'if': return self.parse_if()
            if internal == 'loop': return self.parse_loop()
            if internal == 'for': return self.parse_traversal()
            if internal == 'fn': return self.parse_definition()
            if internal == 'do': return self.parse_do_block()
            if internal == 'try': return self.parse_try()
            if internal == 'judge': return self.parse_judge()
        if tok in ('否则', '再若'):
            raise self._err(f"{tok} 不能单独作为语句，需跟在「若」之后")
        stmt = self.parse_simple_statement()
        if self.peek() == ';':
            self.consume(';')
        return stmt

    def parse_simple_statement(self):
        tok = self.peek()
        internal = self.KEYWORD_REVERSE.get(tok)
        if internal == 'set':
            self.consume(tok)
            var = self.consume()
            if not self._is_ident(var) or var[0].isdigit():
                raise self._err(f"非法变量名: {var}")
            if self.peek() == '=':
                self.consume('=')
                value = self.parse_expression()
                return ['set', var, value]
            raise self._err("设定语句格式: 变量 = 表达式")
        elif internal == 'print':
            self.consume(tok)
            self.consume('(')
            expr = self.parse_expression()
            self.consume(')')
            return ['print', expr]
        elif internal == 'query':
            self.consume(tok)
            return ['query', self.parse_expression()]
        elif internal == 'write':
            self.consume(tok)
            if self.peek() == '(':
                return self.parse_set_batch()
            obj = self.parse_expression()
            if isinstance(obj, str) and '.' in obj:
                return ['write', obj]
            elif self.peek() == '=':
                self.consume('=')
                return ['write', obj, self.parse_expression()]
            raise self._err("置 语句格式: 对象.状态 或 对象 = 状态")
        elif internal == 'read':
            self.consume(tok)
            return ['read', self.consume()]
        elif internal == 'load':
            self.consume(tok)
            return ['load', self.parse_expression()]
        elif internal == 'input':
            self.consume(tok)
            self.consume('(')
            prompt = self.parse_expression() if self.peek() != ')' else None
            self.consume(')')
            return ['input', prompt] if prompt else ['input']
        elif internal == 'debug':
            self.consume(tok)
            args = []
            if self.peek() == '(':
                self.consume('(')
                while self.peek() != ')':
                    args.append(self.parse_expression())
                    if self.peek() == ',': self.consume(',')
                self.consume(')')
            return ['debug'] + args
        elif internal == 'sleep':
            self.consume(tok)
            self.consume('(')
            sec = self.parse_expression()
            self.consume(')')
            return ['sleep', sec]
        elif internal == 'read_file':
            self.consume(tok)
            self.consume('(')
            path = self.parse_expression()
            self.consume(')')
            return ['read_file', path]
        elif internal == 'write_file':
            self.consume(tok)
            self.consume('(')
            path = self.parse_expression()
            self.consume(',')
            content = self.parse_expression()
            self.consume(')')
            return ['write_file', path, content]
        elif internal == 'is_number':
            self.consume(tok)
            self.consume('(')
            val = self.parse_expression()
            self.consume(')')
            return ['is_number', val]
        elif internal == 'is_string':
            self.consume(tok)
            self.consume('(')
            val = self.parse_expression()
            self.consume(')')
            return ['is_string', val]
        elif internal == 'str_equals':
            self.consume(tok)
            self.consume('(')
            a = self.parse_expression()
            self.consume(',')
            b = self.parse_expression()
            self.consume(')')
            return ['str_equals', a, b]
        elif internal == 'lambda':
            self.consume(tok)
            self.consume('(')
            params = []
            while self.peek() != ')':
                params.append(self.consume())
                if self.peek() == ',':
                    self.consume(',')
            self.consume(')')
            body = self.parse_block()
            return ['lambda', params] + body
        elif internal == 'break':
            self.consume(tok)
            return ['break']
        elif internal == 'break':
            self.consume(tok)
            return ['break']
        elif internal == 'return':
            self.consume(tok)
            expr = self.parse_expression()
            return ['return', expr]
        elif internal == 'context':
            self.consume(tok)
            obj = self.parse_expression()
            body = self.parse_block()
            return ['context', obj] + body
        elif internal == 'try':
            return self.parse_try()
        else:
            # 连续赋值 或 表达式/函数调用
            if self.pos + 2 < len(self.tokens) and self.tokens[self.pos+1] == '=':
                var = self.consume()
                if not self._is_ident(var) or var[0].isdigit():
                    raise self._err(f"非法变量名: {var}")
                self.consume('=')
                value = self.parse_expression()
                return ['set', var, value]
            if isinstance(tok, str) and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1] == '(':
                func = self.consume()
                self.consume('(')
                args = []
                while self.peek() != ')':
                    args.append(self.parse_expression())
                    if self.peek() == ',':
                        self.consume(',')
                self.consume(')')
                return [func] + args
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
        return ['write', items]

    def parse_expression(self, min_prec=0):
        lhs = self.parse_primary()
        while True:
            op = self.peek()
            if op is None: break
            internal_op = self.OP_MAP.get(op)
            if internal_op is None or internal_op not in self.PREC:
                break
            prec = self.PREC[internal_op]
            if prec < min_prec:
                break
            next_min = prec + (0 if internal_op in self.RIGHT_ASSOC else 1)
            self.consume(op)
            rhs = self.parse_expression(next_min)
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
        if tok and tok[0] in ('"', '\u201c', '\u2018') and len(tok) >= 2:
            self.consume()
            return tok[1:-1]
        if isinstance(tok, str) and tok.startswith('原文{') and tok.endswith('}'):
            self.consume()
            return tok[3:-1]
        if tok.isdigit() or (tok.startswith('-') and tok[1:].isdigit()):
            self.consume()
            return int(tok)

        if self._is_ident(tok):
            internal = self.KEYWORD_REVERSE.get(tok)
            if internal == 'lambda':
                if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1] == '(':
                    self.consume(tok)
                    self.consume('(')
                    params = []
                    while self.peek() != ')':
                        params.append(self.consume())
                        if self.peek() in (',', '，'):
                            self.consume()
                    self.consume(')')
                    body = self.parse_block()
                    return ['lambda', params] + body
            saved_tok = tok
            self.consume()
            # 如果是关键字命令，转换为内部标识符，以便正确生成 AST
            internal_saved = self.KEYWORD_REVERSE.get(saved_tok, saved_tok)

            # 函数调用形式：标识符后跟 '(' 或 '（'
            if self.peek() in ('(', '（'):
                func = internal_saved          # 使用内部标识
                self.consume()
                args = []
                while self.peek() not in (')', '）'):
                    args.append(self.parse_expression())
                    if self.peek() in (',', '，'):
                        self.consume()
                self.consume()
                return [func] + args

            # 前缀操作符（如读、非、取位等）
            if internal_saved in self.PREFIXABLE_OPS or self.OP_MAP.get(internal_saved) in self.PREFIXABLE_OPS:
                internal_op = internal_saved
                args = []
                if internal_op in self.PREFIXABLE_OPS_SINGLE_ARG:
                    # 一元前缀：取下一个任意 token 作为参数（空白已在词法阶段跳过）
                    if self.peek() is not None:
                        args.append(self.parse_primary())
                else:
                    while (self.peek() is not None and
                           self.peek() not in (';', '}', ')', '）', ',', '，') and
                           self.OP_MAP.get(self.peek()) not in self.PREC):
                        args.append(self.parse_primary())
                if args:
                    return [internal_op] + args
                else:
                    return internal_op   # 无参数时返回操作符本身（例如单独的 `非`）

            # 普通标识符（变量名或未识别的字符串）
            return saved_tok
        raise self._err(f"未知的表达式元素: {tok}")

    def parse_block(self):
        self.consume('{')
        stmts = []
        while self.peek() != '}':
            stmt = self.parse_statement()
            if stmt is not None:   # 忽略空语句（单独分号）
                stmts.append(stmt)
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
                    return ['if', cond, ['do'] + true_body,
                            ['if', elif_cond, ['do'] + elif_body, self._parse_elif_tail()]]
                else:
                    false_body = self.parse_block()
                    return ['if', cond, ['do'] + true_body, ['do'] + false_body]
            elif nxt == '再若':
                self.consume('再若')
                self.consume('(')
                elif_cond = self.parse_expression()
                self.consume(')')
                elif_body = self.parse_block()
                false_part = self._parse_elif_tail()
                if false_part is not None:
                    return ['if', cond, ['do'] + true_body,
                            ['if', elif_cond, ['do'] + elif_body, false_part]]
                else:
                    return ['if', cond, ['do'] + true_body,
                            ['if', elif_cond, ['do'] + elif_body]]
            else:
                return ['if', cond, ['do'] + true_body]

    def parse_try(self):
        self.consume('尝试')
        try_body = self.parse_block()
        self.consume('捕获')
        self.consume('(')
        error_var = self.consume()
        self.consume(')')
        catch_body = self.parse_block()
        return ['try', ['do'] + try_body, ['catch', error_var] + catch_body]

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
                        return ['if', cond, ['do'] + body, self._parse_elif_tail()]
                    else:
                        false_body = self.parse_block()
                        return ['do'] + false_body
                elif nxt == '再若':
                    self.consume('再若')
                    self.consume('(')
                    cond = self.parse_expression()
                    self.consume(')')
                    body = self.parse_block()
                    false_part = self._parse_elif_tail()
                    if false_part is not None:
                        return ['if', cond, ['do'] + body, false_part]
                    else:
                        return ['if', cond, ['do'] + body]
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
        return ['loop', cond] + body

    def parse_traversal(self):
        self.consume('遍历')       # 消耗 '遍历'（中文或英文皮肤的关键字）
        var = self.consume()
        # 消耗 '从' 关键字，如果存在
        if self.peek() == '从':
            self.consume('从')
        # 如果皮肤改变了关键字，可能没有 '从'；此时假设之后直接是起始表达式
        start = self.parse_expression()
        # 消耗 '到' 关键字，如果存在
        if self.peek() == '到':
            self.consume('到')
        end = self.parse_expression()
        body = self.parse_block()
        return ['for', var, start, end] + body

    def parse_definition(self):
        self.consume('定义')
        name = self.consume()
        self.consume('(')
        params = []
        while self.peek() != ')':
            params.append(self.consume())
            if self.peek() == ',':
                self.consume(',')
        self.consume(')')
        body = self.parse_block()
        return ['fn', name, params] + body

    def parse_do_block(self):
        self.consume('做')
        return ['do'] + self.parse_block()

    def parse_judge(self):
        self.consume()   # 消耗 '判' 或皮肤对应的关键字
        expr = self.parse_expression()
        self.consume('{')
        bodies = {'真': None, '可能': None, '假': None}
        while self.peek() != '}':
            tag = self.consume()
            if tag not in bodies:
                raise self._err(f"判 分支必须是 真/可能/假，但得到 {tag}")
            body = self.parse_block()
            bodies[tag] = body
        self.consume('}')
        true_body = ['do'] + (bodies['真'] if bodies['真'] else [])
        maybe_body = ['do'] + (bodies['可能'] if bodies['可能'] else [])
        false_body = ['do'] + (bodies['假'] if bodies['假'] else [])
        return ['judge', expr, true_body, maybe_body, false_body]