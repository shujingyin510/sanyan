"""三态 Agent Runtime v2 — 30天自动演示
每一步输入都会显示，像真人操作一样
"""

import os

os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')

from sugar.parser import parse_code
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache

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
        ('是列表', 'is_list'),
        ('连接', 'concat'),
        ('取长', 'length'),
        ('子串', 'substring'),
        ('查找', 'find'),
        ('分割', 'split'),
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


# ══════════════════════════════════════════
# 测试流程（每步带说明）
# ══════════════════════════════════════════
steps = [
    # ── 第一幕：初识老王 ──
    ('送苹果', '初次见面，送个苹果'),
    ('送花', '再送一束花，看联想链'),
    ('状态', '查看初始状态'),
    ('送石头', '送个奇怪东西，测试疑惑态'),
    ('借钱', '试试借钱，回忆检查苹果'),
    ('状态', '借钱后状态'),
    ('还钱', '还钱消除负面记忆'),
    ('送苹果', '推高好感'),
    ('送苹果', '继续推'),
    ('送苹果', '好感接近上限'),
    ('状态', '高好感验证'),
    # ── 第二幕：结识李婶 ──
    ('李婶', '走到隔壁李婶家'),
    ('送花', '给李婶送花——第一天不应提苹果'),
    ('送石头', '李婶的疑惑态'),
    ('状态', '李婶记忆隔离验证'),
    ('睡觉', '过夜，传闻传播'),
    ('状态', '查看传闻'),
    ('李婶', '切到李婶'),
    ('听说', '李婶打听传闻'),
    ('老王', '回到老王'),
    ('最近怎么样', '测试关联链'),
    ('状态', '传播后状态'),
    # ── 第三幕：时间流逝 ──
    ('睡觉', 'Day 3'),
    ('睡觉', 'Day 4'),
    ('睡觉', 'Day 5'),
    ('睡觉', 'Day 6'),
    ('睡觉', 'Day 7'),
    ('状态', '一周后'),
    ('你好啊', '一周后打招呼——还记得'),
    ('睡觉', 'Day 8'),
    ('睡觉', 'Day 9'),
    ('睡觉', 'Day 10'),
    ('状态', '十天后'),
    ('睡觉', 'Day 11'),
    ('睡觉', 'Day 12'),
    ('睡觉', 'Day 13'),
    ('睡觉', 'Day 14'),
    ('睡觉', 'Day 15'),
    ('状态', '十五天后——记忆大幅衰减'),
    ('你好啊', '尝试打招呼'),
    ('睡觉', 'Day 16'),
    ('睡觉', 'Day 17'),
    ('睡觉', 'Day 18'),
    ('睡觉', 'Day 19'),
    ('睡觉', 'Day 20'),
    ('状态', '二十天后'),
    ('睡觉', 'Day 21'),
    ('睡觉', 'Day 22'),
    ('睡觉', 'Day 23'),
    ('睡觉', 'Day 24'),
    ('睡觉', 'Day 25'),
    ('睡觉', 'Day 26'),
    ('睡觉', 'Day 27'),
    ('睡觉', 'Day 28'),
    ('睡觉', 'Day 29'),
    ('睡觉', 'Day 30'),
    ('状态', '三十天——记忆全清'),
    ('你好啊', '最终问候——失忆不忘情'),
    ('状态', '最终状态'),
    ('退出', '游戏结束'),
]

import builtins


def echo_input():
    """模拟输入，每次回显到屏幕上"""

    def _input(prompt=''):
        if not hasattr(echo_input, 'step'):
            echo_input.step = 0
        if echo_input.step >= len(steps):
            return '退出'
        cmd, desc = steps[echo_input.step]
        # 打印输入
        print(f'{prompt}{cmd}')
        if desc:
            print(f'  >>> {desc}')
        echo_input.step += 1
        return cmd

    return _input


builtins.input = echo_input()

# 运行
e = SanyanEvaluator(max_loop_steps=999999)
_register_aliases()  # 注册中文别名（必须在 evaluator 实例化之后）
src = open('ternary_agent/runtime_v2/npc_game.san', encoding='utf-8').read()
ast, _ = parse_code(src)
fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
e.eval(['do'] + fixed)
