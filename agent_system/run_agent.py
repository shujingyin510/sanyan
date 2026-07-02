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
    或修改 agent_system/sanyan/agent_policy.san 中的 API密钥
"""

import sys
import os
import argparse
import sqlite3
import json
import time as _time

# 仓库根（run_agent.py 已迁入 agent_system/）：本文件内相对路径均以仓库根为基准
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

from sugar.parser import parse_code
from core.evaluator import SanyanEvaluator
from ops.file_ops import clear_cache
from core.preprocess import preprocess_includes


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
    # 优先级: 环境（单一 typed 配置，占位符视为空）> agent_policy.san > village_config.san
    from agent_system.config import api_key_from_env

    key = api_key_from_env()
    if key:
        return key
    # 在 agent.san（含 #include 展开）中查找 API密钥
    agent_path = os.path.join('agent_system', 'sanyan', 'agent.san')
    with open(agent_path, encoding='utf-8') as f:
        src = f.read()
    src = preprocess_includes(src)
    for line in src.split('\n'):
        if 'API密钥' in line and '=' in line and 'sk-' in line:
            key = line.split('"')[1] if '"' in line else ''
            if key and '你的' not in key:
                return key
    # 尝试从 village_config.san 读取（游戏用的密钥文件）
    village_cfg = os.path.join('agent_system', 'sanyan', 'runtime_v2', 'village_config.san')
    if os.path.exists(village_cfg):
        with open(village_cfg, encoding='utf-8') as f:
            for line in f:
                if 'API密钥' in line or '密钥' in line:
                    key = line.split('"')[1] if '"' in line else ''
                    if key and '你的' not in key and key.startswith('sk-'):
                        return key
    return ''


_agent_hooks_registered = False


def init_evaluator(api_key):
    """幂等初始化: 第二次调用只重建evaluator,跳过重复注册"""
    global _agent_hooks_registered
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

    # 注册 write_code 工具所需的 Python 函数（仅首次）
    if _agent_hooks_registered:
        return evaluator
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

    def _spawn_sub_agent_hook(e, args):
        """调度子Agent: LLM模式(有key) 或 代码模式"""
        params = str(e.eval(args[0])) if args else ''
        task = ''
        name = 'sub'
        for line in params.splitlines():
            line = line.strip()
            if line.startswith('task='):
                task = line[5:]
            elif line.startswith('name='):
                name = line[5:]
        if not task:
            return 'missing task='

        # 代码模式: 以 ( 开头
        if task.strip().startswith('('):
            from agent_system.agent_tools import _spawn_sub_agent

            return _spawn_sub_agent(params)

        # LLM 模式: 需要 API key
        if not api_key or '你的key' in api_key:
            return 'LLM mode needs valid API key'

        from agent_system.agent_tools import _agent_registry

        _agent_registry[name] = {'status': 'running', 'task': task, 'result': None}

        import io
        import sys

        sys.path.insert(0, '.')
        from core.evaluator import SanyanEvaluator
        from ops.file_ops import clear_cache
        from core.preprocess import preprocess_includes
        from sugar.parser import parse_code
        import os as _os

        try:
            clear_cache()
            sub_ev = SanyanEvaluator(max_loop_steps=300000)
            _os.environ['SANYAN_API_KEY'] = api_key

            # 加载 agent.san + 最小工具集到子求值器
            # 注册中文别名（Agent需要）
            _register_aliases()
            # 注册子Agent基础工具
            from ops.registry import register as _reg_op

            def _sub_read_file(ev, a):
                path = str(ev.eval(a[0])) if a else ''
                try:
                    with open(path, encoding='utf-8') as fh:
                        content = fh.read()
                    return content[:3000]
                except Exception as ex:
                    return 'read error: ' + str(ex)

            def _sub_write_file(ev, a):
                params = str(ev.eval(a[0])) if a else ''
                parts = params.split('|', 1)
                if len(parts) < 2:
                    return 'need path|content'
                try:
                    with open(parts[0], 'w', encoding='utf-8') as fh:
                        fh.write(parts[1])
                    return 'written ' + str(len(parts[1])) + ' bytes'
                except Exception as ex:
                    return 'write error: ' + str(ex)

            def _sub_search(ev, a):
                pattern = str(ev.eval(a[0])) if a else ''
                import glob

                files = glob.glob('**/*' + pattern + '*', recursive=True)[:20]
                return chr(10).join(files) if files else 'no match'

            def _sub_analyze(ev, a):
                path = str(ev.eval(a[0])) if a else ''
                try:
                    with open(path, encoding='utf-8') as fh:
                        content = fh.read()
                    lines = len(content.splitlines())
                    return path + ': ' + str(lines) + ' lines'
                except Exception as ex:
                    return 'analyze error: ' + str(ex)

            _reg_op('读文件钩子', _sub_read_file)
            _reg_op('写文件钩子', _sub_write_file)
            _reg_op('搜代码钩子', _sub_search)
            _reg_op('分析文件', _sub_analyze)
            _reg_op('列出Agent', lambda ev, a: 'sub-agent tools: read, write, search, analyze')

            agent_path = _os.path.join('agent_system', 'sanyan', 'agent.san')
            src = open(agent_path, encoding='utf-8').read()
            src = preprocess_includes(src)
            ast, _ = parse_code(src)
            fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
            sub_ev.eval(['do'] + fixed)

            # 捕获子 Agent 输出
            old = sys.stdout
            sys.stdout = io.StringIO()
            try:
                sub_ev.eval(['Agent运行', task])
            finally:
                out = sys.stdout.getvalue()
                sys.stdout = old

            # 置信度衰减检测 (严格单调递减 + 窗口检测)
            import re
            from agent_system.agent_tools import _AGENT_CONF_WINDOW, _AGENT_CONF_FLOOR, _classify_failure

            confs = [float(m) for m in re.findall(r'信度[=:\uff1a]\s*([0-9.]+)', out)]
            rounds = re.findall(r'第\s*(\d+)\s*轮', out)
            win = _AGENT_CONF_WINDOW
            if len(confs) >= max(win, 2):
                recent = confs[-win:]
                # 严格单调递减: 每一项 >= 后一项
                drop = all(recent[i] > recent[i + 1] for i in range(len(recent) - 1))
                if drop and recent[-1] < _AGENT_CONF_FLOOR:
                    reason = _classify_failure(out, rounds, confs)
                    _agent_registry[name] = {
                        'status': 'capped',
                        'task': task,
                        'result': 'confidence drop ' + str(recent) + ' reason:' + reason,
                        'failure_reason': reason,
                        'start_time': _time.time(),
                    }
                    return '[Agent ' + name + '] degraded ' + reason + ', restart'

            # 兜底: 轮次过多 (用配置值)
            max_r = max([int(r) for r in rounds]) if rounds else 0
            if max_r >= 6:
                reason = _classify_failure(out, rounds, confs)
                return '[Agent ' + name + '] round ' + str(max_r) + ', ' + reason + ', capped'

            result = out.strip()[:1000] if out.strip() else 'no output'
            _agent_registry[name] = {'status': 'done', 'task': task, 'result': result}
            return '[Agent ' + name + '] ' + result
        except Exception as ex:
            _agent_registry[name] = {'status': 'error', 'task': task, 'result': str(ex)}
            return '[Agent ' + name + '] error: ' + str(ex)[:300]

    def _agent_message_hook(e, args):
        from agent_system.agent_tools import _agent_message

        return _agent_message(str(e.eval(args[0])) if args else '')

    def _agent_list_hook(e, args):
        from agent_system.agent_tools import _agent_list

        return _agent_list(str(e.eval(args[0])) if args else '')

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
                prefix = f'[{start + 1}-{end}] '
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

            results: list[str] = []
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
                result += '\n  ... 结果已截断 (共 25 条)'
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
                capture_output=True,
                text=True,
                timeout=60,
                cwd=_os.path.dirname(_os.path.abspath(__file__)) or '.',
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
            r = _sp.run(
                ['git', 'diff', '--stat'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=os.path.dirname(os.path.abspath(__file__)) or '.',
            )
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
            r = _sp.run(
                ['git', 'status', '--short'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=os.path.dirname(os.path.abspath(__file__)) or '.',
            )
            output = r.stdout.strip() or '(工作区干净)'
            return output
        except Exception as ex:
            return f'git status 失败: {ex}'

    def _save_task_hook(e, args):
        """保存任务状态到 SQLite"""
        mem = {}
        if e.has_var('_任务记忆'):
            raw = e.get_var('_任务记忆')
            if hasattr(raw, 'to_payload'):
                raw = raw.to_payload()
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
        prefixed = os.path.join('agent_system', 'sanyan', path)
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
        big_funcs = [d for d in defs if '行)' in d and int(d.split('(')[-1].replace('行)', '').replace('行', '')) > 50]
        if big_funcs:
            summary += f'\n⚠ >50行: {", ".join(d.split(" :")[0].replace("def ", "") for d in big_funcs)}'
        summary += '\n'
        return summary + '\n'.join([*defs[:15], '---', *imps[:8]])

    def _find_symbol(e, args):
        """查找符号定义和引用"""
        symbol = str(e.eval(args[0])) if args else ''
        if not symbol:
            return '请指定符号名'
        import glob as _glob

        results: list[str] = []
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
            from core.lexer import tokenize
            from core.parser import parse

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

    def _run_assembly_hook(e, args):
        "write assembly and run"
        source = str(e.eval(args[0])) if args else ''
        if not source:
            return 'provide assembly source'
        import os
        import io
        import sys

        os.makedirs('build', exist_ok=True)
        try:
            from compiler.asm import Assembler

            a = Assembler()
            data = a.build(source)
            out_path = 'build/agent_asm.bin'
            with open(out_path, 'wb') as f:
                f.write(data)
            result = f'asm OK: {len(data)}B, {a.var_count} vars'
            from vm import VM

            old = sys.stdout
            sys.stdout = io.StringIO()
            VM.from_bin(out_path).run()
            out = sys.stdout.getvalue()
            sys.stdout = old
            if out.strip():
                result += ' output: ' + out.strip()
        except Exception as ex:
            result = f'asm FAIL: {ex}'
        return result

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
    reg_op('运行汇编', _run_assembly_hook)

    agent_path = os.path.join('agent_system', 'sanyan', 'agent.san')
    src = open(agent_path, encoding='utf-8').read()
    # 预处理 #include 展开
    src = preprocess_includes(src)
    # 新提示词已内置完整语法，不再注入 markdown 文档
    # 密钥不入源码文本（泄露面）：本函数开头已 setenv，.san 侧经 环境变量("SANYAN_API_KEY") 读取
    ast, _ = parse_code(src)
    fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
    evaluator.eval(['do'] + fixed)
    _agent_hooks_registered = True
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
            from core.lexer import tokenize
            from core.parser import parse

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
    agent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_system', 'sanyan')
    return {
        'agent.san': os.path.getmtime(os.path.join(agent_dir, 'agent.san')),
        'agent_policy.san': os.path.getmtime(os.path.join(agent_dir, 'agent_policy.san')),
        'decision.san': os.path.getmtime(os.path.join(agent_dir, 'decision.san')),
    }


def run_interactive(evaluator, api_key, rt=None):
    """交互模式 — V5 AgentRuntime 驱动"""
    print('三言 Agent V5 - 多轮对话（输入 exit 退出）')
    print('  /状态 → 三态决策摘要')
    print('  /记忆 → 任务记忆')
    print('  /仪表盘 → 实时仪表盘')
    print('  /追踪 → 决策链可视化')
    print('  /性能 → 性能报告')
    print('  /经验 → 跨会话经验')
    print('  /安全 → 安全沙箱状态')
    print('  /共享 → 共享上下文')
    print('  /管道 → 工具管道列表')
    print()
    round_num = 0
    while True:
        round_num += 1
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
        if q.startswith('/状态'):
            print(f'  三态: {rt.ternary.summary()}' if rt else '  无引擎')
            continue
        if q.startswith('/记忆'):
            print(f'  阶段: {rt.memory.get("stage", "?")}' if rt else '')
            print(f'  修改: {rt.memory.get("modified", [])}' if rt else '')
            continue
        if q.startswith('/仪表盘') or q.startswith('/dashboard'):
            print(rt.get_dashboard() if rt else '  无引擎')
            continue
        if q.startswith('/追踪') or q.startswith('/trace'):
            print(rt.visualize_trace() if rt else '  无引擎')
            continue
        if q.startswith('/性能') or q.startswith('/perf'):
            print(rt.get_performance_report() if rt else '  无性能数据')
            continue
        if q.startswith('/经验') or q.startswith('/exp'):
            if rt and rt.experience_store:
                top_tools = rt.experience_store.get_top_tools(limit=5)
                print('  最可靠工具:')
                for tool, score in top_tools:
                    print(f'    {tool}: {score:.2f}')
                patterns = rt.experience_store.get_failure_patterns(limit=3)
                if patterns:
                    print('  常见失败:')
                    for p in patterns:
                        print(f'    {p["tool"]}: {p["error"][:40]} (x{p["count"]})')
            continue
        if q.startswith('/安全') or q.startswith('/sandbox'):
            print(rt.security_sandbox.summary() if rt else '  无沙箱')
            continue
        if q.startswith('/共享') or q.startswith('/shared'):
            if rt and rt.shared_context:
                print(rt.shared_context.summary())
            continue
        if q.startswith('/管道') or q.startswith('/pipeline'):
            if rt and rt.pipeline:
                pipelines = rt.pipeline.list_pipelines()
                print('  已定义管道:' if pipelines else '  (无管道)')
                for p in pipelines:
                    print(f'    - {p}')
            continue
        try:
            result = rt.run(q, max_rounds=15)
            print(f'→ {result["answer"]}')
        except Exception as e:
            print(f'错误: {e}')
        print()


# ====== 任务持久化 (SQLite) ======

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)) or '.', 'agent_state.db')


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT, status TEXT DEFAULT 'running',
        created_at REAL, updated_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS task_memory (
        task_id INTEGER, key TEXT, value TEXT, PRIMARY KEY (task_id, key)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS tool_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER, round_num INTEGER, tool TEXT, params TEXT, result TEXT, timestamp REAL
    )""")
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
    conn.commit()
    conn.close()


def _create_task(description):
    conn = sqlite3.connect(DB_PATH)
    now = _time.time()
    cur = conn.execute(
        'INSERT INTO tasks (description, status, created_at, updated_at) VALUES (?,?,?,?)',
        (description, 'running', now, now),
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return task_id


def _finish_task(task_id, status='completed'):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE tasks SET status=?, updated_at=? WHERE id=?', (status, _time.time(), task_id))
    conn.commit()
    conn.close()


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
    row = conn.execute(
        "SELECT id, description FROM tasks WHERE status='running' ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
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


# ====== AgentRuntime V3 导入 ======
from agent_system.agent_runtime import AgentRuntime
from agent_system.agent_tools import (
    _analyze_file_direct,
    _find_symbol_direct,
    _read_file_direct_simple,
    _search_code_direct,
    _replace_in_file_direct,
    _replace_all_direct,
    _write_file_direct_simple,
    _list_files_direct_simple,
    _run_test_direct,
    _run_shell_direct,
    _git_diff_direct,
    _git_status_direct,
    _git_stash_direct,
    _git_reset_hard_direct,
    _git_commit_auto_direct,
)
from agent_system.agent_evolution import ConstrainedEvolutionSystem
from agent_system.agent_review import (
    ReviewedEvolutionLoop,
    EvolutionDashboard,
)
from agent_system.agent_validation import EvolutionValidation
from agent_system.agent_metaconfig import MetaConfigSystem
# ======  End AgentRuntime imports ======


def _save_execution_log(path: str, task: str, result: dict, rt):
    """保存执行日志到文件"""
    import datetime

    lines = [
        '=== Agent 执行日志 ===',
        f'时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'任务: {task}',
        '',
        '=== 执行历史 ===',
    ]

    memory = result.get('memory', {})
    history = memory.get('history', [])

    for i, entry in enumerate(history, 1):
        tool = entry.get('tool', 'unknown')
        params = entry.get('params', '')
        result_str = entry.get('result', '')
        duration = entry.get('duration', 0)
        trit = entry.get('trit', 0)

        status = '✓' if trit == 1 else '✗' if trit == -1 else '○'
        lines.append(f'[r{i}] {status} {tool} ({duration:.1f}s)')
        if params:
            lines.append(f'  参数: {params[:100]}')
        if result_str:
            lines.append(f'  结果: {result_str[:200]}')
        lines.append('')

    lines.append('=== 结果 ===')
    lines.append(f'答案: {result.get("answer", "无")}')
    lines.append(f'修改文件: {", ".join(memory.get("modified", []))}')

    # 性能报告
    lines.append('')
    lines.append('=== 性能 ===')
    lines.append(rt.get_performance_report())

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'[日志] 已保存到: {path}')


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
    parser.add_argument('--dashboard', action='store_true', help='显示实时仪表盘')
    parser.add_argument('--trace', action='store_true', help='显示决策追踪')
    parser.add_argument('--log', type=str, default='', help='保存执行日志到文件')
    parser.add_argument('--perf', action='store_true', help='显示性能报告')
    parser.add_argument('--sandbox', action='store_true', help='启用安全沙箱（只读模式）')
    parser.add_argument('--parallel', action='store_true', help='启用并行执行')
    parser.add_argument('--stream', action='store_true', help='启用流式输出')
    parser.add_argument('--pipeline', type=str, default='', help='执行工具管道')
    parser.add_argument('--evolve', action='store_true', help='运行约束进化验证')
    parser.add_argument('--self-host', action='store_true', help='运行自举验证')
    parser.add_argument('--auto-evolve', action='store_true', help='运行自动化进化闭环')
    parser.add_argument('--code-evolve', action='store_true', help='Agent自主改代码闭环')
    parser.add_argument('--review-evolve', action='store_true', help='带审查的进化闭环')
    parser.add_argument('--learn', action='store_true', help='从git历史批量学习项目风格')
    parser.add_argument('--approve-rule', action='store_true', help='审批待生成的规则')
    parser.add_argument('--reject-rule', action='store_true', help='拒绝待生成的规则')
    parser.add_argument('--list-rules', action='store_true', help='列出所有规则')
    parser.add_argument('--export-rules', type=str, default='', help='导出规则到文件')
    parser.add_argument('--import-rules', type=str, default='', help='从文件导入规则')
    parser.add_argument('--model', type=str, default='', help='指定模型 (deepseek-v4-pro/deepseek-coder/claude/gpt4)')
    parser.add_argument('--evo-dashboard', action='store_true', help='进化仪表盘')
    parser.add_argument('--validate', action='store_true', help='运行进化验证（100次随机+收敛+Reviewer）')
    parser.add_argument('--metaconfig', action='store_true', help='MetaConfig进化（配置参数验证）')
    parser.add_argument('--max-cycles', type=int, default=3, help='最大进化轮次')
    args = parser.parse_args()

    # 三言代码：直接执行，跳过 Agent 和 LLM
    if args.question:
        q = args.question.strip()
        if q.startswith('(') or '(设' in q or '(循环' in q or '(输出' in q or '(加' in q:
            from core.lexer import tokenize
            from core.parser import parse
            from core.evaluator import SanyanEvaluator

            e = SanyanEvaluator(max_loop_steps=50000)
            try:
                # 括号匹配提取所有顶层表达式
                exprs = _extract_exprs(q)
                if not exprs:
                    exprs = [q]
                from core.lexer import tokenize
                from core.parser import parse

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

    # 统一引擎：AgentRuntime V5（--auto 和非 auto 都走这里）
    sandbox = evaluator.get_var('_sandbox') if evaluator.has_var('_sandbox') else None
    rt = AgentRuntime(evaluator, sandbox)

    # Phase 3: 配置安全沙箱
    if args.sandbox:
        rt.security_sandbox.read_only = True
        print('  [沙箱模式] 只读，禁止文件修改')

    # 注册工具
    for name, func in [
        ('analyze', lambda p, d: _analyze_file_direct(p)),
        ('find_symbol', lambda p, d: _find_symbol_direct(p)),
        ('read_file', lambda p, d: _read_file_direct_simple(p)),
        ('search_code', lambda p, d: _search_code_direct(p)),
        ('replace_in_file', lambda p, d: _replace_in_file_direct(p, d)),
        ('replace_all', lambda p, d: _replace_all_direct(p, d)),
        ('write_file', lambda p, d: _write_file_direct_simple(p, d)),
        ('list_files', lambda p, d: _list_files_direct_simple(p)),
        ('run_test', lambda p, d: _run_test_direct(p, d)),
        ('run_shell', lambda p, d: _run_shell_direct(p, d)),
        ('git_diff', lambda p, d: _git_diff_direct()),
        ('git_status', lambda p, d: _git_status_direct()),
        ('git_stash', lambda p, d: _git_stash_direct()),
        ('git_reset_hard', lambda p, d: _git_reset_hard_direct()),
        ('git_commit_auto', lambda p, d: _git_commit_auto_direct(p)),
        ('done', lambda p, d: p if p else '完成'),
    ]:
        rt.register(name, func)

    # Phase 3: 同步工具到并行执行器
    rt.parallel_executor.tools = rt.tools

    max_r = args.rounds or 15

    # Phase 3: 显示仪表盘
    if args.dashboard:
        print(rt.get_dashboard())
        return

    # Phase 3: 显示追踪
    if args.trace:
        print(rt.visualize_trace())
        return

    # Phase 3: 显示性能报告
    if args.perf:
        print(rt.get_performance_report())
        return

    # 批量学习
    if args.learn:
        print('从 git 历史批量学习项目风格...')
        output_path = rt.batch_learn_from_git()
        if output_path:
            print(f'\n风格已保存到: {output_path}')
        return

    # 规则管理
    if args.approve_rule:
        if rt.rule_engine.approve_rule():
            print('规则已审批通过并保存')
        else:
            print('没有待审批的规则')
        return

    if args.reject_rule:
        if rt.rule_engine.reject_rule():
            print('规则已拒绝')
        else:
            print('没有待审批的规则')
        return

    if args.list_rules:
        print(rt.rule_engine.get_rules_summary())
        return

    # 规则导出导入
    if args.export_rules:
        from agent_system.project_migrator import export_project_rules

        output = export_project_rules(args.export_rules)
        print(f'规则已导出到: {output}')
        return

    if args.import_rules:
        from agent_system.project_migrator import import_project_rules

        result = import_project_rules(args.import_rules)
        print('导入结果:')
        print(f'  规则: {result["rules_imported"]} 条')
        print(f'  模板: {result["templates_imported"]} 个')
        print(f'  学习记录: {"是" if result["styles_imported"] else "否"}')
        if result['errors']:
            print(f'  错误: {result["errors"]}')
        return

    # Layer 3: 约束进化验证
    if args.evolve:
        evo = ConstrainedEvolutionSystem()
        print('运行约束进化验证...')
        result = evo.propose_and_verify('vm/__init__.py', 'VM._dispatch', '优化分派逻辑')
        print(f'\n状态: {result["status"]}')
        if result['status'] == 'accepted':
            print(f'一致性: {result["verification"]["consistency_rate"]:.1%}')
            print(f'综合得分: {result["evaluation"]["total_score"]:.2f}')
        else:
            print(f'原因: {result.get("reason", "未通过验证")}')
        print(evo.summary())
        return

    # Layer 3: 自举验证
    if args.self_host:
        evo = ConstrainedEvolutionSystem()
        print('运行自举验证...')
        result = evo.run_self_host_check()
        print(f'\n结果: {"通过" if result["success"] else "失败"}')
        print(f'字节码编译器: {"通过" if result["bytecode_compiler"]["success"] else "失败"}')
        print(f'VM一致性: {result["vm_consistency"]["consistent"]}/{result["vm_consistency"]["total"]}')
        return

    # Layer 3: 自动化进化闭环
    if args.auto_evolve:
        evo = ConstrainedEvolutionSystem()
        result = evo.run_evolution(max_cycles=args.max_cycles or 3)
        print(evo.summary())
        return

    # Layer 3: Agent自主改代码闭环
    if args.code_evolve:
        from agent_system.agent_evolution_v2 import AgentCodeModifier

        modifier = AgentCodeModifier()
        result = modifier.run_evolution_loop(max_cycles=args.max_cycles or 3)
        print(modifier.summary())
        return

    # Layer 3: 带审查的进化闭环
    if args.review_evolve:
        loop = ReviewedEvolutionLoop()
        # 测试补丁
        test_patches = [
            {
                'target': 'vm/__init__.py',
                'action': 'replace',
                'before': 'old code',
                'after': 'new code',
                'rationale': '缓存优化：减少重复计算',
                'expected': '提升5-10%',
            },
            {
                'target': 'core/ternary_core.py',
                'action': 'replace',
                'before': 'old code',
                'after': 'new code',
                'rationale': '循环优化：减少迭代次数',
                'expected': '减少10-20%耗时',
            },
        ]
        result = loop.run(test_patches)
        print(f'\n结果: 接受{result["accepted"]} 拒绝{result["rejected"]} 回滚{result["rolled_back"]}')
        print(loop.summary())
        return

    # 进化仪表盘
    if args.evo_dashboard:
        dashboard = EvolutionDashboard()
        print(dashboard.render())
        return

    # 进化验证
    if args.validate:
        validator = EvolutionValidation()
        report = validator.run_all(
            n_random=100,
            n_convergence=20,
            n_reviewer=100,
            n_meta=5,
        )
        validator.print_report(report)
        return

    # MetaConfig进化
    if args.metaconfig:
        from agent_system.agent_metaconfig import TaskReplay

        system = MetaConfigSystem()

        # 先记录一些历史任务
        replay = TaskReplay()
        for i in range(30):
            replay.record_task(f'task_{i}', ['analyze', 'read_file'], success=True, duration=1.0, tokens=100)

        # 运行多个配置变更
        proposals = [
            {'parameter': 'cooldown_seconds', 'new_value': 15, 'reason': '减少等待时间'},
            {'parameter': 'tournament_candidates', 'new_value': 4, 'reason': '增加候选数量'},
            {'parameter': 'max_lines_changed', 'new_value': 25, 'reason': '允许更大变更'},
        ]
        result = system.run(proposals)
        print(f'\n结果: 接受{result["accepted"]} 拒绝{result["rejected"]} 未知{result["unknown"]}')
        print(system.summary())
        return

    if args.question:
        # 设置日志文件
        log_path = args.log if args.log else ''

        result = rt.run(args.question, max_rounds=max_r, dry_run=args.dry_run)
        print(f'\n→ {result["answer"]}')

        # 保存执行日志
        if log_path:
            import datetime

            if os.path.isdir(log_path):
                log_path = os.path.join(log_path, f'agent_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
            _save_execution_log(log_path, args.question, result, rt)
        if args.report:
            m = result['memory']
            print(f'\n=== 报告 ===\n阶段: {m["stage"]}\n工具: {len(m["history"])}次\n修改: {m["modified"]}')
            # Phase 3: 显示性能摘要
            print('\n=== 性能摘要 ===')
            print(rt.get_performance_report())
            # Phase 3: 显示安全摘要
            print('\n=== 安全摘要 ===')
            print(rt.security_sandbox.summary())
    else:
        run_interactive(evaluator, api_key, rt)  # V5 引擎


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
        print(f'  工具调用: {len(history)} 次' if hasattr(history, '__len__') else '  工具调用: ? 次')
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
