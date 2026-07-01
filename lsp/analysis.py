from __future__ import annotations
import re
from typing import Any, Optional
from core.ternary_core import TritValue

from lsp.keywords import _ALL_KEYWORDS, _FUNC_SIGS, _TYPED_HOVER, _MATH_FUNCS

# --- 源码分析 ---


def _extract_docstrings(text: str) -> dict[str, str]:
    docs: dict[str, str] = {}
    pattern = re.compile(
        r'((?:(?://|／／)[^\n]*\n?\s*)*)'
        r'(?:定义|fn)\s+(\S+)\s*'
        r'\(([^)]*)\)'
    )
    for m in pattern.finditer(text):
        raw = m.group(1)
        name = m.group(2)
        params_sig = m.group(3)
        sig_parts = []
        for p in params_sig.split(','):
            p = p.strip()
            if p:
                sig_parts.append(p)
        sig = f'定义 {name}({", ".join(sig_parts)})'
        lines = [f'`{sig}`']
        for line in raw.split('\n'):
            line = line.strip()
            if line.startswith('//'):
                lines.append(line[2:].strip())
            elif line.startswith('／／'):
                lines.append(line[2:].strip())
        docs[name] = '\n'.join(lines)
    return docs


def _extract_definitions(text: str) -> dict[str, dict]:
    defs: dict[str, dict] = {}
    for i, line in enumerate(text.split('\n')):
        m = re.search(r'(定义|fn)\s+(\S+)\s*\(', line)
        if m:
            col = m.start(2)
            defs[m.group(2)] = {'line': i, 'col': col, 'kind': 'function'}
        m = re.search(r'(?:设|set)\s+(\S+)\s*=', line)
        if m:
            col = m.start(1)
            defs[m.group(1)] = {'line': i, 'col': col, 'kind': 'variable'}
    return defs


def _extract_symbols_for_document(text: str) -> list[dict]:
    symbols: list[dict] = []
    defs = _extract_definitions(text)
    for name, info in defs.items():
        kind = 12 if info['kind'] == 'function' else 13
        line_idx = info['line']
        lines = text.split('\n')
        end_line = line_idx
        if info['kind'] == 'function':
            brace_count = 0
            started = False
            for j in range(line_idx, len(lines)):
                line = lines[j]
                for ch in line:
                    if ch in ('{', '｛'):
                        started = True
                        brace_count += 1
                    elif ch in ('}', '｝'):
                        if started:
                            brace_count -= 1
                            if brace_count == 0:
                                end_line = j
                                break
                if brace_count == 0 and started:
                    break
        symbols.append(
            {
                'name': name,
                'kind': kind,
                'range': {
                    'start': {'line': line_idx, 'character': 0},
                    'end': {'line': end_line, 'character': len(lines[end_line])},
                },
                'selectionRange': {
                    'start': {'line': line_idx, 'character': info['col']},
                    'end': {'line': line_idx, 'character': info['col'] + len(name)},
                },
            }
        )
    return symbols


def _do_folding_ranges(text: str) -> list[dict]:
    ranges: list[dict] = []
    lines = text.split('\n')
    stack: list[int] = []
    opens = {'{', '｛'}
    closes = {'}', '｝'}
    for ln, line in enumerate(lines):
        for ch in line:
            if ch in opens:
                stack.append(ln)
            elif ch in closes and stack:
                start = stack.pop()
                if ln > start:
                    ranges.append(
                        {
                            'startLine': start,
                            'endLine': ln,
                        }
                    )
    return ranges


def _do_references(text: str, pos: dict, uri: str) -> Optional[list[dict]]:
    lines = text.split('\n')
    if pos['line'] >= len(lines):
        return None
    line = lines[pos['line']]
    col = pos['character']
    start = col
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] in '_\u4e00-\u9fff'):
        start -= 1
    end = col
    while end < len(line) and (line[end].isalnum() or line[end] in '_\u4e00-\u9fff'):
        end += 1
    word = line[start:end]
    if not word:
        return None

    refs: list[dict] = []
    for ln, line_text in enumerate(lines):
        idx = 0
        while True:
            idx = line_text.find(word, idx)
            if idx < 0:
                break
            before_ok = idx == 0 or not (line_text[idx - 1].isalnum() or line_text[idx - 1] in '_\u4e00-\u9fff')
            after_ok = idx + len(word) >= len(line_text) or not (
                line_text[idx + len(word)].isalnum() or line_text[idx + len(word)] in '_\u4e00-\u9fff'
            )
            if before_ok and after_ok:
                refs.append(
                    {
                        'uri': uri,
                        'range': {
                            'start': {'line': ln, 'character': idx},
                            'end': {'line': ln, 'character': idx + len(word)},
                        },
                    }
                )
            idx += len(word)
    return refs if refs else None


def _do_rename(text: str, pos: dict, new_name: str, uri: str) -> Optional[dict]:
    refs = _do_references(text, pos, uri)
    if not refs:
        return None
    return {
        'changes': {
            uri: [
                {
                    'range': r['range'],
                    'newText': new_name,
                }
                for r in refs
            ],
        },
    }


def _do_prepare_rename(text: str, pos: dict, uri: str) -> Optional[dict]:
    lines = text.split('\n')
    if pos['line'] >= len(lines):
        return None
    line = lines[pos['line']]
    col = pos['character']
    start = col
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] in '_\u4e00-\u9fff'):
        start -= 1
    end = col
    while end < len(line) and (line[end].isalnum() or line[end] in '_\u4e00-\u9fff'):
        end += 1
    word = line[start:end]
    if not word:
        return None
    return {
        'range': {
            'start': {'line': pos['line'], 'character': start},
            'end': {'line': pos['line'], 'character': end},
        },
        'placeholder': word,
    }


def _extract_variables(text: str) -> list[str]:
    vars_found: set[str] = set()
    for line in text.split('\n'):
        m = re.search(r'(?:设|set)\s+(\S+)', line)
        if m:
            vars_found.add(m.group(1))
        m = re.search(r'(?:定义|fn)\s+(\S+)', line)
        if m:
            vars_found.add(m.group(1))
    return sorted(vars_found)


def _do_definition(text: str, pos: dict, uri: str = '') -> Optional[list[dict]]:
    lines = text.split('\n')
    if pos['line'] >= len(lines):
        return None
    line = lines[pos['line']]
    col = pos['character']
    start = col
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] in '_\u4e00-\u9fff'):
        start -= 1
    end = col
    while end < len(line) and (line[end].isalnum() or line[end] in '_\u4e00-\u9fff'):
        end += 1
    word = line[start:end]
    if not word:
        return None
    defs = _extract_definitions(text)
    if word in defs:
        info = defs[word]
        return [
            {
                'uri': uri,
                'range': {
                    'start': {'line': info['line'], 'character': info.get('col', 0)},
                    'end': {'line': info['line'], 'character': info.get('col', 0) + len(word)},
                },
            }
        ]
    return None


_open_doc_uri: str = ''


def _do_signature_help(text: str, pos: dict) -> Optional[dict]:
    lines = text.split('\n')
    if pos['line'] >= len(lines):
        return None
    line = lines[pos['line']][: pos['character']]
    paren = line.rfind('(')
    if paren < 0:
        return None
    func_name = ''
    i = paren - 1
    while i >= 0 and (line[i].isalnum() or line[i] in '_\u4e00-\u9fff\u3400-\u4dbf'):
        func_name = line[i] + func_name
        i -= 1
    if not func_name or func_name not in _FUNC_SIGS:
        return None
    sig = _FUNC_SIGS[func_name]
    return {
        'signatures': [
            {
                'label': sig,
                'parameters': [],
            }
        ]
    }


def _list_to_completion(items: list[str], kind: int = 14) -> list[dict[str, Any]]:
    return [{'label': i, 'kind': kind} for i in sorted(items)]


def _do_diagnostics(uri: str, text: str) -> list[dict]:
    diagnostics: list[dict] = []
    lines = text.split('\n')
    stack: list[tuple[int, int]] = []
    pairs = {')': '(', '）': '（', '}': '{', '｝': '｛'}
    opens = {'(', '（', '{', '｛'}
    for ln, line in enumerate(lines):
        for cn, ch in enumerate(line):
            if ch in opens:
                stack.append((ln, cn))
            elif ch in pairs:
                if stack and stack[-1][0] == ln:
                    stack.pop()
                elif stack:
                    diagnostics.append(
                        {
                            'range': {
                                'start': {'line': ln, 'character': cn},
                                'end': {'line': ln, 'character': cn + 1},
                            },
                            'severity': 1,
                            'message': f"不匹配的括号 '{ch}'，期望 '{pairs[ch]}'",
                        }
                    )
    for ln, cn in stack:
        diagnostics.append(
            {
                'range': {
                    'start': {'line': ln, 'character': cn},
                    'end': {'line': ln, 'character': cn + 1},
                },
                'severity': 1,
                'message': '未闭合的括号',
            }
        )

    duplicate_pattern = re.compile(r'(?:定义|fn)\s+\S+\s*\(([^)]+)\)')
    for ln, line in enumerate(lines):
        m = duplicate_pattern.search(line)
        if m:
            params = [p.strip().split(':')[0].strip() for p in m.group(1).split(',')]
            seen: set[str] = set()
            for p in params:
                if p and p in seen:
                    diagnostics.append(
                        {
                            'range': {
                                'start': {'line': ln, 'character': 0},
                                'end': {'line': ln, 'character': len(line)},
                            },
                            'severity': 2,
                            'message': f"重复的参数名: '{p}'",
                        }
                    )
                    break
                seen.add(p)

    try:
        from sugar import SugarConverter
        from core.skin import SkinManager

        skin_mgr = SkinManager('chinese')
        ast = SugarConverter.convert(text, skin_mgr)
        if ast:
            _check_undefined(ast, text, diagnostics)
            _check_unused_vars(ast, text, diagnostics)
    except SyntaxError:
        pass

    return diagnostics


def _check_undefined(ast: list, text: str, diagnostics: list, defined: set[str] | None = None):
    if defined is None:
        defined = set()
        _collect_defs(ast, defined)
        for line in text.split('\n'):
            m = re.search(r'(?:设|set)\s+(\S+)', line)
            if m:
                defined.add(m.group(1))
            m = re.search(r'(?:定义|fn)\s+(\S+)', line)
            if m:
                defined.add(m.group(1))
            m = re.search(r'(?:捕获|catch)\s*\n\s*\(?\s*(\S+)', line)
            if m:
                defined.add(m.group(1))
            m = re.search(r'(?:遍历|for)\s+(\S+)\s+(?:从|在|from|in)', line)
            if m:
                defined.add(m.group(1))
        defined |= {'真', '假', '可能', 'true', 'false', 'maybe', '+', '-', '0'}
    _walk_undef(ast, defined, diagnostics)


def _collect_defs(node, defined):
    if not isinstance(node, list) or len(node) == 0:
        return
    first = node[0]
    if first in ('fn', '定义') and len(node) >= 3 and isinstance(node[2], list):
        for p in node[2]:
            if isinstance(p, str):
                defined.add(p)
    elif first in ('catch', '捕获') and len(node) >= 2 and isinstance(node[1], str):
        defined.add(node[1])
    elif first in ('set', '设') and len(node) >= 2 and isinstance(node[1], str):
        defined.add(node[1])
    elif first in ('for', 'forin', '遍历') and len(node) >= 2 and isinstance(node[1], str):
        defined.add(node[1])
    for child in node[1:]:
        _collect_defs(child, defined)


def _walk_undef(node, defined, diagnostics, scope_defined: set | None = None):
    if not isinstance(node, list) or len(node) == 0:
        return
    scoped = set(defined) if scope_defined is None else scope_defined
    first = node[0]
    if first in ('fn', '定义') and len(node) >= 3 and isinstance(node[2], list):
        new_scoped = set(scoped)
        for p in node[2]:
            if isinstance(p, str):
                new_scoped.add(p)
        scoped = new_scoped
    in_list = [first]
    for child in node[1:]:
        if first in ('fn', '定义'):
            break
        in_list.append(child)
        if first in ('catch', '捕获'):
            continue
        if isinstance(child, list):
            _walk_undef(child, scoped, diagnostics, set(scoped))
        elif (
            isinstance(child, str)
            and not child.startswith('"')
            and not child.startswith("'")
            and not child.startswith('\u201c')
            and not child.startswith('\u2018')
            and not child[0].isdigit()
            and child not in ('{', '}', '做')
        ):
            if child in scoped:
                continue
            if child in _ALL_KEYWORDS:
                scoped.add(child)
                continue
            if child in TritValue.STATE_MAP:
                scoped.add(child)
                continue
            if child in _FUNC_SIGS:
                scoped.add(child)
                continue
            if child not in defined and not child.startswith('_'):
                pass
    skip_body = False
    for child in node[1:]:
        if skip_body:
            skip_body = False
            continue
        if isinstance(child, list):
            _walk_undef(child, scoped, diagnostics, set(scoped))


def _check_unused_vars(ast: list, text: str, diagnostics: list):
    defined = {}
    used = set()

    def collect_defs_and_uses(node, defs_dict, uses_set):
        if not isinstance(node, list) or len(node) == 0:
            return
        first = node[0]
        if first in ('set', '设') and len(node) >= 2 and isinstance(node[1], str):
            line_num = getattr(node, 'line', 0) or 0
            if node[1] not in defs_dict:
                defs_dict[node[1]] = line_num
        elif first in ('fn', '定义') and len(node) >= 2 and isinstance(node[1], str):
            line_num = getattr(node, 'line', 0) or 0
            if node[1] not in defs_dict:
                defs_dict[node[1]] = line_num
        elif first in ('lambda', 'λ', '函数') and len(node) >= 2 and isinstance(node[1], list):
            for p in node[1]:
                if isinstance(p, str):
                    uses_set.add(p)
        for child in node[1:]:
            if isinstance(child, list):
                collect_defs_and_uses(child, defs_dict, uses_set)
            elif isinstance(child, str) and child in defs_dict:
                uses_set.add(child)

    collect_defs_and_uses(ast, defined, used)

    for name in list(defined):
        used.add(name)

    unused = [name for name, line in defined.items() if name not in used and not name.startswith('_')]
    for name in unused:
        diagnostics.append(
            {
                'range': {
                    'start': {'line': defined[name], 'character': 0},
                    'end': {'line': defined[name], 'character': len(name)},
                },
                'severity': 2,
                'message': f"未使用的变量或命令: '{name}'",
            }
        )


def _do_formatting(text: str) -> Optional[list[dict]]:
    from sanfmt import format_code
    from sugar import SugarConverter
    from core.skin import SkinManager
    from core.lexer import tokenize
    from core.parser import parse

    skin_mgr = SkinManager('chinese')
    ast = None
    try:
        ast = SugarConverter.convert(text, skin_mgr)
    except SyntaxError:
        pass
    if ast is None:
        tokens = tokenize(text)
        if tokens:
            try:
                ast = parse(tokens)
            except SyntaxError:
                pass
    if ast is None:
        return None

    try:
        formatted = format_code(ast, source=text).rstrip('\n')
    except Exception:
        return None

    if formatted == text.rstrip('\n'):
        return None

    lines = text.split('\n')
    return [
        {
            'range': {
                'start': {'line': 0, 'character': 0},
                'end': {'line': len(lines) - 1, 'character': len(lines[-1])},
            },
            'newText': formatted,
        }
    ]


def _do_completion(text: str, pos: dict) -> Optional[dict]:
    user_defs = _extract_variables(text)
    all_items = list(_ALL_KEYWORDS) + user_defs

    line = text.split('\n')[pos['line']][: pos['character']]
    if not line.strip():
        return {'isIncomplete': False, 'items': _list_to_completion(all_items)}
    prefix = line.split()[-1] if line.split() else ''
    matches = [k for k in all_items if k.startswith(prefix)]
    return {'isIncomplete': False, 'items': _list_to_completion(matches or all_items)}


_docstrings_cache: dict[str, str] = {}
_docstrings_cache_text: str = ''


def _invalidate_docstring_cache(text: str) -> None:
    global _docstrings_cache, _docstrings_cache_text
    if text != _docstrings_cache_text:
        _docstrings_cache = _extract_docstrings(text)
        _docstrings_cache_text = text


def _do_hover(text: str, pos: dict) -> Optional[dict]:
    _invalidate_docstring_cache(text)
    lines = text.split('\n')
    if pos['line'] >= len(lines):
        return None
    line = lines[pos['line']]
    col = pos['character']
    if col >= len(line):
        return None
    start = col
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] in '_{}（）'):
        start -= 1
    end = col
    while end < len(line) and (line[end].isalnum() or line[end] in '_{}（）'):
        end += 1
    word = line[start:end]
    if word in _TYPED_HOVER:
        return {
            'contents': {
                'kind': 'markdown',
                'value': f'**{word}**\n\n{_TYPED_HOVER[word]}',
            }
        }
    if word in _MATH_FUNCS:
        return {
            'contents': {
                'kind': 'markdown',
                'value': f'**{word}** — 数学函数（三进制定点）',
            }
        }
    if word in _docstrings_cache:
        return {
            'contents': {
                'kind': 'markdown',
                'value': f'**{word}**\n\n{_docstrings_cache[word]}',
            }
        }
    return None
