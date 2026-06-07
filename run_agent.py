"""三言 Agent 启动器 — 支持单次/多轮/自主模式
用法:
    python -X utf8 run_agent.py                        # 交互模式
    python -X utf8 run_agent.py "你的问题"              # 单次提问
    python -X utf8 run_agent.py "任务" --auto           # 自主模式，跑完为止
    python -X utf8 run_agent.py "任务" --auto --dry-run # 只读不改
    python -X utf8 run_agent.py "任务" --auto --rounds 3
    python -X utf8 run_agent.py --resume                # 续接上次任务
    python -X utf8 run_agent.py --list-tasks            # 查看任务历史

    设置 API 密钥:
    set SANYAN_API_KEY=sk-xxx
    或修改 ternary_agent/agent_policy.san 中的 API密钥
"""

import sys, os, argparse, sqlite3, json, time as _time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__)) or '.'
os.chdir(PROJECT_ROOT)

from sugar.parser import parse_code
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache
from preprocess import preprocess_includes


def _extract_exprs(text):
    """括号匹配提取所有顶层 S 表达式，支持嵌套"""
    exprs = []
    depth = 0
    start = -1
    for i, c in enumerate(text):
        if c == '(':
            if depth == 0:
                start = i
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0 and start >= 0:
                exprs.append(text[start : i + 1])
    return exprs


def _register_aliases():
    """注册中文别名（必须在 SanyanEvaluator 实例化之后调用）"""
    from ops.registry import register_alias

    aliases = {
        '转字符串': 'to_string',
        '转JSON': 'to_json',
        '解析JSON': 'from_json',
        '时间戳': 'timestamp',
        '字符串包含': 'str_contains',
        '表长': 'list_len',
        '字符串相等': 'str_equals',
        '是字典': 'is_dict',
        '是列表': 'is_list',
        '是字符串': 'is_string',
        '连接': 'concat',
        '取长': 'length',
        '子串': 'substring',
        '查找': 'find',
        '分割': 'split',
        '包含': 'contains',
        '字典键列表': 'dict_keys',
        '含键': 'dict_contains',
        '置键': 'set_key',
        '取键': 'get_key',
        '删除键': 'delete_key',
        '列表合': 'list_concat',
        '取': 'get',
        '不': 'not',
        '读文件': 'read_file',
        '写文件': 'write_file',
        '转数字': 'to_number',
        '取余': 'mod',
        '大于': 'gt',
        '小于': 'lt',
        '等于': 'eq',
        '不等于': 'ne',
        '大于等于': 'gte',
        '小于等于': 'lte',
    }
    for alias, target in aliases.items():
        try:
            register_alias(alias, target)
        except Exception:
            import sys

            print(f'  ⚠ 别名注册失败: {alias} → {target}', file=sys.stderr)


def load_api_key():
    """从环境变量或配置文件读取 API 密钥。"""
    # 优先级: SANYAN_API_KEY > LLM_KEY > agent_policy.san > village_config.san
    for var in ['SANYAN_API_KEY', 'LLM_KEY']:
        key = os.environ.get(var, '')
        if key and '你的' not in key:
            return key
    # 在 agent.san（含 #include 展开）中查找 API密钥
    agent_path = os.path.join('ternary_agent', 'agent.san')
    with open(agent_path, encoding='utf-8') as f:
        src = f.read()
    src = preprocess_includes(src)
    for line in src.split('\n'):
        if 'API密钥' in line and '=' in line and 'sk-' in line:
            key = line.split('"')[1] if '"' in line else ''
            if key and '你的' not in key:
                return key
    # 尝试从 village_config.san 读取（游戏用的密钥文件）
    village_cfg = os.path.join('ternary_agent', 'runtime_v2', 'village_config.san')
    if os.path.exists(village_cfg):
        with open(village_cfg, encoding='utf-8') as f:
            for line in f:
                if 'API密钥' in line or '密钥' in line:
                    key = line.split('"')[1] if '"' in line else ''
                    if key and '你的' not in key and key.startswith('sk-'):
                        return key
    return ''


def init_evaluator(api_key):
    if not api_key or '你的key' in api_key:
        print('错误: 请设置环境变量 SANYAN_API_KEY 或在 agent_policy.san 中填入有效 API 密钥', file=sys.stderr)
        print('      当前值包含占位符 "sk-你的key"，请替换为实际密钥', file=sys.stderr)
        sys.exit(1)
    clear_cache()
    # 注入环境变量，供 .san 文件通过 getenv 读取
    if api_key:
        os.environ['SANYAN_API_KEY'] = api_key
    evaluator = SanyanEvaluator(max_loop_steps=500000)
    _register_aliases()

    # 预创建沙箱求值器
    _sandbox = SanyanEvaluator(max_loop_steps=100000)
    evaluator.set_var('_sandbox', _sandbox)

    # 注册 write_code 工具所需的 Python 函数
    from ops.registry import register as reg_op

    def _new_evaluator(e, args):
        # 传递干跑模式到沙箱
        if e.has_var('_干跑模式') and e.get_var('_干跑模式'):
            sandbox_ref = e.get_var('_sandbox')
            sandbox_ref.set_var('_干跑模式', True)
        return '_sandbox'

    def _list_files(e, args):
        """列文件(glob_pattern) — 列出项目文件"""
        import glob as _glob

        pattern = str(e.eval(args[0])) if args else '*.san'
        try:
            files = _glob.glob(pattern, recursive=True)
            # 限制结果数量，排除 __pycache__ 等
            files = [f for f in files[:100] if '__pycache__' not in f and '.pyc' not in f]
            return '\n'.join(files) if files else '(无匹配文件)'
        except Exception as ex:
            return f'列文件错误: {ex}'

    def _search_content(e, args):
        """搜内容(pattern, [file_path]) — 搜索文件内容"""
        pattern = str(e.eval(args[0])) if args else ''
        file_path = str(e.eval(args[1])) if len(args) > 1 else '*'
        if not pattern:
            return '搜内容需要至少1个参数: 搜内容 关键词 [文件模式]'
        try:
            import glob as _glob
            import os as _os

            matches = _glob.glob(file_path, recursive=True) if file_path != '*' else []
            if not matches:
                matches = _glob.glob('*.san', recursive=False) + _glob.glob('*.py', recursive=False)
            results = []
            for fp in matches[:20]:
                if _os.path.isdir(fp) or '__pycache__' in fp:
                    continue
                try:
                    with open(fp, encoding='utf-8', errors='ignore') as fh:
                        for lineno, line in enumerate(fh, 1):
                            if pattern.lower() in line.lower():
                                results.append(f'{fp}:{lineno}: {line.strip()[:120]}')
                                if len(results) >= 30:
                                    break
                    if len(results) >= 30:
                        break
                except Exception:
                    pass
            return '\n'.join(results) if results else '(未找到)'
        except Exception as ex:
            return f'搜内容错误: {ex}'

    def _list_files_direct(e, args):
        """直接列出文件（用于 agent 工具调用）"""
        pattern = str(e.eval(args[0])) if args else '*.san'
        import glob as _glob

        try:
            # 简单模式不含路径分隔符时，自动改为递归搜索
            if '/' not in pattern and '\\' not in pattern:
                pattern = '**/' + pattern
            files = _glob.glob(pattern, recursive=True)
            files = [f for f in files[:200] if '__pycache__' not in f and '.pyc' not in f]
            if not files:
                return '(无匹配文件)'
            # 折叠显示：前 15 个 + 总数
            shown = files[:15]
            result = '\n'.join(shown)
            if len(files) > 15:
                result += f'\n  ... 还有 {len(files) - 15} 个文件，共 {len(files)} 个'
            return result
        except Exception as ex:
            return f'列文件错误: {ex}'

    def _read_file_direct(e, args):
        """直接读取文件（用于 agent 工具调用），支持 路径 或 路径|起始行|结束行"""
        raw = str(e.eval(args[0])) if args else ''
        parts = raw.split('|')
        path = parts[0].strip() if parts else ''
        path = _resolve_path(path)
        start_line = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 0
        end_line = int(parts[2]) if len(parts) > 2 and parts[2].strip().isdigit() else 0
        # read_file context
        if not path:
            return '请指定文件路径（可加 |起始行|结束行）'
        try:
            with open(path, encoding='utf-8', errors='ignore') as fh:
                lines = fh.readlines()
            if start_line > 0 or end_line > 0:
                start = max(start_line - 1, 0) if start_line > 0 else 0
                end = min(end_line, len(lines)) if end_line > 0 else len(lines)
                if start >= len(lines):
                    return f'{path} 只有 {len(lines)} 行'
                lines = lines[start:end]
                content = ''.join(lines)
                prefix = f'[{start+1}-{end}] '
            else:
                content = ''.join(lines)
                if len(content) > 3000:
                    content = content[:3000] + f'\n...(已截断，共 {len(lines)} 行。用 路径|行号|行号 指定范围)'
                prefix = ''
            return prefix + content
        except FileNotFoundError:
            return f'文件不存在: {path}'
        except Exception as ex:
            return f'读文件错误: {ex}'

    def _write_file_direct(e, args):
        """直接写文件（用于 agent 工具调用），params 格式: 路径|内容"""
        raw = str(e.eval(args[0])) if args else ''
        parts = raw.split('|', 1)
        path = parts[0].strip() if parts else ''
        path = _resolve_path(path)
        content = parts[1].replace('\\n', '\n') if len(parts) > 1 else ''
        # write_file context
        if not path:
            return '请指定文件路径（格式: 路径|内容）'
        dry = e.has_var('_干跑模式') and e.get_var('_干跑模式')
        if dry:
            return f'[干跑] 将写入 {path}（{len(content)}字符）— 文件未实际修改，验证时内容不变'
        try:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(content)
            return f'已写入: {path} ({len(content)} 字符)'
        except Exception as ex:
            return f'写文件错误: {ex}'

    def _replace_in_file(e, args):
        """替换文件内容并写回，params 格式: 路径|旧文字|新文字（\\n → 换行）"""
        raw = str(e.eval(args[0])) if args else ''
        parts = raw.split('|', 2)
        path = parts[0].strip() if parts else ''
        path = _resolve_path(path)
        # replace_in_file context
        old = parts[1] if len(parts) > 1 else ''
        new = parts[2] if len(parts) > 2 else ''
        if not path or not old:
            return '格式: 路径|旧文字|新文字'
        # 转义：\\n → 真实换行
        old = old.replace('\\n', '\n')
        new = new.replace('\\n', '\n')
        dry = e.has_var('_干跑模式') and e.get_var('_干跑模式')
        if dry:
            return f'[干跑] 将在 {path} 替换 {old[:40]} → {new[:40]} — 文件未实际修改，验证时内容不变'
        try:
            with open(path, encoding='utf-8') as fh:
                content = fh.read()
            count = content.count(old)
            if count == 0:
                return f'未找到 "{old[:50]}" 在 {path}'
            content = content.replace(old, new)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(content)
            return f'已替换 {count} 处 "{old[:40]}" → "{new[:40]}" 在 {path}'
        except FileNotFoundError:
            return f'文件不存在: {path}'
        except Exception as ex:
            return f'替换错误: {ex}'

    def _search_code(e, args):
        """搜索代码内容 — 全局搜索关键词"""
        pattern = str(e.eval(args[0])) if args else ''
        if not pattern:
            return '请指定搜索关键词'
        try:
            import glob as _glob
            import os as _os
            results = []
            exts = ['*.py', '*.san', '*.md']
            for ext in exts:
                for fp in _glob.glob('**/' + ext, recursive=True):
                    if '__pycache__' in fp or '.pyc' in fp:
                        continue
                    try:
                        with open(fp, encoding='utf-8', errors='ignore') as fh:
                            for lineno, line in enumerate(fh, 1):
                                if pattern.lower() in line.lower():
                                    results.append(f'{fp}:{lineno}: {line.strip()[:120]}')
                                    if len(results) >= 25:
                                        break
                    except Exception:
                        pass
                    if len(results) >= 25:
                        break
                if len(results) >= 25:
                    break
            if not results:
                return f'未找到 "{pattern}"'
            result = '\n'.join(results)
            if len(results) >= 25:
                result += f'\n  ... 结果已截断 (共 25 条)'
            return result
        except Exception as ex:
            return f'搜索错误: {ex}'

    def _run_test(e, args):
        """运行测试文件"""
        test_path = str(e.eval(args[0])) if args else ''
        if not test_path:
            return '请指定测试文件路径'
        import subprocess as _sp
        import os as _os
        try:
            if not _os.path.exists(test_path):
                return f'测试文件不存在: {test_path}'
            r = _sp.run(
                ['python', '-X', 'utf8', '-m', 'pytest', test_path, '-v', '-q'],
                capture_output=True, text=True, timeout=60,
                cwd=_os.path.dirname(_os.path.abspath(__file__)) or '.'
            )
            output = r.stdout + r.stderr
            if len(output) > 2000:
                # 只保留首尾
                output = output[:1200] + '\n...(截断)...\n' + output[-500:]
            summary = ''
            if 'FAILED' in output or 'ERROR' in output:
                # 提取失败测试
                for line in output.split('\n'):
                    if 'FAILED' in line or 'ERROR' in line:
                        summary += line.strip() + '\n'
                        if len(summary) > 400:
                            break
            status = '通过' if r.returncode == 0 else '失败'
            return f'[{status}] rc={r.returncode}\n{summary}\n{output[:800]}'
        except _sp.TimeoutExpired:
            return '测试超时 (60s)'
        except Exception as ex:
            return f'测试执行错误: {ex}'

    def _git_diff(e, args):
        """运行 git diff 查看当前修改"""
        import subprocess as _sp
        try:
            r = _sp.run(['git', 'diff', '--stat'], capture_output=True, text=True, timeout=10,
                       cwd=os.path.dirname(os.path.abspath(__file__)) or '.')
            output = r.stdout.strip() or '(无修改)'
            if len(output) > 1500:
                output = output[:1500] + '\n...(已截断)'
            return output
        except Exception as ex:
            return f'git diff 失败: {ex}'

    def _git_status(e, args):
        """运行 git status 查看文件状态"""
        import subprocess as _sp
        try:
            r = _sp.run(['git', 'status', '--short'], capture_output=True, text=True, timeout=10,
                       cwd=os.path.dirname(os.path.abspath(__file__)) or '.')
            output = r.stdout.strip() or '(工作区干净)'
            return output
        except Exception as ex:
            return f'git status 失败: {ex}'

    def _save_task_hook(e, args):
        """保存任务状态到 SQLite"""
        mem = {}
        if e.has_var('_任务记忆'):
            raw = e.get_var('_任务记忆')
            if hasattr(raw, 'to_payload'): raw = raw.to_payload()
            if isinstance(raw, dict):
                mem = {str(k): _to_json_safe(v) for k, v in raw.items()}
        tid = e.get_var('_当前任务ID') if e.has_var('_当前任务ID') else 0
        if tid and mem:
            _save_task_state(tid, mem)
            return '已保存'
        return '无任务'

    def _finish_task_hook(e, args):
        """标记任务完成"""
        tid = e.get_var('_当前任务ID') if e.has_var('_当前任务ID') else 0
        status = str(e.eval(args[0])) if args else 'completed'
        if tid:
            _finish_task(tid, status)
            return f'任务 {tid} {status}'
        return '无任务'

    def _new_task_hook(e, args):
        """创建新任务"""
        desc = str(e.eval(args[0])) if args else '未知'
        tid = _create_task(desc)
        e.set_var('_当前任务ID', tid)
        return tid

    def _clean_json(e, args):
        """清理 JSON 文本中的非法控制字符 + ---END--- 尾标记"""
        text = str(e.eval(args[0])) if args else ''
        # 去 ---END---
        idx = text.rfind('---END---')
        if idx >= 0:
            text = text[:idx]
        # 去掉开头 ```json 或 ```
        text = text.strip()
        if text.startswith('```'):
            end = text.find('\n') if text.find('\n') > 0 else len(text)
            text = text[end:].strip()
        # 去掉最终包裹的 ```
        if text.endswith('```'):
            text = text[:-3].strip()
        # 裸换行 → \\n（修复 JSON 解析）
        in_string = False
        result = []
        for c in text:
            if c == '"':
                in_string = not in_string
            if c == '\n' and in_string:
                result.append('\\n')
            elif c == '\t' and in_string:
                result.append('\\t')
            else:
                result.append(c)
        text = ''.join(result)
        # 解析
        import json as _json
        try:
            parsed = _json.loads(text)
            # 还原 params 中的 \\n
            if isinstance(parsed, dict) and 'params' in parsed:
                parsed['params'] = parsed['params'].replace('\\n', '\n')
            return parsed
        except Exception:
            # 宽松解析：尝试去掉控制字符
            try:
                clean = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                parsed = _json.loads(clean)
                if isinstance(parsed, dict) and 'params' in parsed:
                    parsed['params'] = parsed['params'].replace('\\n', '\n')
                return parsed
            except Exception:
                return None

    def _resolve_path(path):
        """智能路径解析：相对路径找不到时自动搜索"""
        if not path or os.path.exists(path):
            return path
        import glob as _glob
        matches = _glob.glob('**/' + path, recursive=True)
        if matches:
            return matches[0]
        prefixed = os.path.join('ternary_agent', path)
        if os.path.exists(prefixed):
            return prefixed
        matches = _glob.glob('**/' + prefixed, recursive=True)
        return matches[0] if matches else path

    def _replace_all(e, args):
        """批量替换：glob模式|旧文字|新文字"""
        raw = str(e.eval(args[0])) if args else ''
        parts = raw.split('|', 2)
        glob_pattern = parts[0].strip() if parts else '*.py'
        old = parts[1].replace('\\n', '\n') if len(parts) > 1 else ''
        new = parts[2].replace('\\n', '\n') if len(parts) > 2 else ''
        if not old:
            return '格式: 文件模式|旧文字|新文字'
        import glob as _glob
        files = _glob.glob('**/' + glob_pattern, recursive=True)
        files = [f for f in files[:50] if '__pycache__' not in f and '.pyc' not in f]
        results = []
        total = 0
        for fp in files:
            try:
                with open(fp, encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                count = content.count(old)
                if count > 0:
                    dry = e.has_var('_干跑模式') and e.get_var('_干跑模式')
                    if dry:
                        results.append(f'[干跑] {fp}: {count}处')
                    else:
                        content = content.replace(old, new)
                        with open(fp, 'w', encoding='utf-8') as fh:
                            fh.write(content)
                        results.append(f'{fp}: {count}处')
                    total += count
                    if len(results) >= 15:
                        break
            except Exception:
                pass
        if not results:
            return f'未找到 "{old[:40]}" 在 {glob_pattern} 中'
        return '\n'.join([f'共替换 {total} 处:'] + results)

    def _analyze_file(e, args):
        """分析文件结构：返回函数/变量/导入列表"""
        path = str(e.eval(args[0])) if args else ''
        path = _resolve_path(path)
        try:
            with open(path, encoding='utf-8', errors='ignore') as fh:
                code = fh.read()
        except Exception:
            return f'无法读取: {path}'
        result = []
        if path.endswith('.py'):
            try:
                import ast as _ast
                tree = _ast.parse(code)
                for node in _ast.walk(tree):
                    if isinstance(node, _ast.FunctionDef):
                        try:
                            args_str = ', '.join(a.arg for a in node.args.args)
                            end_lineno = node.end_lineno or node.lineno
                            lines = end_lineno - node.lineno + 1
                            result.append(f'def {node.name}({args_str}) :{node.lineno}-{end_lineno}({lines}行)')
                        except Exception:
                            result.append(f'def {node.name}(...) :{node.lineno}')
                    elif isinstance(node, _ast.Import):
                        for a in node.names:
                            result.append(f'import {a.name} :{node.lineno}')
                    elif isinstance(node, _ast.ImportFrom):
                        mod = node.module or ''
                        for a in node.names:
                            result.append(f'from {mod} import {a.name} :{node.lineno}')
                    elif isinstance(node, _ast.ClassDef):
                        result.append(f'class {node.name} :{node.lineno}')
            except Exception as ex:
                result.append(f'(Python parse: {ex})')
        elif path.endswith('.san'):
            try:
                from sugar.parser import parse_code
                ast_nodes, _ = parse_code(code)
                if isinstance(ast_nodes, list):
                    for stmt in ast_nodes[1:] if len(ast_nodes) > 1 else []:
                        if isinstance(stmt, list):
                            if stmt[0] in ('def', '定义', 'fn'):
                                name = stmt[1] if len(stmt) > 1 else '?'
                                result.append(f'fn {name}')
                            elif stmt[0] in ('set', '设'):
                                name = stmt[1] if len(stmt) > 1 else '?'
                                result.append(f'设 {name}')
                            elif stmt[0] in ('import', '导入', 'include', '#include'):
                                result.append(f'import {str(stmt[1])[:60]}')
            except Exception as ex:
                result.append(f'(Sanyan parse: {ex})')
        if not result:
            return f'{path}: (无结构信息)'
        # 摘要在前：统计各类数量
        defs = [r for r in result if r.startswith('def ')]
        imps = [r for r in result if r.startswith('import ') or r.startswith('from ')]
        classes = [r for r in result if r.startswith('class ')]
        summary = f'{path}: {code.count(chr(10))}行, {len(defs)}函数, {len(imps)}导入'
        if classes:
            summary += f', {len(classes)}类'
        # 自动统计大函数
        big_funcs = [d for d in defs if '行)' in d and int(d.split('(')[-1].replace('行)','').replace('行','')) > 50]
        if big_funcs:
            summary += f'\n⚠ >50行: {", ".join(d.split(" :")[0].replace("def ","") for d in big_funcs)}'
        summary += '\n'
        return summary + '\n'.join([*defs[:15], '---', *imps[:8]])

    def _find_symbol(e, args):
        """查找符号定义和引用"""
        symbol = str(e.eval(args[0])) if args else ''
        if not symbol:
            return '请指定符号名'
        import glob as _glob
        results = []
        exts = ['*.py', '*.san']
        for ext in exts:
            for fp in _glob.glob('**/' + ext, recursive=True):
                if '__pycache__' in fp or '.pyc' in fp:
                    continue
                try:
                    with open(fp, encoding='utf-8', errors='ignore') as fh:
                        for lineno, line in enumerate(fh, 1):
                            # Match function/class definitions
                            if f'def {symbol}(' in line or f'class {symbol}' in line or f'定义 {symbol}' in line:
                                results.insert(0, f'DEF {fp}:{lineno}: {line.strip()[:80]}')
                            elif symbol in line and 'import' not in line.lower():
                                results.append(f'REF {fp}:{lineno}: {line.strip()[:80]}')
                        if len(results) > 30:
                            break
                except Exception:
                    pass
                if len(results) > 30:
                    break
        if not results:
            return f'未找到符号: {symbol}'
        return f'符号 {symbol} ({len(results)}处):\n' + '\n'.join(results[:25])

    def _sandbox_eval(e, args):
        """在沙箱中求值代码，返回结果"""
        sandbox_tag = str(e.eval(args[0])) if args else ''
        code = str(e.eval(args[1])) if len(args) > 1 else ''
        sandbox = e.get_var(sandbox_tag) if e.has_var(sandbox_tag) else None
        if sandbox is None:
            return '沙箱未初始化'
        try:
            from lexer import tokenize
            from parser import parse

            exprs = _extract_exprs(code)
            if len(exprs) > 1:
                stmts = []
                for ex in exprs:
                    tks = tokenize(ex)
                    s = parse(tks)
                    if s is not None:
                        stmts.append(s)
                if stmts:
                    sexpr = ['做'] + stmts
                    result = sandbox.eval(sexpr)
                    return str(result.to_int() if hasattr(result, 'to_int') else result)
            if code.strip().startswith('('):
                tokens = tokenize(code)
                single = parse(tokens)
                if single is not None:
                    result = sandbox.eval(single)
                    return str(result.to_int() if hasattr(result, 'to_int') else result)
            from sugar.parser import parse_code as pc

            ast2, _ = pc(code)
            result = None
            for stmt2 in ast2[1:] if isinstance(ast2, list) and len(ast2) > 1 else []:
                try:
                    result = sandbox.eval(stmt2)
                except Exception as ex:
                    return 'eval_error:' + str(ex)
            if result is not None:
                return str(result.to_int() if hasattr(result, 'to_int') else result)
            return 'no_result'
        except Exception as ex:
            return 'ex:' + str(ex)

    reg_op('新求值器', _new_evaluator)
    reg_op('求值', _sandbox_eval)
    reg_op('sandbox_eval', _sandbox_eval)
    reg_op('列文件', _list_files)
    reg_op('搜内容', _search_content)
    reg_op('列文件钩子', _list_files_direct)
    reg_op('读文件钩子', _read_file_direct)
    reg_op('写文件钩子', _write_file_direct)
    reg_op('替换写回', _replace_in_file)
    reg_op('搜代码钩子', _search_code)
    reg_op('跑测试钩子', _run_test)
    reg_op('git差异', _git_diff)
    reg_op('git状态', _git_status)
    reg_op('保存任务状态', _save_task_hook)
    reg_op('完成任务', _finish_task_hook)
    reg_op('新建任务', _new_task_hook)
    reg_op('批量替换', _replace_all)
    reg_op('清理JSON', _clean_json)
    reg_op('分析文件', _analyze_file)
    reg_op('查找符号', _find_symbol)

    agent_path = os.path.join('ternary_agent', 'agent.san')
    src = open(agent_path, encoding='utf-8').read()
    # 预处理 #include 展开
    src = preprocess_includes(src)
    # 新提示词已内置完整语法，不再注入 markdown 文档
    if api_key:
        src = src.replace('sk-你的key', api_key)
        print(f'[调试] API密钥已注入 (长度={len(api_key)})')
    else:
        print('[调试] 警告: API密钥为空，LLM调用将失败')
    ast, _ = parse_code(src)
    fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
    evaluator.eval(['do'] + fixed)
    return evaluator


def run_once(evaluator, question):
    # 检测三言代码：直接执行，不走 LLM
    q = question.strip()
    is_code = (
        q.startswith('(')
        or any(kw in q for kw in ['(设 ', '(循环 ', '(输出 ', '(加 ', '(减 ', '(乘 ', '(除 '])
        or '输出(' in q
        or '设 ' == q[:2]
    )
    if is_code:
        try:
            from lexer import tokenize
            from parser import parse

            exprs = _extract_exprs(q)
            if not exprs:
                exprs = [q]
            parsed = []
            for ex in exprs:
                tokens = tokenize(ex)
                node = parse(tokens)
                if node is not None:
                    parsed.append(node)
            sexpr = parsed[0] if len(parsed) == 1 else ['做'] + parsed
            r = evaluator.eval(sexpr)
            print(r.to_int() if hasattr(r, 'to_int') else r)
            return
        except Exception as ex:
            print(f'执行错误: {ex}')
            return

    evaluator.eval(['Agent运行', question])
    # 导出决策数据 JSON（置信度、传播链等）
    try:
        if evaluator.has_var('_决策记录'):
            records = evaluator.get_var('_决策记录')
            if hasattr(records, 'to_payload') and hasattr(records, 'is_dict') and records.is_dict():
                records = records.to_payload()
            if isinstance(records, dict):
                import json as _json

                _rec = {str(k): (v.to_payload() if hasattr(v, 'to_payload') else str(v)) for k, v in records.items()}
                with open('agent_decision.json', 'w', encoding='utf-8') as jf:
                    _json.dump(_rec, jf, ensure_ascii=False, indent=2)
                print('决策数据已导出到 agent_decision.json')
    except Exception:
        pass
    try:
        evaluator.eval(['保存记忆'])
    except Exception:
        pass


def _watch_files():
    """返回当前所有 Agent 文件的修改时间戳字典。"""
    agent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ternary_agent')
    return {
        'agent.san': os.path.getmtime(os.path.join(agent_dir, 'agent.san')),
        'agent_policy.san': os.path.getmtime(os.path.join(agent_dir, 'agent_policy.san')),
        'decision.san': os.path.getmtime(os.path.join(agent_dir, 'decision.san')),
    }


def run_interactive(evaluator, api_key):
    print('三言 Agent v0.3.0 - 多轮对话（输入 exit 退出）')
    print('  /解释 → 查看最近决策解释')
    print('  /解释 N → 查看第N轮决策解释')
    print('  修改 agent_policy.san 后自动重载')
    print()
    mtimes = _watch_files()
    round_num = 0
    while True:
        round_num += 1
        # 热重载检查：策略文件是否变更
        try:
            new_mtimes = _watch_files()
            if new_mtimes != mtimes:
                print('[策略文件已更新，正在重新加载...]')
                evaluator = init_evaluator(api_key)
                mtimes = new_mtimes
                mtimes = new_mtimes
        except OSError:
            pass

        try:
            q = input(f'[{round_num}] > ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n再见')
            break
        if not q:
            continue
        if q.lower() in ('exit', '退出', 'quit', 'q'):
            print('再见')
            break

        # 特殊命令
        if q.startswith('/解释'):
            parts = q.split()
            if len(parts) >= 2:
                try:
                    evaluator.eval(['解释决策', int(parts[1])])
                except ValueError:
                    print('用法: /解释 N')
            else:
                evaluator.eval(['最近决策'])
            continue

        if q.startswith('/原因'):
            parts = q.split()
            if len(parts) >= 2:
                try:
                    evaluator.eval(['解释原因', int(parts[1])])
                except ValueError:
                    print('用法: /原因 N')
            else:
                print('用法: /原因 N')
            continue

        if q == '/策略':
            evaluator.eval(['策略概览'])
            continue

        try:
            evaluator.eval(['Agent运行', q])
        except Exception as e:
            print(f'错误: {e}')
        try:
            evaluator.eval(['保存记忆'])
        except Exception:
            pass
        print()




# ====== 任务持久化 (SQLite) ======

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)) or '.', 'agent_state.db')

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT, status TEXT DEFAULT 'running',
        created_at REAL, updated_at REAL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS task_memory (
        task_id INTEGER, key TEXT, value TEXT, PRIMARY KEY (task_id, key)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS tool_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER, round_num INTEGER, tool TEXT, params TEXT, result TEXT, timestamp REAL
    )''')
    conn.commit()
    return conn

def _to_json_safe(obj):
    """递归转换 Sanyan 对象到 JSON 安全类型"""
    if hasattr(obj, 'to_payload'):
        return obj.to_payload()
    if hasattr(obj, 'to_int'):
        return obj.to_int()
    if isinstance(obj, dict):
        return {str(k): _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(item) for item in obj]
    return obj

def _save_task_state(task_id, memory_dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE tasks SET updated_at=? WHERE id=?', (_time.time(), task_id))
    for k, v in memory_dict.items():
        safe = _to_json_safe(v)
        val_str = json.dumps(safe, ensure_ascii=False)
        conn.execute('INSERT OR REPLACE INTO task_memory VALUES (?,?,?)', (task_id, k, val_str))
    conn.commit(); conn.close()

def _create_task(description):
    conn = sqlite3.connect(DB_PATH)
    now = _time.time()
    cur = conn.execute('INSERT INTO tasks (description, status, created_at, updated_at) VALUES (?,?,?,?)',
                      (description, 'running', now, now))
    conn.commit(); task_id = cur.lastrowid; conn.close()
    return task_id

def _finish_task(task_id, status='completed'):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE tasks SET status=?, updated_at=? WHERE id=?', (status, _time.time(), task_id))
    conn.commit(); conn.close()

def _load_task(task_id):
    conn = sqlite3.connect(DB_PATH)
    mem = {}
    for row in conn.execute('SELECT key, value FROM task_memory WHERE task_id=?', (task_id,)):
        mem[row[0]] = row[1]
    desc = conn.execute('SELECT description FROM tasks WHERE id=?', (task_id,)).fetchone()
    conn.close()
    return (desc[0] if desc else ''), mem

def _get_last_task():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT id, description FROM tasks WHERE status='running' ORDER BY updated_at DESC LIMIT 1").fetchone()
    conn.close()
    return (row[0], row[1]) if row else (None, None)

def _list_tasks():
    conn = sqlite3.connect(DB_PATH)
    print('\n=== SanyanAgent 任务历史 ===')
    for row in conn.execute('SELECT id, description, status, created_at FROM tasks ORDER BY id DESC LIMIT 20'):
        ts = _time.strftime('%m-%d %H:%M', _time.localtime(row[3]))
        icon = {'running': 'R', 'completed': 'V', 'failed': 'X'}.get(row[2], '?')
        print(f'  [{row[0]}] {icon} {row[2]:10s} {ts}  {row[1][:60]}')
    conn.close()


# ====== AgentRuntime V2: 系统决策引擎 ======
# 架构: LLM只输出下一步工具 → 系统执行 → 系统判断 → 喂回LLM
# 替代 agent.san 的补丁层（惰性检测/空工具纠正/答案提取等10+补丁）

class AgentRuntime:
    """Agent 运行时：系统决策 + LLM 工具选择"""
    def __init__(self, evaluator, sandbox):
        self.ev = evaluator
        self.sandbox = sandbox
        self.tools = {}
        self.memory = {'history': [], 'modified': [], 'stage': 'init'}
        self.context = ''
        self.round = 0

    def register(self, name, handler):
        self.tools[name] = handler

    def run(self, task, max_rounds=10, dry_run=False):
        self.round = 0
        self.context = task
        self.memory = {'history': [], 'modified': [], 'stage': '分析', 'trust': 50}
        scene = self._match_scene(task)

        while self.round < max_rounds:
            self.round += 1
            prompt = self._build_prompt(task, scene)
            raw = self._llm_call(prompt)
            tool, params = self._parse_tool(raw)

            if not tool or tool not in self.tools:
                decision = self._decide('', {}, scene)
                if decision == 'done': break
                if decision == 'retry':
                    self.context += f'\n[系统] 请选择一个可用工具'
                    continue
                break

            result = self.tools[tool](params, dry_run)
            self.memory['history'].append({'tool': tool, 'params': params, 'result': str(result)[:300]})
            if tool in ('write_file', 'replace_in_file', 'replace_all'):
                self.memory['modified'].append(params.split('|')[0] if '|' in params else params)
                self.memory['stage'] = '修改'

            decision = self._decide(tool, result, scene)
            # analyze/find_symbol：结果非空直接完成
            if tool in ('analyze', 'find_symbol') and result and '未找到' not in str(result):
                return {'answer': self._extract_answer(tool, result), 'memory': self.memory}
            if tool == 'done':
                return {'answer': result if result else '完成', 'memory': self.memory}
            if decision == 'done':
                return {'answer': self._extract_answer(tool, result), 'memory': self.memory}
            elif decision == 'retry':
                self.context += f'\n[系统] 需要继续。工具结果: {str(result)[:500]}'

            self.context += f'\n[工具: {tool}] {str(result)[:500]}'

        return {'answer': f'已达{max_rounds}轮上限', 'memory': self.memory}

    def _build_prompt(self, task, scene):
        mem_hint = ''
        if self.memory['stage'] == '修改':
            mem_hint = '\n⚠代码已修改，请run_test验证后再判断是否完成。'
        if self.memory['history']:
            last = self.memory['history'][-1]
            if last['tool'] == 'run_test' and 'FAIL' in str(last.get('result', '')):
                mem_hint = '\n测试失败！请分析错误并修复，然后重测。'
        return f'任务: {task}\n阶段: {self.memory["stage"]}\n{self.context[-3000:]}\n{mem_hint}\n下一步用什么工具？只答: tool_name|params'

    def _llm_call(self, prompt):
        try:
            model = self.ev.get_var('模型名') if self.ev.has_var('模型名') else 'deepseek-chat'
            url = self.ev.get_var('模型URL') if self.ev.has_var('模型URL') else ''
            key = self.ev.get_var('API密钥') if self.ev.has_var('API密钥') else ''
            # 去包装：Sanyan 变量可能是 TritValue
            if hasattr(model, 'to_payload'): model = str(model.to_payload())
            if hasattr(url, 'to_payload'): url = str(url.to_payload())
            if hasattr(key, 'to_payload'): key = str(key.to_payload())
            import urllib.request as _req, json as _json
            body = _json.dumps({
                'model': str(model).strip(),
                'messages': [
                    {'role': 'system', 'content': '你是工具调用系统。只输出: tool_name|params。如: analyze|run_agent.py。如: read_file|run_agent.py|1|10。如: replace_in_file|f.py|old|new。如: done|回答文本。'},
                    {'role': 'user', 'content': prompt}
                ], 'temperature': 0.7, 'max_tokens': 256
            }, ensure_ascii=False).encode('utf-8')
            req = _req.Request(str(url).strip(), data=body, headers={
                'Content-Type': 'application/json', 'Authorization': f'Bearer {str(key).strip()}'}, method='POST')
            resp = _req.urlopen(req, timeout=60).read().decode('utf-8')
            data = _json.loads(resp)
            return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f'[LLM错误] {e}')
            return f'error|{e}'

    def _parse_tool(self, raw):
        raw = raw.strip().replace('---END---', '').replace('---JSON---', '').strip('{}"\' ')
        if '|' in raw:
            parts = raw.split('|', 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''
        if raw.startswith('done'):
            rest = raw.split('|', 1)[1] if '|' in raw else ''
            return 'done', rest
        return raw, ''

    def _decide(self, tool, result, scene):
        result_str = str(result)
        # analyze/find_symbol: 结果有⚠行 → 完成
        if tool in ('analyze', 'find_symbol'):
            if '⚠' in result_str or '(0处)' in result_str:
                return 'done'
        # run_test passed + 之前改过 → 完成
        if tool == 'run_test' and ('通过' in result_str or 'OK' in result_str):
            if self.memory['modified']:
                return 'done'
        # run_test failed → 重试（最多3次）
        if tool == 'run_test' and ('FAIL' in result_str or '失败' in result_str):
            fails = sum(1 for h in self.memory['history'] if h['tool'] == 'run_test')
            if fails < 3:
                return 'retry'
        # done tool
        if tool == 'done':
            return 'done'
        # 修改后没跑测试 → 继续
        if tool in ('replace_in_file', 'replace_all', 'write_file') and not any(h['tool'] == 'run_test' for h in self.memory['history']):
            return 'retry'
        return 'continue'

    def _extract_answer(self, tool, result):
        result_str = str(result)
        if '⚠' in result_str:
            idx = result_str.index('⚠')
            return result_str[idx:idx+200]
        if '共替换' in result_str:
            return result_str[:200]
        if '已替换' in result_str:
            return result_str[:200]
        return result_str[:200] if result_str else '完成'

    def _match_scene(self, task):
        kw = task.lower()
        if any(w in kw for w in ['借钱','借款','转账','密码']):
            return {'scene': '高风险', 'risk': '高'}
        if any(w in kw for w in ['改','修改','替换','删','更新']):
            return {'scene': '修改', 'risk': '低'}
        if any(w in kw for w in ['写代码','程序','函数','计算']):
            return {'scene': '代码', 'risk': '低'}
        return {'scene': '通用', 'risk': '低'}

# ====== Tool 包装函数 (AgentRuntime V2) ======

def _resolve_path_simple(path):
    if not path or os.path.exists(path):
        return path
    import glob as _glob
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
        big = [d for d in defs if '行)' in d and int(d.split('(')[-1].replace('行)','').replace('行','')) > 50]
        if big:
            summary += f'\n⚠ >50行: {", ".join(d.split(" :")[0].replace("def ","") for d in big)}'
        return summary + '\n' + '\n'.join(defs[:12] + ['---'] + imps[:6])
    except Exception as e:
        return f'analyze错误: {e}'

def _find_symbol_direct(symbol):
    import glob as _glob
    results = []
    for ext in ['*.py', '*.san']:
        for fp in _glob.glob('**/' + ext, recursive=True):
            if '__pycache__' in fp: continue
            try:
                with open(fp, encoding='utf-8', errors='ignore') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if f'def {symbol}(' in line or f'class {symbol}' in line or f'定义 {symbol}' in line:
                            results.insert(0, f'DEF {fp}:{lineno}')
                        elif symbol in line and 'import' not in line.lower():
                            results.append(f'REF {fp}:{lineno}')
            except Exception: pass
            if len(results) > 20: break
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
            all_lines = all_lines[max(start-1,0):min(end,total) if end else total]
        content = ''.join(all_lines)
        return content[:3000] + (f'\n...(共{total}行)' if len(content) > 3000 else '')
    except Exception as e:
        return f'读文件错误: {e}'

def _search_code_direct(pattern):
    import glob as _glob
    results = []
    for ext in ['*.py', '*.san', '*.md']:
        for fp in _glob.glob('**/' + ext, recursive=True):
            if '__pycache__' in fp: continue
            try:
                with open(fp, encoding='utf-8', errors='ignore') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if pattern.lower() in line.lower():
                            results.append(f'{fp}:{lineno}: {line.strip()[:100]}')
                            if len(results) >= 20: break
            except Exception: pass
            if len(results) >= 20: break
    return '\n'.join(results) if results else f'未找到: {pattern}'

def _replace_in_file_direct(params, dry_run=False):
    parts = params.replace('\\n', '\n').split('|', 2)
    if len(parts) < 3: return '格式: 路径|旧文字|新文字'
    path, old, new = _resolve_path_simple(parts[0]), parts[1], parts[2]
    if dry_run: return f'[干跑] {path}: {old[:30]}→{new[:30]}'
    try:
        content = open(path, encoding='utf-8').read()
        count = content.count(old)
        if count == 0: return f'未找到 "{old[:40]}"'
        content = content.replace(old, new)
        open(path, 'w', encoding='utf-8').write(content)
        return f'已替换 {count} 处'
    except Exception as e:
        return f'替换错误: {e}'

def _replace_all_direct(params, dry_run=False):
    parts = params.replace('\\n', '\n').split('|', 2)
    if len(parts) < 3: return '格式: 文件模式|旧文字|新文字'
    pattern, old, new = parts
    import glob as _glob
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
        except Exception: pass
    return '\n'.join([f'共替换 {sum(1 for _ in results)} 个文件'] + results[:15]) if results else '未找到'

def _write_file_direct_simple(params, dry_run=False):
    parts = params.split('|', 1)
    path, content = _resolve_path_simple(parts[0]), parts[1].replace('\\n', '\n') if len(parts) > 1 else ''
    if dry_run: return f'[干跑] {path}: {len(content)}字符'
    try:
        open(path, 'w', encoding='utf-8').write(content)
        return f'已写入 {path}'
    except Exception as e:
        return f'写入错误: {e}'

def _list_files_direct_simple(pattern):
    import glob as _glob
    files = _glob.glob('**/' + (pattern or '*.py'), recursive=True)
    return '\n'.join(files[:20]) + (f'\n...共{len(files)}个' if len(files) > 20 else '')

def _run_test_direct(test_path):
    import subprocess as _sp
    try:
        r = _sp.run(['python', '-X', 'utf8', '-m', 'pytest', test_path, '-v', '-q'], capture_output=True, text=True, timeout=60, cwd=os.path.dirname(os.path.abspath(__file__)) or '.')
        output = r.stdout[-500:] + r.stderr[-300:]
        if 'FAILED' in output or 'ERROR' in output:
            return f'FAIL rc={r.returncode}\n{output[:800]}'
        return f'通过 rc={r.returncode}'
    except Exception as e:
        return f'测试错误: {e}'

def _git_diff_direct():
    import subprocess as _sp
    try:
        r = _sp.run(['git', 'diff', '--stat'], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or '(无修改)'
    except: return 'git错误'

def _git_status_direct():
    import subprocess as _sp
    try:
        r = _sp.run(['git', 'status', '--short'], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or '(干净)'
    except: return 'git错误'

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='三言 Agent — 可读决策 DSL + 自主编程助手')
    parser.add_argument('question', nargs='?', default='', help='任务描述（留空进入交互模式）')
    parser.add_argument('--auto', action='store_true', help='自主模式：不停轮直到完成')
    parser.add_argument('--rounds', type=int, default=0, help='最大轮次（覆盖策略配置）')
    parser.add_argument('--dry-run', action='store_true', help='只读不改，禁止文件写入')
    parser.add_argument('--report', action='store_true', help='完成后输出修改报告')
    parser.add_argument('--resume', action='store_true', help='续接上次未完成任务')
    parser.add_argument('--list-tasks', action='store_true', help='查看任务历史')
    args = parser.parse_args()

    # 三言代码：直接执行，跳过 Agent 和 LLM
    if args.question:
        q = args.question.strip()
        if q.startswith('(') or '(设' in q or '(循环' in q or '(输出' in q or '(加' in q:
            from lexer import tokenize
            from parser import parse
            from evaluator import SanyanEvaluator

            e = SanyanEvaluator(max_loop_steps=50000)
            try:
                # 括号匹配提取所有顶层表达式
                exprs = _extract_exprs(q)
                if not exprs:
                    exprs = [q]
                from lexer import tokenize
                from parser import parse

                parsed = []
                for ex in exprs:
                    tokens = tokenize(ex)
                    node = parse(tokens)
                    if node is not None:
                        parsed.append(node)
                sexpr = parsed[0] if len(parsed) == 1 else ['做'] + parsed
                r = e.eval(sexpr)
                print(r.to_int() if hasattr(r, 'to_int') else r)
            except Exception as ex:
                print(f'错误: {ex}')
            return

    # --list-tasks: 查看历史
    _init_db()
    if args.list_tasks:
        _list_tasks()
        return

    api_key = load_api_key()
    if not api_key or '你的' in api_key:
        print('请设置 API 密钥：set SANYAN_API_KEY=sk-xxx')
        sys.exit(1)

    # --rounds 覆盖策略配置
    if args.rounds > 0:
        os.environ['AGENT_MAX_ROUNDS'] = str(args.rounds)

    evaluator = init_evaluator(api_key)

    # --auto 使用新 AgentRuntime V2（系统决策引擎，替代 agent.san 补丁层）
    if args.auto:
        sandbox = evaluator.get_var('_sandbox') if evaluator.has_var('_sandbox') else None
        rt = AgentRuntime(evaluator, sandbox)
        rt.register('analyze', lambda p, d: _analyze_file_direct(p))
        rt.register('find_symbol', lambda p, d: _find_symbol_direct(p))
        rt.register('read_file', lambda p, d: _read_file_direct_simple(p))
        rt.register('search_code', lambda p, d: _search_code_direct(p))
        rt.register('replace_in_file', lambda p, d: _replace_in_file_direct(p, d))
        rt.register('replace_all', lambda p, d: _replace_all_direct(p, d))
        rt.register('write_file', lambda p, d: _write_file_direct_simple(p, d))
        rt.register('list_files', lambda p, d: _list_files_direct_simple(p))
        rt.register('run_test', lambda p, d: _run_test_direct(p))
        rt.register('git_diff', lambda p, d: _git_diff_direct())
        rt.register('git_status', lambda p, d: _git_status_direct())
        rt.register('done', lambda p, d: p if p else '完成')
        result = rt.run(args.question, max_rounds=args.rounds or 10, dry_run=args.dry_run)
        print(f"\n→ {result['answer']}")
        if args.report:
            print(f"\n=== 报告 ===\n阶段: {result['memory']['stage']}\n工具: {len(result['memory']['history'])}次\n修改: {result['memory']['modified']}")
        return

    # --resume: 续接上次任务
    if args.resume:
        tid, desc = _get_last_task()
        if tid:
            desc, mem = _load_task(tid)
            evaluator.set_var('_当前任务ID', tid)
            evaluator.set_var('_当前任务描述', desc)
            run_once(evaluator, desc)
            if args.report:
                _print_report(evaluator)
        else:
            print('没有未完成的任务')
        return

    if args.question:
        if args.auto:
            # 自主模式：inject max rounds and auto flag into evaluator
            if args.rounds > 0:
                evaluator.set_var('最大轮次', args.rounds)
            if args.dry_run:
                evaluator.set_var('_干跑模式', True)
            run_once(evaluator, args.question)
            if args.report:
                _print_report(evaluator)
        else:
            run_once(evaluator, args.question)
    else:
        run_interactive(evaluator, api_key)


def _print_report(evaluator):
    """输出修改报告"""
    try:
        mem = None
        if evaluator.has_var('_ctx'):
            ctx = evaluator.get_var('_ctx')
            if isinstance(ctx, dict) and '_任务记忆' in ctx:
                mem = ctx['_任务记忆']
            elif hasattr(ctx, 'get'):
                mem = ctx.get('_任务记忆', None)
        if mem is None:
            print('\n(无任务记忆)')
            return
        # Extract fields
        files = mem.get('修改文件列表', []) if isinstance(mem, dict) else []
        history = mem.get('工具历史', []) if isinstance(mem, dict) else []
        stage = mem.get('当前阶段', '未知') if isinstance(mem, dict) else '未知'
        task = mem.get('任务描述', '') if isinstance(mem, dict) else ''

        print('\n' + '=' * 40)
        print('  SanyanAgent 任务报告')
        print('=' * 40)
        print(f'  任务: {str(task)[:80]}')
        print(f'  阶段: {str(stage)}')
        print(f'  工具调用: {len(history)} 次' if hasattr(history, '__len__') else f'  工具调用: ? 次')
        if hasattr(files, '__len__') and len(files) > 0:
            print(f'  修改文件: {len(files)} 个')
            for f in files:
                print(f'    - {str(f)}')
        else:
            print('  修改文件: 无')
        print('=' * 40)
    except Exception as ex:
        print(f'\n(报告生成失败: {ex})')


if __name__ == '__main__':
    main()
