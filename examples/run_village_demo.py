"""桃花村 v2.0 — 自动演示 / 手动 LLM 交互

用法:
    python -X utf8 run_village_demo.py           # 自动演示（30步）
    python -X utf8 run_village_demo.py --manual   # 手动 LLM 对话
    set LLM_KEY=你的key                          # LLM 模式需要
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os
import sys
import builtins

os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')

from sugar.parser import parse_code
from core.evaluator import SanyanEvaluator
from ops.file_ops import clear_cache
from core.values import ReturnException

clear_cache()


def _register_aliases():
    """注册中文别名（必须在 SanyanEvaluator 实例化之后调用）"""
    from ops.registry import register_alias

    aliases = [
        ('转字符串', 'to_string'),
        ('转JSON', 'to_json'),
        ('解析JSON', 'from_json'),
        ('字符串包含', 'str_contains'),
        ('表长', 'list_len'),
        ('字符串相等', 'str_equals'),
        ('是字典', 'is_dict'),
        ('连接', 'concat'),
        ('取长', 'length'),
        ('子串', 'substring'),
        ('包含', 'contains'),
        ('字典键列表', 'dict_keys'),
        ('含键', 'dict_contains'),
        ('置键', 'set_key'),
        ('取键', 'get_key'),
        ('删除键', 'delete_key'),
        ('列表合', 'list_concat'),
        ('取', 'get'),
        ('不', 'not'),
        ('读文件', 'read_file'),
        ('写文件', 'write_file'),
        ('切片', 'slice'),
        ('置元素', 'set_element'),
    ]

    for a, t in aliases:
        try:
            register_alias(a, t)
        except Exception:
            pass


def run_auto():
    """自动演示模式"""
    steps = [
        ('送苹果', '见面礼'),
        ('送花', '再送花'),
        ('铁匠', '去铁匠铺'),
        ('送酒', '送酒'),
        ('帮忙', '帮忙'),
        ('村长', '去村长家'),
        ('你好', '打招呼'),
        ('刘嫂', '找刘嫂'),
        ('你好', '打招呼'),
        ('状态', '查看全村'),
        ('睡觉', '过夜'),
        ('猎户', '找猎户'),
        ('送肉', '送猎物'),
        ('小贩', '去村口'),
        ('你好', '打招呼'),
        ('状态', '查看'),
        ('睡觉', '过夜'),
        ('郎中', '找郎中'),
        ('送苹果', '送礼'),
        ('睡觉', '过夜'),
        ('老王', '回老王家'),
        ('你好', '打招呼'),
        ('状态', '查看'),
        ('睡觉', '过夜'),
        ('睡觉', '又一天'),
        ('状态', '多天后'),
        ('退出', '结束'),
    ]
    test_iter = iter([s[0] for s in steps])

    def fake_input(prompt=''):
        try:
            cmd = next(test_iter)
            print(f'{prompt}\033[33m{cmd}\033[0m')
            return cmd
        except StopIteration:
            return '退出'

    builtins.input = fake_input

    e = SanyanEvaluator(max_loop_steps=999999)
    _register_aliases()
    src = open('agent_system/sanyan/runtime_v2/village_game.san', encoding='utf-8').read()
    ast, _ = parse_code(src)
    fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
    from core.values import ReturnException

    try:
        e.eval(['do'] + fixed)
    except ReturnException:
        pass  # 退出时正常结束


def run_manual():
    """手动交互模式（支持 LLM）"""
    e = SanyanEvaluator(max_loop_steps=999999)
    _register_aliases()

    # 直接读取配置（village_config.san 已包含 key）
    src = open('agent_system/sanyan/runtime_v2/village_game.san', encoding='utf-8').read()
    # 手动模式自动启用 LLM
    src = src.replace('设 LLM启用 = 假', '设 LLM启用 = 真')
    # 检查环境变量覆盖
    if os.environ.get('LLM_URL'):
        src = src.replace(
            '模型URL = "https://api.xiaomimimo.com/v1/chat/completions"', f'模型URL = "{os.environ["LLM_URL"]}"'
        )
    if os.environ.get('LLM_MODEL'):
        src = src.replace('模型名 = "mimo-v1"', f'模型名 = "{os.environ["LLM_MODEL"]}"')
    if os.environ.get('LLM_KEY'):
        src = src.replace('tp-你的key', os.environ['LLM_KEY'])

    ast, _ = parse_code(src)
    fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
    try:
        e.eval(['do'] + fixed)
    except ReturnException:
        pass

    key = os.environ.get('LLM_KEY', '')
    has_llm = key and '你的key' not in key
    print()
    print('  ══════════════════════════════════════')
    if has_llm:
        print('  桃花村 手动 LLM 对话模式')
        print(f'  模型: {os.environ.get("LLM_MODEL", "deepseek-v4-pro")}')
    else:
        print('  桃花村 手动规则模式')
        print('  设置 LLM_KEY 环境变量启用大模型')
        print('  命令: 老王/送苹果/你好/状态/睡觉/退出/启用LLM/开始观察')
    print('  ══════════════════════════════════════')
    print()

    while True:
        try:
            cmd = input('玩家 > ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not cmd:
            continue
        if cmd in ('退出', 'exit', 'quit'):
            try:
                e.eval(['显示状态'])
            except Exception:
                pass
            try:
                e.eval(['返回', 0])
            except Exception:
                pass
            break
        if cmd == '启用LLM':
            e.eval(['启用LLM'])
            continue
        if cmd == '禁用LLM':
            e.eval(['禁用LLM'])
            continue
        if cmd == '开始观察':
            e.eval(['开始观察'])
            continue
        # 村庄命令：直接调用
        if cmd in ('状态', '睡觉'):
            try:
                e.eval([cmd])
            except Exception as ex:
                print(f'  错误: {ex}')
            continue
        try:
            e.eval(['NPC对话', cmd])
            e.eval(['时间流逝'])
        except Exception as ex:
            print(f'  错误: {ex}')


if __name__ == '__main__':
    if '--manual' in sys.argv:
        run_manual()
    else:
        run_auto()
