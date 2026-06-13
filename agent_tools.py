"""Tool 包装函数 — AgentRuntime V3 工具层"""

import os
import glob as _glob
import subprocess as _sp

# ====== Tool 包装函数 ======


def _resolve_path_simple(path):
    if not path or os.path.exists(path):
        return path
    # 沙箱：禁止目录穿越
    if '..' in path:
        return path.replace('..', '_')

    matches = _glob.glob('**/' + path, recursive=True)
    return matches[0] if matches else path


def _analyze_file_direct(path):
    try:
        import ast as _ast

        path = _resolve_path_simple(path)
        code = open(path, encoding='utf-8', errors='ignore').read()
        tree = _ast.parse(code) if path.endswith('.py') else None
        if not tree:
            return f'{path}: 非Python文件'
        result = []
        for node in _ast.walk(tree):
            if isinstance(node, _ast.FunctionDef):
                try:
                    args_str = ', '.join(a.arg for a in node.args.args)
                    end = node.end_lineno or node.lineno
                    lines = end - node.lineno + 1
                    result.append(f'def {node.name}({args_str}) :{node.lineno}-{end}({lines}行)')
                except Exception:
                    result.append(f'def {node.name}(...) :{node.lineno}')
            elif isinstance(node, _ast.Import):
                for a in node.names:
                    result.append(f'import {a.name} :{node.lineno}')
            elif isinstance(node, _ast.ImportFrom):
                mod = node.module or ''
                for a in node.names:
                    result.append(f'from {mod} import {a.name} :{node.lineno}')
        defs = [r for r in result if r.startswith('def ')]
        imps = [r for r in result if r.startswith('import ') or r.startswith('from ')]
        summary = f'{path}: {code.count(chr(10))}行, {len(defs)}函数, {len(imps)}导入'
        big = [d for d in defs if '行)' in d and int(d.split('(')[-1].replace('行)', '').replace('行', '')) > 50]
        if big:
            summary += f'\n⚠ >50行: {", ".join(d.split(" :")[0].replace("def ", "") for d in big)}'
        return summary + '\n' + '\n'.join(defs[:12] + ['---'] + imps[:6])
    except Exception as e:
        return f'analyze错误: {e}'


def _find_symbol_direct(symbol):
    results: list[str] = []
    for ext in ['*.py', '*.san']:
        for fp in _glob.glob('**/' + ext, recursive=True):
            if '__pycache__' in fp:
                continue
            try:
                with open(fp, encoding='utf-8', errors='ignore') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if f'def {symbol}(' in line or f'class {symbol}' in line or f'定义 {symbol}' in line:
                            results.insert(0, f'DEF {fp}:{lineno}')
                        elif symbol in line and 'import' not in line.lower():
                            results.append(f'REF {fp}:{lineno}')
            except Exception:
                pass
            if len(results) > 20:
                break
    return f'符号 {symbol} ({len(results)}处):\n' + '\n'.join(results[:15]) if results else f'未找到符号: {symbol}'


def _read_file_direct_simple(params):
    parts = params.split('|')
    path = _resolve_path_simple(parts[0])
    start = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 0
    end = int(parts[2]) if len(parts) > 2 and parts[2].strip().isdigit() else 0
    try:
        with open(path, encoding='utf-8', errors='ignore') as fh:
            all_lines = fh.readlines()
        total = len(all_lines)
        if start > 0:
            all_lines = all_lines[max(start - 1, 0) : min(end, total) if end else total]
        content = ''.join(all_lines)
        return content[:3000] + (f'\n...(共{total}行)' if len(content) > 3000 else '')
    except Exception as e:
        return f'读文件错误: {e}'


def _search_code_direct(pattern):

    results = []
    for ext in ['*.py', '*.san', '*.md']:
        for fp in _glob.glob('**/' + ext, recursive=True):
            if '__pycache__' in fp:
                continue
            try:
                with open(fp, encoding='utf-8', errors='ignore') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if pattern.lower() in line.lower():
                            results.append(f'{fp}:{lineno}: {line.strip()[:100]}')
                            if len(results) >= 20:
                                break
            except Exception:
                pass
            if len(results) >= 20:
                break
    return '\n'.join(results) if results else f'未找到: {pattern}'


def _replace_in_file_direct(params, dry_run=False):
    parts = params.replace('\\n', '\n').split('|', 2)
    if len(parts) < 3:
        return '格式: 路径|旧文字|新文字'
    path, old, new = _resolve_path_simple(parts[0]), parts[1], parts[2]
    if dry_run:
        return f'[干跑] {path}: {old[:30]}→{new[:30]}'
    try:
        content = open(path, encoding='utf-8').read()
        count = content.count(old)
        if count == 0:
            return f'未找到 "{old[:40]}"'
        content = content.replace(old, new)
        open(path, 'w', encoding='utf-8').write(content)
        return f'已替换 {count} 处'
    except Exception as e:
        return f'替换错误: {e}'


def _replace_all_direct(params, dry_run=False):
    parts = params.replace('\\n', '\n').split('|', 2)
    if len(parts) < 3:
        return '格式: 文件模式|旧文字|新文字'
    pattern, old, new = parts

    files = _glob.glob('**/' + pattern, recursive=True)
    results = []
    for fp in files[:30]:
        try:
            content = open(fp, encoding='utf-8', errors='ignore').read()
            count = content.count(old)
            if count > 0:
                if dry_run:
                    results.append(f'[干跑] {fp}: {count}处')
                else:
                    open(fp, 'w', encoding='utf-8').write(content.replace(old, new))
                    results.append(f'{fp}: {count}处')
        except Exception:
            pass
    return '\n'.join([f'共替换 {sum(1 for _ in results)} 个文件'] + results[:15]) if results else '未找到'


def _write_file_direct_simple(params, dry_run=False):
    parts = params.split('|', 1)
    path, content = _resolve_path_simple(parts[0]), parts[1].replace('\\n', '\n') if len(parts) > 1 else ''
    if dry_run:
        return f'[干跑] {path}: {len(content)}字符'
    try:
        open(path, 'w', encoding='utf-8').write(content)
        return f'已写入 {path}'
    except Exception as e:
        return f'写入错误: {e}'


def _list_files_direct_simple(pattern):

    files = _glob.glob('**/' + (pattern or '*.py'), recursive=True)
    return '\n'.join(files[:20]) + (f'\n...共{len(files)}个' if len(files) > 20 else '')


def _run_test_direct(test_path):

    try:
        r = _sp.run(
            ['python', '-X', 'utf8', '-m', 'pytest', test_path, '-v', '-q'],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(os.path.abspath(__file__)) or '.',
        )
        output = r.stdout[-500:] + r.stderr[-300:]
        if 'FAILED' in output or 'ERROR' in output:
            return f'FAIL rc={r.returncode}\n{output[:800]}'
        return f'通过 rc={r.returncode}'
    except Exception as e:
        return f'测试错误: {e}'


def _git_diff_direct():

    try:
        r = _sp.run(['git', 'diff', '--stat'], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or '(无修改)'
    except Exception:
        return 'git错误'


def _run_assembly(params):
    """写汇编代码并执行"""
    import tempfile, os
    source = ''; output = 'build/agent_asm.bin'; run_flag = True
    for line in (params or '').splitlines():
        line = line.strip()
        if line.startswith('source='): source = line[7:]
        elif line.startswith('path='): output = line[5:].strip()
        elif line == '--no-run': run_flag = False
    if not source: return '缺少 source= 参数'
    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
    try:
        from asm import Assembler
        a = Assembler(); data = a.build(source)
        with open(output, 'wb') as f: f.write(data)
        result = f'汇编成功: {len(data)}字节'
        if run_flag:
            from vm import VM; import io, sys
            old = sys.stdout; sys.stdout = io.StringIO()
            VM.from_bin(output).run()
            out = sys.stdout.getvalue(); sys.stdout = old
            result += f' 输出: {out.strip() or "(空)"}'
    except Exception as e:
        result = f'汇编失败: {e}'
    return result


def _git_status_direct():

    try:
        r = _sp.run(['git', 'status', '--short'], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or '(干净)'
    except Exception:
        return 'git错误'


def _run_assembly(params):
    """写汇编代码并执行"""
    import tempfile, os
    source = ''; output = 'build/agent_asm.bin'; run_flag = True
    for line in (params or '').splitlines():
        line = line.strip()
        if line.startswith('source='): source = line[7:]
        elif line.startswith('path='): output = line[5:].strip()
        elif line == '--no-run': run_flag = False
    if not source: return '缺少 source= 参数'
    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
    try:
        from asm import Assembler
        a = Assembler(); data = a.build(source)
        with open(output, 'wb') as f: f.write(data)
        result = f'汇编成功: {len(data)}字节'
        if run_flag:
            from vm import VM; import io, sys
            old = sys.stdout; sys.stdout = io.StringIO()
            VM.from_bin(output).run()
            out = sys.stdout.getvalue(); sys.stdout = old
            result += f' 输出: {out.strip() or "(空)"}'
    except Exception as e:
        result = f'汇编失败: {e}'
    return result
