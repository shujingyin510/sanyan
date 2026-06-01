"""桃花村 v2.0 — 时间+日程+天气 自动演示"""

import os
import builtins

os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')

from sugar.parser import parse_code
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache

clear_cache()

def _register_aliases():
    """注册中文别名（必须在 SanyanEvaluator 实例化之后调用）"""
    from ops.registry import register_alias
    aliases = [
        ('转字符串', 'to_string'), ('转JSON', 'to_json'), ('解析JSON', 'from_json'),
        ('字符串包含', 'str_contains'), ('表长', 'list_len'), ('字符串相等', 'str_equals'),
        ('是字典', 'is_dict'), ('连接', 'concat'), ('取长', 'length'),
        ('子串', 'substring'), ('包含', 'contains'), ('字典键列表', 'dict_keys'),
        ('含键', 'dict_contains'), ('置键', 'set_key'), ('取键', 'get_key'),
        ('删除键', 'delete_key'), ('列表合', 'list_concat'), ('取', 'get'),
        ('不', 'not'), ('读文件', 'read_file'), ('写文件', 'write_file'),
    ]
    for a, t in aliases:
        try:
            register_alias(a, t)
        except Exception:
            pass

steps = [
    ('送苹果', '见面礼'),
    ('送花', '再送花'),
    ('铁匠', '去铁匠铺'),
    ('送酒', '送酒 — 时间推进'),
    ('帮忙', '帮忙 — 时间推进'),
    ('村长', '去村长家'),
    ('你好', '打招呼 — 时段变化'),
    ('刘嫂', '找刘嫂'),
    ('你好', '打招呼'),
    ('状态', '查看全村'),
    ('睡觉', '过夜 — 新一天新天气'),
    ('猎户', '早晨找猎户'),
    ('送肉', '送猎物'),
    ('小贩', '去村口'),
    ('你好', '打招呼'),
    ('状态', '查看'),
    ('睡觉', '过夜'),
    ('郎中', '早晨找郎中'),
    ('送苹果', '送礼 — 时段推进'),
    ('睡觉', '过夜 — 可能下雨'),
    ('老王', '早晨回老王家'),
    ('你好', '下雨天打招呼'),
    ('状态', '查看天氣影響'),
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
_register_aliases()  # 注册中文别名（必须在 evaluator 实例化之后）
src = open('ternary_agent/runtime_v2/village_game.san', encoding='utf-8').read()
ast, _ = parse_code(src)
fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
e.eval(['do'] + fixed)
