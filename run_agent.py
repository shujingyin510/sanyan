"""三言 Agent 启动器 - 支持单次/多轮对话
用法:
    python -X utf8 run_agent.py                     # 多轮对话
    python -X utf8 run_agent.py "你的问题"           # 单次提问

    设置 API 密钥（二选一）:
    set SANYAN_API_KEY=sk-xxx
    或修改 ternary_agent/agent_policy.san 中的 API密钥
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__)) or '.'
os.chdir(PROJECT_ROOT)

from sugar.parser import parse_code
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache
from preprocess import preprocess_includes


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

    # 注册 write_code 工具所需的 Python 函数
    from ops.registry import register as reg_op
    def _new_evaluator(e, args):
        """创建新的沙箱求值器实例"""
        e2 = SanyanEvaluator(max_loop_steps=100000)
        # 返回一个可以被 san 代码引用的对象
        tag = f'_sandbox_{id(e2)}'
        e.set_var(tag, e2)
        return tag

    def _sandbox_eval(e, args):
        """在沙箱中求值代码，返回结果"""
        sandbox_tag = str(e.eval(args[0])) if args else ''
        code = str(e.eval(args[1])) if len(args) > 1 else ''
        sandbox = e.get_var(sandbox_tag) if e.has_var(sandbox_tag) else None
        if sandbox is None:
            return '沙箱未初始化'
        try:
            if code.strip().startswith('('):
                from lexer import tokenize
                from parser import parse
                tokens = tokenize(code)
                sexpr = parse(tokens)
                if sexpr is not None:
                    remaining = parse(tokens)
                    if remaining is not None:
                        sexpr = ['做', sexpr] + [remaining]
                        more = parse(tokens)
                        while more is not None:
                            sexpr.append(more)
                            more = parse(tokens)
                    result = sandbox.eval(sexpr)
                    return str(result.to_int() if hasattr(result, 'to_int') else result)
            from sugar.parser import parse_code as pc
            ast2, _ = pc(code)
            result = None
            for stmt2 in (ast2[1:] if isinstance(ast2, list) and len(ast2) > 1 else []):
                try:
                    result = sandbox.eval(stmt2)
                except Exception as ex:
                    return str(ex)
            return str(result.to_int() if hasattr(result, 'to_int') else result) if result is not None else 'nil'
        except Exception as ex:
            return str(ex)

    reg_op('新求值器', _new_evaluator)
    reg_op('求值', _sandbox_eval)
    reg_op('sandbox_eval', _sandbox_eval)

    agent_path = os.path.join('ternary_agent', 'agent.san')
    src = open(agent_path, encoding='utf-8').read()
    # 预处理 #include 展开
    src = preprocess_includes(src)
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
            tokens = tokenize(q)
            sexpr = parse(tokens)
            if sexpr is not None:
                remaining = parse(tokens)
                if remaining is not None:
                    sexpr = ['做', sexpr] + [remaining]
                    more = parse(tokens)
                    while more is not None:
                        sexpr.append(more)
                        more = parse(tokens)
                result = evaluator.eval(sexpr)
                print(f'= {result}')
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
    api_key = load_api_key()
    if not api_key or '你的' in api_key:
        print('请设置 API 密钥：set SANYAN_API_KEY=sk-xxx')
        sys.exit(1)

    evaluator = init_evaluator(api_key)

    if len(sys.argv) > 1:
        run_once(evaluator, sys.argv[1])
    else:
        run_interactive(evaluator, api_key)


if __name__ == '__main__':
    main()
