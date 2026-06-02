"""桃花村 观察模式 — NPC 自主生活，LLM 驱动对话"""

import os, sys, json, urllib.request, urllib.error, time

os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')
from sugar.parser import parse_code
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache
from values import ReturnException, TritValue
clear_cache()


def _register_aliases():
    from ops.registry import register_alias
    for a, t in [('转字符串','to_string'),('转JSON','to_json'),('解析JSON','from_json'),
                 ('字符串包含','str_contains'),('表长','list_len'),('字符串相等','str_equals'),
                 ('是字典','is_dict'),('连接','concat'),('取长','length'),('子串','substring'),
                 ('包含','contains'),('字典键列表','dict_keys'),('含键','dict_contains'),
                 ('置键','set_key'),('取键','get_key'),('删除键','delete_key'),
                 ('列表合','list_concat'),('取','get'),('不','not'),('读文件','read_file'),
                 ('写文件','write_file'),('切片','slice'),('置元素','set_element')]:
        try: register_alias(a, t)
        except: pass


e = SanyanEvaluator(max_loop_steps=9999999)
_register_aliases()

# ── LLM 配置 ──
cfg = {'url':'','model':'','key':''}
cfg_path = 'ternary_agent/runtime_v2/village_config.san'
if os.path.exists(cfg_path):
    with open(cfg_path, encoding='utf-8') as f:
        for line in f:
            if '模型URL' in line: cfg['url'] = line.split('"')[1]
            elif '模型名' in line: cfg['model'] = line.split('"')[1]
            elif 'API密钥' in line: cfg['key'] = line.split('"')[1]
cfg['url'] = cfg['url'] or os.environ.get('LLM_URL','https://api.xiaomimimo.com/v1/chat/completions')
cfg['model'] = cfg['model'] or os.environ.get('LLM_MODEL','mimo-v1')
cfg['key'] = cfg['key'] or os.environ.get('LLM_KEY','')
has_llm = cfg['key'] and len(cfg['key']) > 10 and '你的' not in cfg['key'] and cfg['key'] != 'sk-你的key'


def llm_call(prompt):
    if not has_llm: return None
    body = json.dumps({'model':cfg['model'],'messages':[{'role':'user','content':prompt}],
                       'temperature':0.9,'max_tokens':80}).encode('utf-8')
    req = urllib.request.Request(cfg['url'], body,
        {'Content-Type':'application/json','Authorization':f'Bearer {cfg["key"]}'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return data['choices'][0]['message']['content'].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f'[LLM] HTTP {e.code}: {body[:200]}')
        return None
    except Exception as e:
        import traceback
        print(f'[LLM] Error: {type(e).__name__}: {e}')
        traceback.print_exc()
        return None


# 注册 Python 钩子：游戏调用 生成对话(n1,n2) → Python 调 LLM → 写回 对话缓存
def _gen_dialogue(ev, args):
    if not has_llm: return TritValue(0)
    try:
        n1 = ev.eval(args[0])
        n2 = ev.eval(args[1])
        if isinstance(n1, TritValue):
            n1 = n1.to_payload() if n1.is_string() else str(n1.to_int())
        if isinstance(n2, TritValue):
            n2 = n2.to_payload() if n2.is_string() else str(n2.to_int())
        n1 = str(n1); n2 = str(n2)
    except Exception:
        return TritValue(0)

    try:
        period = ev.eval(['取时段名'])
        weather = ev.scope_vars.get('_V',{}).get('天气','晴天')
        npc_data = ev.scope_vars.get('NPC数据',{})
        d1 = npc_data.get(n1,{}); d2 = npc_data.get(n2,{})
        rel = ev.eval(['取关系',n1,n2])
        cache = ev.scope_vars.get('对话缓存',{}) or {}
        # 天气相关的行为提示
        weather_hint = ''
        if weather == '下雨': weather_hint = '外面下着雨'
        elif weather == '阴天': weather_hint = '天阴着'
        else: weather_hint = '阳光很好'
        # 时段相关的行为提示
        period_hint = ''
        if period == '早晨': period_hint = '刚起床'
        elif period == '中午': period_hint = '该吃午饭了'
        elif period == '晚上': period_hint = '天黑了'
        elif period == '深夜': period_hint = '很晚了'

        p1 = f'{period}，{weather_hint}，{period_hint}。{n1}是{d1.get("角色","村民")}，性格{d1.get("性格","")}。和{n2}是{rel}关系。{n1}遇到{n2}，说一句自然的话（15字内）。'
        line1 = llm_call(p1)
        if line1:
            cache[n1] = line1
            p2 = f'{period}，{weather_hint}。{n2}是{d2.get("角色","村民")}。{n1}刚说：{line1}。请{n2}自然回应（15字内）。'
            line2 = llm_call(p2)
            if line2: cache[n2] = line2
        ev.scope_vars['对话缓存'] = cache
    except Exception as e:
        print(f'[LLM] Error: {e}')
    return TritValue(0)

from ops.registry import register
register('生成对话', _gen_dialogue)


# ── 加载游戏 ──
src = open('ternary_agent/runtime_v2/village_game.san', encoding='utf-8').read()
ast, _ = parse_code(src)
fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')
         and not (isinstance(s, list) and len(s) == 1 and s[0] == '游戏开始')]
try: e.eval(['do'] + fixed)
except ReturnException: pass

src2 = open('ternary_agent/runtime_v2/village_observe.san', encoding='utf-8').read()
ast2, _ = parse_code(src2)
fixed2 = [s for s in ast2[1:] if not (isinstance(s, list) and s[0] == 'export')]
try: e.eval(['do'] + fixed2)
except ReturnException: pass

print(f'桃花村观察模式（{e.get_var("最大天数") or 30}天，Ctrl+C 退出）')
print(f'LLM: {"已启用" if has_llm else "未配置（使用模板对话）- 编辑 village_config.san"}')
if not has_llm:
    key_preview = cfg['key'][:10] + '...' if len(cfg['key']) > 10 else cfg['key'] or '未设置'
    print(f'  当前 API密钥: {key_preview}')
print()
try: e.eval(['开始观察'])
except (KeyboardInterrupt, ReturnException): print('  结束')
