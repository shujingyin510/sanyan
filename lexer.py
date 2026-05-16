"""词法分析器：将源代码字符串切割成 token 列表"""
from runtime import BUILTIN_OPS

KEYWORDS = BUILTIN_OPS

def tokenize(code: str) -> list:
    tokens: list = []
    current = ''
    i = 0
    while i < len(code):
        c = code[i]
        if c == '（':
            if current: tokens.append(current); current = ''
            tokens.append('(')
            i += 1; continue
        if c == '）':
            if current: tokens.append(current); current = ''
            tokens.append(')')
            i += 1; continue
        if c == '：':
            obj = current if current else (tokens[-1] if tokens and tokens[-1] not in ('(', ')', '.') else '')
            current = ''
            i += 1
            while i < len(code) and code[i] in (' ', '\t'):
                i += 1
            if obj in KEYWORDS:
                tokens.append(obj)
                continue
            attr = ''
            while i < len(code) and code[i] not in (' ', '\n', '\t', '\u3000', '（', '）', '：', '，', '\uff1b', '(', ')', '"', '\u201c', '\u201d', '\u2018', '\u2019'):
                attr += code[i]; i += 1
            if obj and attr: tokens.append(obj + '.' + attr)
            elif attr: tokens.append(attr)
            continue
        if c in ('，', '\uff1b'):
            if current: tokens.append(current); current = ''
            i += 1; continue
        if c in ('"', '\u201c', '\u2018'):
            if current: tokens.append(current); current = ''
            quote = c
            end_quote = '"' if quote == '"' else ('\u201d' if quote == '\u201c' else '\u2019')
            j = i + 1
            while j < len(code) and code[j] != end_quote:
                if code[j] == '\\': j += 1
                j += 1
            if j < len(code): j += 1
            tokens.append(code[i:j])
            i = j
            continue
        if c in ('(', ')'):
            if current: tokens.append(current); current = ''
            tokens.append(c)
        elif c in (' ', '\n', '\t', '\u3000'):
            if current: tokens.append(current); current = ''
        elif c == '.':
            if current: current += c
            else: current = c
        else:
            current += c
        i += 1
    if current: tokens.append(current)
    return tokens
