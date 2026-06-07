"""三言 Agent 启动器 — 支持单次/多轮/自主模式
用法:
    python -X utf8 run_agent.py                        # 交互模式
    python -X utf8 run_agent.py "你的问题"              # 单次提问
    python -X utf8 run_agent.py "任务" --auto           # 自主模式，跑完为止
    python -X utf8 run_agent.py "任务" --auto --dry-run # 只读不改
    python -X utf8 run_agent.py "任务" --auto --rounds 3

    设置 API 密钥:
    set SANYAN_API_KEY=sk-xxx
    或修改 ternary_agent/agent_policy.san 中的 API密钥
"""

import sys, os, argparse

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
        """直接读取文件（用于 agent 工具调用）"""
        path = str(e.eval(args[0])) if args else ''
        if not path:
            return '请指定文件路径'
        try:
            with open(path, encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            if len(content) > 5000:
                content = content[:5000] + '\n...(已截断)'
            return content
        except FileNotFoundError:
            return f'文件不存在: {path}'
        except Exception as ex:
            return f'读文件错误: {ex}'

    def _write_file_direct(e, args):
        """直接写文件（用于 agent 工具调用），params 格式: 路径|内容"""
        raw = str(e.eval(args[0])) if args else ''
        parts = raw.split('|', 1)
        path = parts[0].strip() if parts else ''
        content = parts[1] if len(parts) > 1 else ''
        if not path:
            return '请指定文件路径（格式: 路径|内容）'
        try:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(content)
            return f'已写入: {path} ({len(content)} 字符)'
        except Exception as ex:
            return f'写文件错误: {ex}'

    def _replace_in_file(e, args):
        """替换文件内容并写回，params 格式: 路径|旧文字|新文字"""
        raw = str(e.eval(args[0])) if args else ''
        parts = raw.split('|', 2)
        path = parts[0].strip() if parts else ''
        old = parts[1] if len(parts) > 1 else ''
        new = parts[2] if len(parts) > 2 else ''
        if not path or not old:
            return '格式: 路径|旧文字|新文字'
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


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='三言 Agent — 可读决策 DSL + 自主编程助手')
    parser.add_argument('question', nargs='?', default='', help='任务描述（留空进入交互模式）')
    parser.add_argument('--auto', action='store_true', help='自主模式：不停轮直到完成')
    parser.add_argument('--rounds', type=int, default=0, help='最大轮次（覆盖策略配置）')
    parser.add_argument('--dry-run', action='store_true', help='只读不改，禁止文件写入')
    parser.add_argument('--report', action='store_true', help='完成后输出修改报告')
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

    api_key = load_api_key()
    if not api_key or '你的' in api_key:
        print('请设置 API 密钥：set SANYAN_API_KEY=sk-xxx')
        sys.exit(1)

    # --rounds 覆盖策略配置
    if args.rounds > 0:
        os.environ['AGENT_MAX_ROUNDS'] = str(args.rounds)

    evaluator = init_evaluator(api_key)

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
        print('  sanagent 任务报告')
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
