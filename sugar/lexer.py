"""词法分析器：全角映射、token化、行号追踪"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Token:
    kind: str
    value: str
    line: int
    col: int


FULLWIDTH_MAP = {
    '（': '(', '）': ')', '｛': '{', '｝': '}', '［': '[', '］': ']',
    '＝': '=', '＞': '>', '＜': '<', '＋': '+', '－': '-', '＊': '*', '／': '/',
    '％': '%', '＾': '^', '，': ',', '；': ';', '：': ':', '！': '!',
    '　': ' ',
}
FULLWIDTH_DIGITS = {
    '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
    '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
}
SYMBOL_CHARS = frozenset('{ } ( ) ; , = > < + - * / % ^ . [ ] ! :'.split())


STRING_OPEN = set('"\'') | {'\u201c', '\u2018', '\u300c', '\u300e'}
STRING_CLOSE = {
    '"': '"', "'": "'",
    '\u201c': '\u201d', '\u2018': '\u2019',
    '\u300c': '\u300d', '\u300e': '\u300f',
}

def tokenize(code: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    length = len(code)
    line = 1
    col = 1

    while i < length:
        c = code[i]

        # Track line numbers
        if c == '\n':
            line += 1
            col = 1
            i += 1
            continue

        # Skip whitespace
        if c in (' ', '\t', '\r'):
            i += 1
            col += 1
            continue

        # Fullwidth mapping
        if c in FULLWIDTH_MAP:
            c = FULLWIDTH_MAP[c]

        # Fullwidth dot
        if c == '。':
            c = '.'

        # Comments: // or ／／
        if c == '/' and i + 1 < length:
            next_c = code[i + 1]
            if next_c == '/' or next_c == '／':
                i += 2
                col += 2
                while i < length and code[i] != '\n':
                    i += 1
                continue

        # Comments: #
        if c == '#':
            i += 1
            col += 1
            while i < length and code[i] != '\n':
                i += 1
            continue

        # Strings: "..." 、「...」、『...』、'...'
        if c in STRING_OPEN:
            start_col = col
            quote = c
            end_quote = STRING_CLOSE[quote]
            j = i + 1
            while j < length and code[j] != end_quote:
                if code[j] == '\\':
                    j += 1
                j += 1
            if j < length:
                j += 1
            tokens.append(Token('STRING', code[i:j], line, start_col))
            # Update col
            for ch in code[i:j]:
                if ch == '\n':
                    line += 1
                    col = 1
                else:
                    col += 1
            i = j
            continue

        # Numbers
        is_neg_num = (c == '-' and i + 1 < length and code[i + 1].isdigit())
        if c.isdigit() or c in FULLWIDTH_DIGITS or is_neg_num:
            start_col = col
            start = i
            if is_neg_num:
                i += 1
                col += 1
            while i < length and (code[i].isdigit() or code[i] in FULLWIDTH_DIGITS or code[i] == '.'):
                ch = code[i]
                if ch in FULLWIDTH_DIGITS:
                    ch = FULLWIDTH_DIGITS[ch]
                i += 1
                col += 1
            num_str = code[start:i]
            # Convert fullwidth digits and fullwidth symbols
            converted = ''
            for ch in num_str:
                ch = FULLWIDTH_MAP.get(ch, ch)
                converted += FULLWIDTH_DIGITS.get(ch, ch)
            tokens.append(Token('NUMBER', converted, line, start_col))
            continue

        # Multi-character operators: !=, >=, <=, !>, !<
        next_c = code[i + 1] if i + 1 < length else ''
        next_mapped = FULLWIDTH_MAP.get(next_c, next_c)
        if c == '!' and next_mapped in ('=', '>', '<'):
            tokens.append(Token('OP', c + next_mapped, line, col))
            i += 2
            col += 2
            continue
        if c in ('>', '<', '=') and next_mapped == '=':
            tokens.append(Token('OP', c + next_mapped, line, col))
            i += 2
            col += 2
            continue

        # Single-character symbols
        if c in SYMBOL_CHARS:
            tokens.append(Token('SYMBOL', c, line, col))
            i += 1
            col += 1
            continue

        # Words (identifiers/keywords)
        if c.isalnum() or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf' or c == '_':
            start_col = col
            start = i
            while i < length:
                ch = code[i]
                if ch.isalnum() or '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf' or ch in ('_', '.'):
                    i += 1
                    col += 1
                else:
                    break
            word = code[start:i]

            # 原文{...} 块
            if word == '原文' and i < length and code[i] == '{':
                i += 1
                col += 1
                b_start = i
                braces = 1
                while i < length and braces > 0:
                    if code[i] == '{':
                        braces += 1
                    elif code[i] == '}':
                        braces -= 1
                    if code[i] == '\n':
                        line += 1
                        col = 1
                    else:
                        col += 1
                    i += 1
                raw_content = code[b_start:i-1]
                tokens.append(Token('STRING', f'"{raw_content}"', line, start_col))
                continue

            # 模板{...${expr}...} 块
            if word == '模板' and i < length and code[i] == '{':
                t_tokens = _parse_template(code, i, line, col)
                tokens.extend(t_tokens)
                # 跳过到模板结束
                braces = 1
                j = i + 1
                while j < length and braces > 0:
                    if code[j] == '{':
                        braces += 1
                    elif code[j] == '}':
                        braces -= 1
                    if code[j] == '\n':
                        line += 1
                        col = 1
                    else:
                        col += 1
                    j += 1
                i = j
                continue

            tokens.append(Token('WORD', word, line, start_col))
            continue

        # Unknown character - skip
        i += 1
        col += 1

    return tokens


def _parse_template(code: str, pos: int, line: int, col: int) -> list[Token]:
    """解析 模板{text${expr}text} 块，返回 concat(...) 的 tokens。"""
    ptr = pos  # points to '{'
    if ptr < len(code) and code[ptr] == '{':
        ptr += 1
    tokens = [Token('WORD', 'concat', line, col), Token('SYMBOL', '(', line, col)]
    while ptr < len(code):
        ch = code[ptr]
        if ch == '}':
            ptr += 1
            break
        if ch == '$' and ptr + 1 < len(code) and code[ptr + 1] == '{':
            ptr += 2
            expr_start = ptr
            braces = 1
            while ptr < len(code) and braces > 0:
                if code[ptr] == '{':
                    braces += 1
                elif code[ptr] == '}':
                    braces -= 1
                ptr += 1
            var = code[expr_start:ptr-1]
            tokens.append(Token('WORD', var, line, col))
            continue
        # 普通文本
        text_start = ptr
        while ptr < len(code) and code[ptr] != '$' and code[ptr] != '}':
            if code[ptr] == '\\':
                ptr += 1
            ptr += 1
        text = code[text_start:ptr]
        tokens.append(Token('STRING', f'"{text}"', line, col))
    tokens.append(Token('SYMBOL', ')', line, col))
    return tokens
