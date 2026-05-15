"""糖语法转换器：类 C 语法 -> S-表达式 AST"""
from preprocess import preprocess_includes

class SugarConverter:
    @staticmethod
    def tokenize(code: str, skin_mgr=None):
        fullwidth_map = {
            '（': '(', '）': ')', '｛': '{', '｝': '}', '［': '[', '］': ']',
            '＝': '=', '＞': '>', '＜': '<', '＋': '+', '－': '-', '＊': '*', '／': '/',
            '％': '%', '＾': '^', '，': ',', '；': ';', '：': ':', '！': '!',
            '　': ' ', # 全角空格
        }
        fullwidth_digits = {
            '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
            '５': '5', '６': '6', '７': '7', '８': '8', '９': '9'
        }

        tokens = []
        i = 0
        length = len(code)

        while i < length:
            c = code[i]

            # 1. Skip whitespace
            if c in (' ', '\t', '\n', '\r'):
                i += 1
                continue

            # 2. Comments
            if (c == '/' or c == '／') and i+1 < length and (code[i+1] == '/' or code[i+1] == '／'):
                i += 2
                while i < length and code[i] != '\n': i += 1
                continue
            if c == '#':
                i += 1
                while i < length and code[i] != '\n': i += 1
                continue

            # 3. String literals
            if c in ('"', "'", '“', '‘', '「', '『'):
                quote = c
                end_map = {'"': '"', "'": "'", '“': '”', '‘': '’', '「': '」', '『': '』'}
                end_quote = end_map[quote]
                j = i + 1
                while j < length and code[j] != end_quote:
                    if code[j] == '\\': j += 1
                    j += 1
                if j < length:
                    tokens.append(f'"{code[i+1:j]}"')
                    i = j + 1
                else:
                    tokens.append(f'"{code[i+1:]}"')
                    i = length
                continue

            # 4. Numbers (must be before identifiers and symbols to catch . in 0.5)
            is_neg_num = (c == '-' and i+1 < length and (code[i+1].isdigit() or code[i+1] in fullwidth_digits))
            if c.isdigit() or c in fullwidth_digits or is_neg_num:
                start = i
                if is_neg_num: i += 1
                while i < length and (code[i].isdigit() or code[i] in fullwidth_digits or code[i] == '.'):
                    i += 1
                raw = code[start:i]
                normalized = ''.join(fullwidth_digits.get(ch, ch) for ch in raw)
                tokens.append(normalized)
                continue

            # 5. Fullwidth dot
            if c == '。': c = '.'

            # 6. Multi-character operators
            if i+1 < length:
                next_c = code[i+1]
                next_c = fullwidth_map.get(next_c, next_c)
                combined = c + next_c if c not in fullwidth_map else fullwidth_map[c] + next_c
                if combined in ('>=', '<=', '==', '!=', '!>', '!<'):
                    tokens.append(combined)
                    i += 2
                    continue

            # 7. Single-character symbols
            if c in fullwidth_map: c = fullwidth_map[c]
            if c in ('{', '}', '(', ')', ';', ',', '=', '>', '<', '+', '-', '*', '/', '%', '^', '.', '[', ']', '!', ':'):
                tokens.append(c)
                i += 1
                continue

            # 8. Identifiers and keywords (including template/raw block)
            if c.isalpha() or c == '_' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf':
                start = i
                while i < length and (code[i].isalnum() or code[i] == '_' or
                                      '\u4e00' <= code[i] <= '\u9fff' or
                                      '\u3400' <= code[i] <= '\u4dbf'):
                    i += 1
                word = code[start:i]

                if word == '原文' and i < length and code[i] == '{':
                    i += 1; b_start = i; braces = 1
                    while i < length and braces > 0:
                        if code[i] == '{': braces += 1
                        elif code[i] == '}': braces -= 1
                        i += 1
                    tokens.append(f'"{code[b_start:i-1]}"')
                    continue
                if word == '模板' and i < length and code[i] == '{':
                    t_tokens, new_i = SugarConverter._parse_template(code, i+1)
                    tokens.extend(t_tokens); i = new_i
                    continue

                tokens.append(word)
                continue

            i += 1

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
            if idx > 0: tokens.append(',')
            if isinstance(part, list):
                tokens.extend(part)
            else:
                tokens.append(f'"{part}"')
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
        code = preprocess_includes(code, add_comment=True)
        tokens = cls.tokenize(code, skin_manager)
        parser = _Parser(tokens, skin_manager, source_code=code)
        return parser.parse_program()

def _is_sanyan_ident(tok):
    if not tok: return False
    if tok[0].isdigit(): return False
    for c in tok:
        if c.isalnum() or c == '_' or c == '.' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf':
            continue
        return False
    return True

class _Parser:
    @staticmethod
    def _is_ident(tok):
        return _is_sanyan_ident(tok)

    def __init__(self, tokens, skin_manager=None, source_code=None):
        self.tokens = tokens
        self.pos = 0
        self.elif_depth = 0
        self.max_elif_depth = 50
        self.skin = skin_manager
        self.source_code = source_code
        self.token_lines = self._compute_token_lines()

        # 基础映射（始终支持英文）
        self.OP_MAP = {
            '>': 'gt', '<': 'lt', '==': 'eq', '!=': 'ne', '>=': 'gte', '<=': 'lte',
            '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'mod', '^': 'pow',
            '!>': 'ngt', '!<': 'nlt',
            'gt': 'gt', 'lt': 'lt', 'eq': 'eq', 'ne': 'ne', 'gte': 'gte', 'lte': 'lte',
            'add': 'add', 'sub': 'sub', 'mul': 'mul', 'div': 'div', 'mod': 'mod', 'pow': 'pow',
            'and': 'and', 'or': 'or', 'not': 'not', 'digit': 'digit',
            'read': 'read', 'import': 'import', 'load': 'load', 'print': 'print', 'count': 'count',
            'abs': 'abs', 'max': 'max', 'min': 'min', 'sqrt': 'sqrt', 'sin': 'sin', 'cos': 'cos', 'tan': 'tan',
            'log': 'log', 'log10': 'log10', 'floor': 'floor', 'ceil': 'ceil', 'round': 'round',
            'to_json': 'to_json', 'from_json': 'from_json'
        }
        self.KEYWORD_MAP = {
            'set': 'set', 'if': 'if', 'elif': 'elif', 'else': 'else',
            'loop': 'loop', 'for': 'for', 'fn': 'fn', 'return': 'return',
            'break': 'break', 'continue': 'continue', 'try': 'try', 'catch': 'catch',
            'judge': 'judge', 'lambda': 'lambda', 'in': 'in', 'import': 'import',
            'print': 'print', 'load': 'load', 'count': 'count', 'context': 'context',
            'write': 'write', 'read': 'read', 'query': 'query'
        }

        # 加上皮肤定义的名称（默认为中文）
        if self.skin:
            for intern, name in self.skin.skin_data.get('operators', {}).items():
                self.OP_MAP[name] = intern
            for intern, name in self.skin.skin_data.get('keywords', {}).items():
                self.KEYWORD_MAP[name] = intern

        # 默认中文映射（确保始终可用）
        default_ops = {
            '大于': 'gt', '小于': 'lt', '等于': 'eq', '不等于': 'ne',
            '大于等于': 'gte', '小于等于': 'lte', '不大于': 'ngt', '不小于': 'nlt',
            '加': 'add', '减': 'sub', '乘': 'mul', '除': 'div', '余': 'mod', '幂': 'pow',
            '且': 'and', '或': 'or', '非': 'not', '取位': 'digit'
        }
        default_kws = {
            '设': 'set', '若': 'if', '再若': 'elif', '否则': 'else',
            '循环': 'loop', '遍历': 'for', '定义': 'fn', '返回': 'return',
            '跳出': 'break', '继续': 'continue', '尝试': 'try', '捕获': 'catch',
            '判': 'judge', '函数': 'lambda', 'λ': 'lambda', '在': 'in',
            '导入': 'import', '输出': 'print', '加载': 'load', '计数': 'count',
            '对': 'context', '置': 'write', '读': 'read', '查': 'query',
            '从': 'from', '到': 'to'
        }
        for k, v in default_ops.items():
            if k not in self.OP_MAP: self.OP_MAP[k] = v
        for k, v in default_kws.items():
            if k not in self.KEYWORD_MAP: self.KEYWORD_MAP[k] = v

        self.PREC = {
            'and': 1, 'or': 1,
            'eq': 2, 'ne': 2, 'gt': 2, 'lt': 2, 'gte': 2, 'lte': 2, 'ngt': 2, 'nlt': 2,
            'add': 3, 'sub': 3,
            'mul': 4, 'div': 4, 'mod': 4,
            'pow': 5,
        }
        self.RIGHT_ASSOC = {'pow'}
        self.PREFIXABLE_OPS = {
            'add', 'sub', 'mul', 'div', 'mod', 'pow',
            'gt', 'lt', 'eq', 'ne', 'gte', 'lte', 'ngt', 'nlt',
            'not', 'and', 'or', 'digit', 'read', 'import', 'load', 'print', 'query'
        }
        self.PREFIXABLE_OPS_SINGLE_ARG = {'read', 'not', 'digit', 'import', 'load', 'print', 'query'}

    def _compute_token_lines(self):
        if not self.source_code: return [1] * len(self.tokens)
        lines = self.source_code.split('\n')
        token_lines = []
        current_line = 1
        line_start_idx = 0
        for tok in self.tokens:
            tok_clean = tok.strip('"')
            while current_line <= len(lines):
                line_content = lines[current_line-1]
                idx = self.source_code.find(tok_clean, line_start_idx)
                if idx != -1 and idx < line_start_idx + len(line_content) + 1:
                    token_lines.append(current_line)
                    line_start_idx = idx + len(tok_clean)
                    break
                else:
                    line_start_idx += len(line_content) + 1
                    current_line += 1
            else:
                token_lines.append(current_line)
        return token_lines

    def peek(self): return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    def consume(self, expected=None):
        tok = self.peek()
        if expected and tok != expected:
            line = self.token_lines[self.pos] if self.pos < len(self.token_lines) else '未知'
            raise SyntaxError(f"行 {line}: 期望 '{expected}'，但得到 '{tok}'")
        self.pos += 1
        return tok

    def parse_program(self):
        stmts = []
        while self.peek():
            stmt = self.parse_statement()
            if stmt: stmts.append(stmt)
        if not stmts: return None
        return ['do'] + stmts if len(stmts) > 1 else stmts[0]

    def parse_statement(self):
        tok = self.peek()
        if not tok: return None
        kw = self.KEYWORD_MAP.get(tok, tok)

        # 裸赋值支持 (变量 = 表达式)
        if self._is_ident(tok) and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1] == '=':
            var_name = self.consume()
            self.consume('=')
            expr = self.parse_expression()
            if self.peek() == ';': self.consume(';')
            return ['set', var_name, expr]

        if kw == 'set':
            self.consume()
            var_name = self.consume()
            self.consume('=')
            expr = self.parse_expression()
            if self.peek() == ';': self.consume(';')
            return ['set', var_name, expr]
        elif kw == 'write':
            self.consume() # consume '置'
            target = self.consume()
            self.consume('=')
            value = self.parse_expression()
            if self.peek() == ';': self.consume(';')
            return ['write', target, value]
        elif kw == 'if':
            return self.parse_if()
        elif kw == 'loop':
            self.consume()
            cond = self.parse_expression()
            body = self.parse_block()
            return ['loop', cond, body]
        elif kw == 'for':
            self.consume() # consume '遍历'
            var = self.consume()
            next_tok = self.peek()
            next_kw = self.KEYWORD_MAP.get(next_tok, next_tok)
            if next_kw == 'from':
                self.consume() # consume '从'
                start_val = self.parse_expression()
                if self.KEYWORD_MAP.get(self.peek()) == 'to':
                    self.consume() # consume '到'
                end_val = self.parse_expression()
                body = self.parse_block()
                return ['for', var, start_val, end_val, body]
            else:
                if next_kw == 'in':
                    self.consume() # consume '在'
                lst = self.parse_expression()
                body = self.parse_block()
                return ['forin', var, lst, body]
        elif kw == 'fn':
            self.consume()
            name = self.consume()
            params = []
            if self.peek() == '(':
                self.consume('(')
                while self.peek() and self.peek() != ')':
                    p = self.consume()
                    # 跳过类型标注 : 类型
                    if self.peek() == ':':
                        self.consume(':')
                        self.consume()
                    params.append(p)
                    if self.peek() == ',': self.consume(',')
                self.consume(')')
            body = self.parse_block()
            return ['fn', name, params, body]
        elif kw == 'return':
            self.consume(); expr = self.parse_expression()
            if self.peek() == ';': self.consume(';')
            return ['return', expr]
        elif kw == 'break':
            self.consume()
            if self.peek() == ';': self.consume(';')
            return ['break']
        elif kw == 'continue':
            self.consume()
            if self.peek() == ';': self.consume(';')
            return ['continue']
        elif kw == 'try':
            self.consume(); try_body = self.parse_block()
            self.consume() # consume '捕获'
            err_var = '_'
            if self.peek() == '(':
                self.consume('('); err_var = self.consume(); self.consume(')')
            catch_body = self.parse_block()
            # 修正为 ControlOps 期望的结构: ['try', try_body, ['捕获', err_var, catch_body]]
            # 注意这里必须匹配 ControlOps.try_catch 中的 catch_spec[0]
            if not isinstance(catch_body, list) or (isinstance(catch_body, list) and len(catch_body) > 0 and catch_body[0] != 'do'):
                catch_body_list = [catch_body]
            else:
                # 如果已经是 do 块，提取内容
                catch_body_list = catch_body[1:] if isinstance(catch_body, list) and len(catch_body) > 0 and catch_body[0] == 'do' else [catch_body]

            return ['try', try_body, ['捕获', err_var] + catch_body_list]


        elif kw == 'judge':
            self.consume(); val = self.parse_expression(); self.consume('{')
            cases = []
            while self.peek() and self.peek() != '}':
                cases.append(self.parse_expression()); cases.append(self.parse_block())
            self.consume('}')
            return ['judge', val] + cases
        else:
            expr = self.parse_expression()
            if self.peek() == ';': self.consume(';')
            return expr

    def parse_if(self):
        self.consume() # if/elif
        cond = self.parse_expression()
        then_body = self.parse_block()
        else_body = None
        if self.peek() and self.KEYWORD_MAP.get(self.peek()) == 'elif':
            self.elif_depth += 1
            if self.elif_depth > self.max_elif_depth: raise SyntaxError("elif 嵌套过深")
            else_body = self.parse_if()
            self.elif_depth -= 1
        elif self.peek() and self.KEYWORD_MAP.get(self.peek()) == 'else':
            self.consume(); else_body = self.parse_block()
        return ['if', cond, then_body, else_body] if else_body else ['if', cond, then_body]

    def parse_block(self):
        if self.peek() == '{':
            self.consume('{')
            stmts = []
            while self.peek() and self.peek() != '}':
                s = self.parse_statement()
                if s: stmts.append(s)
            self.consume('}')
            return ['do'] + stmts if len(stmts) != 1 else stmts[0]
        else:
            return self.parse_statement()

    def parse_expression(self, precedence=0):
        left = self.parse_primary()
        while True:
            tok = self.peek()
            if not tok: break
            op = self.OP_MAP.get(tok)
            if not op or op not in self.PREC or self.PREC[op] < precedence: break
            self.consume()
            next_prec = self.PREC[op] + (0 if op in self.RIGHT_ASSOC else 1)
            right = self.parse_expression(next_prec)
            left = [op, left, right]
        return left

    def parse_primary(self):
        tok = self.consume()
        if tok == '(':
            expr = self.parse_expression(); self.consume(')')
            return expr

        # 处理点号属性访问 (如 test.断言相等)
        if self.peek() == '.':
            self.consume('.')
            attr = self.consume()
            # 转换为 (get test "断言相等") 或 (test "断言相等")
            # 核心 Evaluator 处理 dot notation。这里我们生成 ['test.attr']
            return f"{tok}.{attr}"

        if tok == '[':
            saved_pos = self.pos
            # 尝试解析列表推导式: [expr 遍历 var 在 lst [若 cond]]
            try:
                inner_expr = self.parse_expression()
            except SyntaxError:
                inner_expr = None
            if inner_expr is not None and self.peek() and self.KEYWORD_MAP.get(self.peek()) == 'for':
                self.consume() # consume '遍历'
                var = self.consume()
                if self.KEYWORD_MAP.get(self.peek()) == 'in': self.consume()
                lst = self.parse_expression()
                cond = None
                if self.KEYWORD_MAP.get(self.peek()) == 'if':
                    self.consume()
                    cond = self.parse_expression()
                self.consume(']')
                filter_node = ['filter', ['lambda', [var], cond], lst] if cond else lst
                return ['map', ['lambda', [var], [inner_expr]], filter_node]
            # 不是推导式，回退并解析普通列表
            self.pos = saved_pos

            items = []
            while self.peek() and self.peek() != ']':
                items.append(self.parse_expression())
                if self.peek() == ',': self.consume(',')
            self.consume(']')
            return ['list'] + items

        kw = self.KEYWORD_MAP.get(tok, self.OP_MAP.get(tok, tok))
        if kw in self.PREFIXABLE_OPS:
            if kw in self.PREFIXABLE_OPS_SINGLE_ARG:
                return [kw, self.parse_expression(10)]
            self.consume('(')
            args = []
            while self.peek() and self.peek() != ')':
                args.append(self.parse_expression())
                if self.peek() == ',': self.consume(',')
            self.consume(')')
            return [kw] + args

        if kw == 'lambda':
            self.consume('(')
            params = []
            while self.peek() and self.peek() != ')':
                p = self.consume()
                # 跳过类型标注 : 类型
                if self.peek() == ':':
                    self.consume(':')
                    self.consume()
                params.append(p)
                if self.peek() == ',': self.consume(',')
            self.consume(')')
            body = self.parse_block()
            return ['lambda', params, body]

        if tok.startswith('"'): return tok
        if tok.replace('.', '', 1).isdigit() or (tok.startswith('-') and tok[1:].replace('.', '', 1).isdigit()):
            return tok

        if self.peek() == '(':
            self.consume('(')
            args = []
            while self.peek() and self.peek() != ')':
                args.append(self.parse_expression())
                if self.peek() == ',': self.consume(',')
            self.consume(')')
            return [tok] + args
        if self.peek() == '[':
            self.consume('['); idx = self.parse_expression(); self.consume(']')
            return ['get', tok, idx]
        return tok
