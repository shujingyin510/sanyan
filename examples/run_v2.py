"""Runtime v2 启动器 — 测试和 NPC 演示
用法:
    python -X utf8 run_v2.py test     # 运行测试
    python -X utf8 run_v2.py npc      # 运行 NPC 30天演示
"""

import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')

from sugar.parser import parse_code
from core.evaluator import SanyanEvaluator
from ops.file_ops import clear_cache

clear_cache()


def _register_aliases():
    """注册中文别名（必须在 SanyanEvaluator 实例化之后调用）"""
    from ops.registry import register_alias

    aliases = [
        ('转字符串', 'to_string'),
        ('转JSON', 'to_json'),
        ('解析JSON', 'from_json'),
        ('时间戳', 'timestamp'),
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


cmd = sys.argv[1] if len(sys.argv) > 1 else 'test'
file_map = {
    'test': 'agent_system/sanyan/runtime_v2/tests_v2.san',
    'npc': 'agent_system/sanyan/runtime_v2/npc_demo.san',
    'game': 'agent_system/sanyan/runtime_v2/npc_game.san',
}

if cmd not in file_map:
    print('用法: python -X utf8 run_v2.py [test|npc]')
    sys.exit(1)

e = SanyanEvaluator(max_loop_steps=500000)
_register_aliases()  # 注册中文别名（必须在 evaluator 实例化之后）
src = open(file_map[cmd], encoding='utf-8').read()
ast, _ = parse_code(src)
fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
e.eval(['do'] + fixed)
