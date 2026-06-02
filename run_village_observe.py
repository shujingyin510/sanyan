"""桃花村 观察模式 — NPC 自主生活，无玩家干预，全部入睡才过天

用法:
    python -X utf8 run_village_observe.py
    编辑 village_config.san 填入 LLM key 启用大模型
"""

import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')

from sugar.parser import parse_code
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache
from values import ReturnException

clear_cache()


def _register_aliases():
    from ops.registry import register_alias
    aliases = [
        ('转字符串', 'to_string'), ('转JSON', 'to_json'), ('解析JSON', 'from_json'),
        ('字符串包含', 'str_contains'), ('表长', 'list_len'), ('字符串相等', 'str_equals'),
        ('是字典', 'is_dict'), ('连接', 'concat'), ('取长', 'length'),
        ('子串', 'substring'), ('包含', 'contains'), ('字典键列表', 'dict_keys'),
        ('含键', 'dict_contains'), ('置键', 'set_key'), ('取键', 'get_key'),
        ('删除键', 'delete_key'), ('列表合', 'list_concat'), ('取', 'get'),
        ('不', 'not'), ('读文件', 'read_file'), ('写文件', 'write_file'),
        ('切片', 'slice'), ('置元素', 'set_element'),
    ]
    for a, t in aliases:
        try:
            register_alias(a, t)
        except Exception:
            pass


e = SanyanEvaluator(max_loop_steps=999999)
_register_aliases()

src = open('ternary_agent/runtime_v2/village_game.san', encoding='utf-8').read()
# 自动启用 LLM
src = src.replace('设 LLM启用 = 假', '设 LLM启用 = 真')
# 环境变量覆盖
if os.environ.get('LLM_URL'):
    src = src.replace('模型URL = "https://api.xiaomimimo.com/v1/chat/completions"',
                       f'模型URL = "{os.environ["LLM_URL"]}"')
if os.environ.get('LLM_MODEL'):
    src = src.replace('模型名 = "mimo-v1"',
                       f'模型名 = "{os.environ["LLM_MODEL"]}"')
if os.environ.get('LLM_KEY'):
    src = src.replace('tp-你的key', os.environ['LLM_KEY'])

ast, _ = parse_code(src)
fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
try:
    e.eval(['do'] + fixed)
except ReturnException:
    pass

print()
print('  ══════════════════════════════════════')
print('  桃花村 观察模式 — NPC 自主生活')
print('  全部 NPC 入睡后自动进入下一天')
print('  ══════════════════════════════════════')
print()

try:
    e.eval(['开始观察'])
except KeyboardInterrupt:
    print()
    print('  观察结束')
