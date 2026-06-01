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

os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')

from ops.registry import register_alias

register_alias('转字符串', 'to_string')
register_alias('转JSON', 'to_json')
register_alias('解析JSON', 'from_json')
register_alias('时间戳', 'timestamp')
register_alias('字符串包含', 'str_contains')
register_alias('表长', 'list_len')
register_alias('字符串相等', 'str_equals')
register_alias('是字典', 'is_dict')
register_alias('是列表', 'is_list')
register_alias('是字符串', 'is_string')
register_alias('连接', 'concat')
register_alias('取长', 'length')
register_alias('子串', 'substring')
register_alias('查找', 'find')
register_alias('分割', 'split')
register_alias('包含', 'contains')
register_alias('字典键列表', 'dict_keys')
register_alias('含键', 'dict_contains')
register_alias('置键', 'set_key')
register_alias('取键', 'get_key')
register_alias('删除键', 'delete_key')
register_alias('列表合', 'list_concat')
register_alias('取', 'get')
register_alias('不', 'not')
register_alias('读文件', 'read_file')
register_alias('写文件', 'write_file')
register_alias('转数字', 'to_number')

from sugar.parser import parse_code
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache
from preprocess import preprocess_includes


def load_api_key():
    """从环境变量或 agent_policy.san 读取 API 密钥。"""
    env_key = os.environ.get('SANYAN_API_KEY', '')
    if env_key:
        return env_key
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
    return ''


def init_evaluator(api_key):
    clear_cache()
    evaluator = SanyanEvaluator(max_loop_steps=500000)

    agent_path = os.path.join('ternary_agent', 'agent.san')
    src = open(agent_path, encoding='utf-8').read()
    # 预处理 #include 展开 + API key 注入
    src = preprocess_includes(src)
    src = src.replace('sk-你的key', api_key)
    ast, _ = parse_code(src)
    fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
    evaluator.eval(['do'] + fixed)
    return evaluator


def run_once(evaluator, question):
    evaluator.eval(['Agent运行', question])
    try:
        evaluator.eval(['保存记忆'])
    except Exception:
        pass


def _watch_files():
    """返回当前策略文件的修改时间戳字典。"""
    agent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ternary_agent')
    return {
        'agent.san': os.path.getmtime(os.path.join(agent_dir, 'agent.san')),
        'agent_policy.san': os.path.getmtime(os.path.join(agent_dir, 'agent_policy.san')),
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
