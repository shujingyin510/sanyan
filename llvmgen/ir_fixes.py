"""LLVM IR 后处理工具。

修复 IR 中的常见问题：缺失终止指令、null-safe 运行时函数、
缺失常量定义、参数 unbox 模式等。
从 compiler.py 拆分而来。
"""

from __future__ import annotations


def _fix_terminators(ir: str) -> str:
    """确保 IR 中每个基本块都有终止指令 (ret/br/unreachable)。"""
    lines = ir.split('\n')
    result = []
    in_block = False
    has_term = True
    terminators = ('ret ', 'br ', 'unreachable', 'resume ', 'switch ', 'indirectbr ', 'callbr ')

    for line in lines:
        stripped = line.strip()
        is_label = (
            stripped
            and stripped.endswith(':')
            and not stripped.startswith(';')
            and not stripped.startswith('"')
            and line[0] not in (' ', '\t')
            and not line.startswith('  ')
        )

        if is_label:
            if in_block and not has_term:
                result.append('  unreachable')
            in_block = True
            has_term = False

        if stripped == '}':
            if in_block and not has_term:
                result.append('  unreachable')
            in_block = False
            has_term = True

        for t in terminators:
            if t in stripped and not stripped.startswith(';') and not stripped.startswith('"'):
                has_term = True
                break

        result.append(line)

    return '\n'.join(result)


def _fix_rt_list_get_null_safe(ir_text: str) -> str:
    """把常用运行时函数替换为 null-safe 版本。"""
    import re

    ir_text = re.sub(
        r'(define i8\* @rt_list_get\(i8\* %lst, i32 %idx\) \{\n)(?:entry:\n)?',
        r'\1  %_ns_gln = icmp eq i8* %lst, null\n  br i1 %_ns_gln, label %_ns_gl_null, label %_ns_gl_ok\n_ns_gl_null:\n  ret i8* null\n_ns_gl_ok:\n',
        ir_text,
    )

    ir_text = re.sub(
        r'(define i32 @rt_list_len\(i8\* %lst\) \{\n)(?:entry:\n)?',
        r'\1  %_ns_lln = icmp eq i8* %lst, null\n  br i1 %_ns_lln, label %_ns_ll_null, label %_ns_ll_ok\n_ns_ll_null:\n  ret i32 0\n_ns_ll_ok:\n',
        ir_text,
    )

    ir_text = re.sub(
        r'(define i32 @rt_str_len\(i8\* %s\) \{\n)(?:entry:\n)?',
        r'\1  %_ns_sln = icmp eq i8* %s, null\n  br i1 %_ns_sln, label %_ns_sl_null, label %_ns_sl_ok\n_ns_sl_null:\n  ret i32 0\n_ns_sl_ok:\n',
        ir_text,
    )

    ir_text = re.sub(
        r'(define i8\* @rt_list_push_item\(i8\* %lst, i8\* %item\) \{\n)(?:entry:\n)?',
        r'\1  %_ns_pin = icmp eq i8* %lst, null\n  br i1 %_ns_pin, label %_ns_pi_null, label %_ns_pi_ok\n_ns_pi_null:\n  ret i8* null\n_ns_pi_ok:\n',
        ir_text,
    )

    ir_text = re.sub(
        r'(define i32 @rt_str_find\(i8\* %s, i8\* %sub\) \{\n)(?:entry:\n)?',
        r'\1  %_ns_sf0 = icmp eq i8* %s, null\n  br i1 %_ns_sf0, label %_ns_sf_null, label %_ns_sf_c1\n_ns_sf_null:\n  ret i32 -1\n_ns_sf_c1:\n  %_ns_sf1 = icmp eq i8* %sub, null\n  br i1 %_ns_sf1, label %_ns_sf_null, label %_ns_sf_ok\n_ns_sf_ok:\n',
        ir_text,
    )

    ir_text = ir_text.replace(
        'define i8* @rt_str_to_list(i8* %a) {\n  ret i8* null\n}',
        'define i8* @rt_str_to_list(i8* %a) {\n  %_stl = call i8* @rt_list_new()\n  ret i8* %_stl\n}',
    )

    ir_text = ir_text.replace(
        'define i8* @rt_int_to_str(i8* %v) {\n  ret i8* null\n}',
        'define i8* @rt_int_to_str(i8* %v) {\n  %_its = call i8* @rt_str_new(i8* null, i32 0)\n  ret i8* %_its\n}',
    )

    ir_text = ir_text.replace(
        'define i8* @rt_dict_keys(i8* %d) {\n  ret i8* null\n}',
        'define i8* @rt_dict_keys(i8* %d) {\n  %_dk = call i8* @rt_list_new()\n  ret i8* %_dk\n}',
    )

    ir_text = ir_text.replace(
        'define i8* @rt_list_concat(i8* %a, i8* %b) {\n  ret i8* %a\n}',
        'define i8* @rt_list_concat(i8* %a, i8* %b) {\n  %_lcn = icmp eq i8* %a, null\n  br i1 %_lcn, label %_lc_retb, label %_lc_reta\n_lc_retb:\n  ret i8* %b\n_lc_reta:\n  ret i8* %a\n}',
    )

    ir_text = ir_text.replace(
        'define i8* @rt_str_substr(i8* %a, i8* %b, i8* %c) {\n  ret i8* %a\n}',
        'define i8* @rt_str_substr(i8* %a, i8* %b, i8* %c) {\n  %_ssn = icmp eq i8* %a, null\n  br i1 %_ssn, label %_ss_ret_ok, label %_ss_ret_a\n_ss_ret_ok:\n  %_ssr = call i8* @rt_str_new(i8* null, i32 0)\n  ret i8* %_ssr\n_ss_ret_a:\n  ret i8* %a\n}',
    )

    ir_text = re.sub(r'(?<=_ok:\n)entry:\n', r'', ir_text)

    return ir_text


def _fix_param_unbox(ir_text: str) -> str:
    """修复 fn handler 的参数 unbox/rebox 模式。"""
    import re

    lines = ir_text.split('\n')
    result = []
    i = 0
    fixed = 0
    while i < len(lines):
        m1 = re.match(r'\s*(%\d+)\s*=\s*ptrtoint\s+i8\*\s+(%_\w+_arg)\s+to\s+i64\s*$', lines[i])
        if m1 and i + 6 < len(lines):
            raw = m1.group(1)
            param = m1.group(2)
            m2 = re.match(r'\s*(%\d+)\s*=\s*ashr\s+i64\s+' + re.escape(raw) + r'\s*,\s*1\s*$', lines[i + 1])
            m3 = re.match(r'\s*(%\d+)\s*=\s*alloca\s+i8\*\s*$', lines[i + 2])
            if m2 and m3:
                val = m2.group(1)
                alloca_reg = m3.group(1)
                m4 = re.match(r'\s*(%\d+)\s*=\s*shl\s+i64\s+' + re.escape(val) + r'\s*,\s*1\s*$', lines[i + 3])
                if m4:
                    shl = m4.group(1)
                    m5 = re.match(r'\s*(%\d+)\s*=\s*or\s+i64\s+' + re.escape(shl) + r'\s*,\s*1\s*$', lines[i + 4])
                    if m5:
                        orr = m5.group(1)
                        m6 = re.match(
                            r'\s*(%\d+)\s*=\s*inttoptr\s+i64\s+' + re.escape(orr) + r'\s+to\s+i8\*\s*$', lines[i + 5]
                        )
                        if m6:
                            ptr = m6.group(1)
                            indent = ' ' * (len(lines[i]) - len(lines[i].lstrip()))
                            store_old = f'{indent}store i8* {ptr}, i8** {alloca_reg}'
                            if lines[i + 6].strip() == store_old.strip():
                                result.append(f'{indent}{alloca_reg} = alloca i8*')
                                result.append(f'{indent}store i8* {param}, i8** {alloca_reg}')
                                i += 7
                                fixed += 1
                                continue
        result.append(lines[i])
        i += 1
    return '\n'.join(result)


def _fix_missing_constants(ir_text: str) -> str:
    """补发缺失的 @.str.N 字符串常量定义。"""
    import re

    lines = ir_text.split('\n')
    defs = set()
    refs = set()
    for line in lines:
        if 'private constant' in line:
            for m in re.findall(r'@\.str\.(\d+)', line):
                defs.add(int(m))
        else:
            for m in re.findall(r'@\.str\.(\d+)', line):
                refs.add(int(m))
    missing = refs - defs
    if not missing:
        return ir_text
    extra = []
    for idx in sorted(missing):
        extra.append(f'@.str.{idx} = private constant [22 x i8] c"__sanyan_fixup_{idx:04d}__\\00"')
    result = []
    for line in lines:
        result.append(line)
        if line.startswith('declare ') and extra:
            result.extend(extra)
            extra = []
    if extra:
        result.extend(extra)
    return '\n'.join(result)


def _merge_ir_modules(ir_parts: list[str]) -> str:
    """合并多个LLVM IR模块，去重define/declare。"""
    if not ir_parts:
        return ''
    result = ''
    seen_defines = set()
    seen_declares = set()
    seen_globals = set()
    for i, part in enumerate(ir_parts):
        for line in part.split('\n'):
            s = line.strip()
            if i > 0 and ('target triple' in s or 'ModuleID' in s):
                continue
            if s.startswith('@') and ('global' in s or '= private constant' in s or '= external' in s):
                name = s.split('=')[0].strip().lstrip('@').split()[0]
                if name in seen_globals:
                    continue
                seen_globals.add(name)
            if s.startswith('declare '):
                fn = s.split('@')[1].split('(')[0] if '@' in s else ''
                if fn in seen_declares:
                    continue
                seen_declares.add(fn)
            if s.startswith('define '):
                fn = s.split('@')[1].split('(')[0] if '@' in s else ''
                if fn in ('main', '__init') and i > 0:
                    continue
                if fn in seen_defines and fn not in ('main', '__init'):
                    continue
                seen_defines.add(fn)
            result += line + '\n'
    return result
