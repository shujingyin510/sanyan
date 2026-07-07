"""Tool 包装函数 — AgentRuntime V3 工具层"""

import ast as _ast_mod
import difflib as _difflib
import os
import glob as _glob
import re as _re
import subprocess as _sp
import time as _time

# 0707 第九轮实录：read_file 范围读输出行号（N│），坐标供 replace_lines 用；
# 弱模型把带行号的文本原样抄进 old/new 时按此模式剥除——U+2502 紧跟行首数字
# 在真实 Python 代码里几乎不可能出现，剥除安全。
_LINENO_PREFIX = _re.compile(r'(?m)^[ \t]{0,6}\d{1,6}│')


def _strip_lineno_prefixes(text):
    return _LINENO_PREFIX.sub('', text)


# ====== Tool 包装函数 ======


def _resolve_path_simple(path):
    if not path or os.path.exists(path):
        return path
    # 沙箱：禁止目录穿越
    if '..' in path:
        return path.replace('..', '_')

    matches = _glob.glob('**/' + path, recursive=True)
    return matches[0] if matches else path


def param_path(params):
    """从工具参数中提取文件路径"""
    if isinstance(params, str):
        return params.split('|')[0]
    if isinstance(params, dict):
        return params.get('path', params.get('test_file', params.get('file', '')))
    return str(params)


def _check_py_syntax_or_revert(path, original):
    """.py 写入后语法自检；坏则还原。返回错误信息（空串=通过）。

    P3 底层优化①：旧行为是把文件改出语法错误还返回"已替换 N 处"成功，
    agent 拿着 AFFIRM 继续走，直到 oracle 才发现文件废了——整轮报销。
    守卫把致命错误变成循环内可恢复的一步。original=None 表示新建文件（坏则删除）。
    """
    if not str(path).endswith('.py'):
        return ''
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            _ast_mod.parse(fh.read())
        return ''
    except SyntaxError as e:
        if original is None:
            try:
                os.remove(path)
            except OSError:
                pass
            return f'写入产生语法错误(文件已删除): 第{e.lineno}行 {e.msg}。请修正后重写'
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(original)
        return f'替换产生语法错误(已自动还原): 第{e.lineno}行 {e.msg}。请修正 new 文本后重试'
    except OSError:
        return ''


def _closest_snippet(content, old, max_lines=12):
    """old 未命中时，从 content 里找最相近的原文片段（引导 agent 修正抄写）。

    P3 底层优化②：弱模型抄 old 差一个空格即"未找到"且不知差在哪，只能盲重试。
    """
    old_lines = [ln for ln in old.splitlines() if ln.strip()]
    if not old_lines:
        return ''
    content_lines = content.splitlines()
    anchor = _difflib.get_close_matches(old_lines[0], content_lines, n=1, cutoff=0.6)
    if not anchor:
        return ''
    idx = content_lines.index(anchor[0])
    window = content_lines[idx : idx + min(len(old_lines) + 2, max_lines)]
    return '\n'.join(window)


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
            # 第三段双语义兼容：LLM 常发"起始行|行数"（如 308|100），旧实现按"结束行"
            # 切出 [307:100]=空串——P2 探针实测模型每轮读到虚空、只能原地打转。
            # 小于起始行 → 行数；否则 → 结束行（start=1 时两种语义结果相同）。
            if end and end < start:
                end = start + end - 1
            if start > total:
                return f'(空: 文件共{total}行, 起始行{start}超界)'
            all_lines = all_lines[start - 1 : min(end, total) if end else total]
            # 0707 第九轮实录：范围读不带行号，模型两次原话抱怨"没显示具体行号"——
            # 顶推推荐的 replace_lines 按行号操作，工具却不给坐标，模型只能凭记忆
            # 构造 old 串（r9 未找到）或散文空转烧光预算。行号仅定位，抄进 old/new
            # 会被 _strip_lineno_prefixes 剥掉。
            content = ''.join(f'{start + i}│{line}' for i, line in enumerate(all_lines))
        else:
            content = ''.join(all_lines)
        # 4500: 94行级函数(~3.3k字符)+行号前缀须完整可见, replace_in_file 需要精确旧文本
        return content[:4500] + (f'\n...(共{total}行)' if len(content) > 4500 else '')
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
        note = ''
        if count == 0:
            # 模型把 read_file 的行号前缀（N│）连同代码抄进了 old——剥掉再试一次；
            # 命中才剥 new（同一份复制粘贴的证据），原文直接命中则两者都不动。
            stripped = _strip_lineno_prefixes(old)
            if stripped != old and content.count(stripped) > 0:
                old, new, count = stripped, _strip_lineno_prefixes(new), content.count(stripped)
                note = '（old/new 中的行号前缀已剥除——行号仅是 read_file 的显示，不在文件里）'
            else:
                hint = _closest_snippet(content, old)
                return f'未找到 "{old[:40]}"' + (f'；文件中最接近的原文是:\n{hint}' if hint else '')
        open(path, 'w', encoding='utf-8').write(content.replace(old, new))
        err = _check_py_syntax_or_revert(path, content)
        if err:
            return err
        return f'已替换 {count} 处{note}'
    except Exception as e:
        return f'替换错误: {e}'


def _replace_lines_direct(params, dry_run=False):
    """行区间替换: 路径|起始行|结束行|新文本（\\n→换行）。

    P3 底层优化③：精确文本匹配是强加给弱模型的摩擦——它本来就在用行号思考
    （read_file 就是按行号读的）。行区间替换绕开抄写问题；语法守卫兜底安全。
    """
    parts = params.split('|', 3)
    if len(parts) < 4:
        return '格式: 路径|起始行|结束行|新文本'
    path = _resolve_path_simple(parts[0].strip())
    try:
        start, end = int(parts[1]), int(parts[2])
    except ValueError:
        return '格式: 路径|起始行|结束行|新文本（行号须为整数）'
    # 模型常把带行号的 read_file 输出整段抄来当新文本——行号前缀不属于文件内容
    new_text = _strip_lineno_prefixes(parts[3].replace('\\n', '\n'))
    if dry_run:
        return f'[干跑] {path}: L{start}-{end}'
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            lines = fh.read().splitlines(keepends=True)
        total = len(lines)
        if not (1 <= start <= end <= total):
            return f'行区间无效: L{start}-{end}（文件共{total}行）'
        original = ''.join(lines)
        if new_text and not new_text.endswith('\n'):
            new_text += '\n'
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(''.join(lines[: start - 1]) + new_text + ''.join(lines[end:]))
        err = _check_py_syntax_or_revert(path, original)
        if err:
            return err
        return f'已替换 {path} 第{start}-{end}行（{end - start + 1}行 → {len(new_text.splitlines())}行）'
    except OSError as e:
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
                    err = _check_py_syntax_or_revert(fp, content)
                    results.append(f'{fp}: {err}' if err else f'{fp}: {count}处')
        except Exception:
            pass
    return '\n'.join([f'共替换 {sum(1 for _ in results)} 个文件'] + results[:15]) if results else '未找到'


def _write_file_direct_simple(params, dry_run=False):
    parts = params.split('|', 1)
    path, content = _resolve_path_simple(parts[0]), parts[1].replace('\\n', '\n') if len(parts) > 1 else ''
    if dry_run:
        return f'[干跑] {path}: {len(content)}字符'
    try:
        original = None
        if os.path.exists(path):
            original = open(path, encoding='utf-8', errors='replace').read()
        open(path, 'w', encoding='utf-8').write(content)
        err = _check_py_syntax_or_revert(path, original)
        if err:
            return err
        return f'已写入 {path}'
    except Exception as e:
        return f'写入错误: {e}'


def _list_files_direct_simple(pattern):

    files = _glob.glob('**/' + (pattern or '*.py'), recursive=True)
    return '\n'.join(files[:20]) + (f'\n...共{len(files)}个' if len(files) > 20 else '')


def _run_test_direct(test_path, dry_run=False):

    if isinstance(test_path, dict):
        test_path = test_path.get('test_file', test_path.get('path', ''))
    if not test_path:
        from agent_system.contracts import ToolResult, ToolStatus

        return ToolResult(ToolStatus.ERROR, error='缺少 test_file 参数', meta={'passed': False})

    if dry_run:
        return f'[干跑] 将运行测试: {test_path}'

    try:
        r = _sp.run(
            ['python', '-X', 'utf8', '-m', 'pytest', test_path, '-v', '-q'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60,
            # 仓库根（本文件已在 agent_system/ 下）——曾锚 agent_system/ 导致
            # tests/ 永远找不到，agent 的自验证工具从重构起就是坏的
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))) or '.',
        )
        output = r.stdout[-500:] + r.stderr[-300:]
        from agent_system.contracts import ToolResult, ToolStatus

        passed = 'FAILED' not in output and 'ERROR' not in output and r.returncode == 0
        if passed:
            return ToolResult(ToolStatus.OK, data=f'通过 rc={r.returncode}', meta={'passed': True})
        return ToolResult(ToolStatus.ERROR, error=f'FAIL rc={r.returncode}\n{output[:800]}', meta={'passed': False})
    except Exception as e:
        from agent_system.contracts import ToolResult, ToolStatus

        return ToolResult(ToolStatus.ERROR, error=f'测试错误: {e}', meta={'passed': False})


def _run_shell_direct(cmd, dry_run=False):
    """执行 shell 命令"""
    if dry_run:
        return f'[干跑] 将执行: {cmd}'
    if not cmd or not cmd.strip():
        return '缺少命令'
    try:
        r = _sp.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8',  # Windows 默认 GBK 解码 utf-8 输出会在 reader 线程抛异常
            errors='replace',
            timeout=60,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))) or '.',
        )
        output = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            return f'失败 rc={r.returncode}\n{output[-800:]}'
        return output[-500:] or '成功'
    except _sp.TimeoutExpired:
        return '命令超时(60s)'
    except Exception as e:
        return f'命令错误: {e}'


def _git_diff_direct():

    try:
        r = _sp.run(['git', 'diff', '--stat'], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or '(无修改)'
    except Exception:
        return 'git错误'


def _run_assembly(params):
    """写汇编代码并执行"""
    import os

    source = ''
    output = 'build/agent_asm.bin'
    run_flag = True
    for line in (params or '').splitlines():
        line = line.strip()
        if line.startswith('source='):
            source = line[7:]
        elif line.startswith('path='):
            output = line[5:].strip()
        elif line == '--no-run':
            run_flag = False
    if not source:
        return '缺少 source= 参数'
    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
    try:
        from compiler.asm import Assembler

        a = Assembler()
        data = a.build(source)
        with open(output, 'wb') as f:
            f.write(data)
        result = f'汇编成功: {len(data)}字节'
        if run_flag:
            from vm import VM
            import io
            import sys

            old = sys.stdout
            sys.stdout = io.StringIO()
            VM.from_bin(output).run()
            out = sys.stdout.getvalue()
            sys.stdout = old
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


def _git_stash_direct():
    try:
        r = _sp.run(['git', 'stash', '-m', 'agent自动保存现场'], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or r.stderr.strip() or '已stash'
    except Exception:
        return 'git stash错误'


def _git_reset_hard_direct():
    try:
        r = _sp.run(['git', 'reset', '--hard', 'HEAD~1'], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or r.stderr.strip() or '已reset'
    except Exception:
        return 'git reset错误'


def _git_commit_auto_direct(params):
    msg = (params or '').strip() or 'agent自动提交'
    try:
        r = _sp.run(['git', 'commit', '-am', msg], capture_output=True, text=True, timeout=15)
        return r.stdout.strip() or r.stderr.strip() or f'已提交: {msg}'
    except Exception:
        return 'git commit错误'


# Multi-agent tools
_agent_registry: dict[str, dict] = {}
_AGENT_TIMEOUT = 30  # 可被 agent_policy.san 中 Agent超时秒数 覆盖
_AGENT_MAX_RETRY = 2
_AGENT_CONF_WINDOW = 4  # 置信度衰减检测窗口
_AGENT_CONF_FLOOR = 0.35  # 置信度底线


def _agent_force_recover(name):
    if name in _agent_registry:
        _agent_registry[name] = {
            'status': 'killed',
            'task': _agent_registry[name].get('task', ''),
            'result': 'force killed',
        }
        return 'Agent ' + name + ' killed'
    return 'Agent ' + name + ' not found'


def _agent_check_deadlock():
    stuck = []
    now = _time.time()
    for name, info in list(_agent_registry.items()):
        if info.get('status') == 'running':
            start = info.get('start_time', now)
            if now - start > 30:
                info['status'] = 'stuck'
                stuck.append(name)
    return 'stuck: ' + ', '.join(stuck) if stuck else 'all clear'


def _agent_cleanup(max_age=300):
    now = _time.time()
    for name, info in list(_agent_registry.items()):
        if now - info.get('start_time', 0) > max_age:
            del _agent_registry[name]
    return 'ok'


def _load_agent_config(evaluator=None):
    """从 evaluator 或 agent_policy.san 加载多Agent配置"""
    global _AGENT_TIMEOUT, _AGENT_CONF_WINDOW, _AGENT_CONF_FLOOR
    if evaluator:
        try:
            if evaluator.has_var('Agent超时秒数'):
                _AGENT_TIMEOUT = evaluator.get_var('Agent超时秒数').to_int()
            if evaluator.has_var('Agent置信度衰减窗'):
                _AGENT_CONF_WINDOW = evaluator.get_var('Agent置信度衰减窗').to_int()
            if evaluator.has_var('Agent置信度底线'):
                _AGENT_CONF_FLOOR = evaluator.get_var('Agent置信度底线').to_float()
        except Exception:
            pass


def _classify_failure(out, rounds, confs):
    """分类重启原因: info_gap / wrong_approach / unsolvable / escalation"""
    if not confs:
        return 'unknown'
    if any('UNCERT' in out[o : o + 200] for o in range(0, len(out), 500)):
        return 'info_gap'
    floor = min(confs) if confs else 1.0
    if floor < 0.2:
        return 'unsolvable'
    if len(rounds) >= 4:
        return 'wrong_approach'
    return 'escalation'


def _spawn_sub_agent(params):

    task = ''
    name = 'sub'
    for line in (params or '').splitlines():
        line = line.strip()
        if line.startswith('task='):
            task = line[5:]
        elif line.startswith('name='):
            name = line[5:]
    if not task:
        return 'missing task='
    if name in _agent_registry and _agent_registry[name].get('status') == 'running':
        elapsed = _time.time() - _agent_registry[name].get('start_time', _time.time())
        if elapsed > _AGENT_TIMEOUT:
            _agent_registry[name]['status'] = 'killed'
            return '[Agent ' + name + '] timeout ' + str(int(elapsed)) + 's'
        return 'Agent ' + name + ' running'
    _agent_registry[name] = {'status': 'running', 'task': task, 'result': None, 'start_time': _time.time()}
    try:
        from core.evaluator import SanyanEvaluator
        from ops.file_ops import clear_cache
        from core.lexer import tokenize
        from core.parser import parse
        import io
        import sys

        clear_cache()
        sub_ev = SanyanEvaluator(max_loop_steps=200000)
        old = sys.stdout
        sys.stdout = io.StringIO()
        tokens = tokenize(task)
        ast = parse(tokens)
        result = sub_ev.eval(ast) if ast else 'parse failed'
        out = sys.stdout.getvalue()
        sys.stdout = old
        out = out.strip() if out.strip() else str(result)
        _agent_registry[name] = {'status': 'done', 'task': task, 'result': str(result)}
        return '[Agent ' + name + '] ' + out[:500]
    except Exception as e:
        _agent_registry[name] = {'status': 'error', 'task': task, 'result': str(e)}
        return '[Agent ' + name + '] error: ' + str(e)[:200]


def _agent_message(params):
    to = ''
    msg = ''
    for line in (params or '').splitlines():
        line = line.strip()
        if line.startswith('to='):
            to = line[3:]
        elif line.startswith('msg='):
            msg = line[4:]
    return f'msg sent to {to}: {msg[:100]}' if to else 'missing to='


def _agent_list(params):
    if not _agent_registry:
        return 'no agents'
    return chr(10).join(f'{n}: {i["status"]}' for n, i in _agent_registry.items())


def _spawn_parallel(params):
    """并行调度多个子Agent: tasks=任务1|任务2|任务3
    每个任务在独立线程中执行，返回所有结果。
    """
    import threading

    tasks = []
    for line in (params or '').splitlines():
        line = line.strip()
        if line.startswith('tasks='):
            tasks = [t.strip() for t in line[6:].split('|') if t.strip()]
    if not tasks:
        return 'missing tasks='

    results = {}
    errors = {}
    lock = threading.Lock()

    def run_one(idx, task):
        try:
            r = _spawn_sub_agent('name=worker' + str(idx) + chr(10) + 'task=' + task)
            with lock:
                results[idx] = r
        except Exception as e:
            with lock:
                errors[idx] = str(e)

    threads = []
    for i, task in enumerate(tasks):
        t = threading.Thread(target=run_one, args=(i, task))
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=60)

    lines = []
    for i in sorted(results.keys()):
        lines.append('worker' + str(i) + ': ' + results[i][:200])
    for i in sorted(errors.keys()):
        lines.append('worker' + str(i) + ' error: ' + errors[i][:100])
    return chr(10).join(lines) if lines else 'all timed out'


def _vote_spawn(params):
    """投票表决: task=任务 n=Agent数(默认3)
    开 n 个子Agent独立决策, 融合结果返回 (值, 信度)
    """
    task = ''
    n = 3
    for line in (params or '').splitlines():
        line = line.strip()
        if line.startswith('task='):
            task = line[5:]
        elif line.startswith('n='):
            try:
                n = int(line[2:])
            except Exception:
                pass
    if not task:
        return 'missing task='

    results = []
    for i in range(n):
        name = 'voter_' + str(i)
        r = _spawn_sub_agent('name=' + name + chr(10) + 'task=' + task)
        results.append(r)

    # 提取 (值, 信度) 从每个结果
    import re

    values = []
    confs = []
    for r in results:
        # 解析 TritValue 输出: '=> 1（三进制: +）' or '=> -1（三进制: -）'
        m = re.search(r'=>\s*(-?\d+)', str(r))
        c = re.search(r'信度[=:：]\s*([0-9.]+)', str(r))
        if m:
            values.append(int(m.group(1)))
            confs.append(float(c.group(1)) if c else 0.5)
    if not values:
        return 'vote failed: no valid results from ' + str(n) + ' agents'

    # 融合: Kleene logic
    has_pos = any(v == 1 for v in values)
    has_neg = any(v == -1 for v in values)
    has_maybe = any(v == 0 for v in values)

    # 归一化: >0→真(1), <0→假(-1), =0→可能(0)
    trit_values = []
    for v in values:
        if v > 0:
            trit_values.append(1)
        elif v < 0:
            trit_values.append(-1)
        else:
            trit_values.append(0)

    has_pos = any(v == 1 for v in trit_values)
    has_neg = any(v == -1 for v in trit_values)
    has_maybe = any(v == 0 for v in trit_values)

    if has_pos and not has_neg and not has_maybe:
        fused = 1  # all agree true
        conf = min(confs)
    elif has_neg and not has_pos and not has_maybe:
        fused = -1  # all agree false
        conf = min(confs)
    else:
        fused = 0  # mixed or has maybe
        conf = sum(confs) / len(confs) if confs else 0.5

    trues = sum(1 for v in trit_values if v == 1)
    falses = sum(1 for v in trit_values if v == -1)
    return (
        'vote('
        + str(n)
        + ' agents): '
        + str(trues)
        + ' true, '
        + str(falses)
        + ' false -> fused='
        + str(fused)
        + ' conf='
        + str(round(conf, 2))
    )
