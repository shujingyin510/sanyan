"""桃花村 观察模式 — NPC 自主生活，LLM 驱动对话，输出 village_log.txt"""
import os, sys, json, urllib.request, urllib.error, time, signal

os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')

def _stop(sig, frame):
    os._exit(0)
signal.signal(signal.SIGINT, _stop)

from sugar.parser import parse_code
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache
from values import ReturnException, TritValue
clear_cache()

def _register_aliases():
    from ops.registry import register_alias
    for a,t in [('转字符串','to_string'),('转JSON','to_json'),('解析JSON','from_json'),
        ('字符串包含','str_contains'),('表长','list_len'),('字符串相等','str_equals'),
        ('是字典','is_dict'),('连接','concat'),('取长','length'),('子串','substring'),
        ('包含','contains'),('字典键列表','dict_keys'),('含键','dict_contains'),
        ('置键','set_key'),('取键','get_key'),('删除键','delete_key'),
        ('列表合','list_concat'),('取','get'),('不','not'),('读文件','read_file'),
        ('写文件','write_file'),('切片','slice'),('置元素','set_element')]:
        try: register_alias(a,t)
        except: pass

e = SanyanEvaluator(max_loop_steps=9999999)
_register_aliases()

# ── 配置 ──
cfg = {'url':'','model':'','key':''}
cp = 'ternary_agent/runtime_v2/village_config.san'
if os.path.exists(cp):
    with open(cp, encoding='utf-8') as f:
        for line in f:
            if '模型URL' in line: cfg['url'] = line.split('"')[1]
            elif '模型名' in line: cfg['model'] = line.split('"')[1]
            elif 'API密钥' in line: cfg['key'] = line.split('"')[1]
cfg['url'] = cfg['url'] or os.environ.get('LLM_URL','https://api.deepseek.com/v1/chat/completions')
cfg['model'] = cfg['model'] or os.environ.get('LLM_MODEL','deepseek-chat')
cfg['key'] = cfg['key'] or os.environ.get('LLM_KEY','')
has_llm = cfg['key'] and len(cfg['key'])>10 and '你的' not in cfg['key'] and cfg['key']!='sk-你的key'

def llm_call(prompt):
    if not has_llm: return None
    body = json.dumps({'model':cfg['model'],'messages':[{'role':'user','content':prompt}],'temperature':0.8,'max_tokens':40}).encode()
    req = urllib.request.Request(cfg['url'],body,{'Content-Type':'application/json','Authorization':f'Bearer {cfg["key"]}'})
    try:
        with urllib.request.urlopen(req,timeout=10) as r:
            text = json.loads(r.read())['choices'][0]['message']['content'].strip()
            # 去所有引号
            for c in '\'"\u201c\u2018\u201d\u2019\u300c\u300d\u300e\u300f': text = text.replace(c, '')
            # 去名字前缀（仅当后面是冒号且前缀 <= 4字）
            for sep in ['：', ':']:
                if sep in text and len(text.split(sep)[0]) <= 4:
                    text = text.split(sep,1)[1].strip()
                    break
            return text.strip()
    except: return None

def _gen_dialogue(ev, args):
    if not has_llm: return TritValue(0)
    try:
        n1 = str(ev.eval(args[0])); n2 = str(ev.eval(args[1]))
        if isinstance(ev.eval(args[0]),TritValue):
            v=ev.eval(args[0]); n1=v.to_payload() if v.is_string() else str(v.to_int())
        if isinstance(ev.eval(args[1]),TritValue):
            v=ev.eval(args[1]); n2=v.to_payload() if v.is_string() else str(v.to_int())
    except: return TritValue(0)

    period = ev.eval(['取时段名'])
    _v = ev.get_var('_V') if ev.has_var('_V') else {}
    weather = _v.get('天气','晴天')
    if hasattr(weather, 'to_payload') and hasattr(weather, 'is_string') and weather.is_string():
        weather = weather.to_payload()
    weather = str(weather)
    wdesc = { '下雨': '雨淅淅沥沥下着', '阴天': '天阴沉沉的', '晴天': '阳光很好' }.get(weather, weather)
    tdesc = { '早晨': '清晨', '中午': '正午', '下午': '午后', '晚上': '傍晚', '深夜': '深夜' }.get(period, period)
    scene_hdr = f'{tdesc}，{wdesc}。'

    npc_data = ev.get_var('NPC数据') if ev.has_var('NPC数据') else {}
    d1=npc_data.get(n1,{}); d2=npc_data.get(n2,{})
    rel = ev.eval(['取关系',n1,n2])
    cache = ev.get_var('对话缓存') if ev.has_var('对话缓存') else {}

    # 裁判 LLM：角色+动作（加角色名避免错位老王打铁）
    role1 = d1.get('角色','村民'); role2 = d2.get('角色','村民')
    sd = llm_call(f'{n1}是{role1}，{n2}是{role2}。只说此刻两人各在做什么，10字内。')
    if sd: cache['_scene'] = scene_hdr + sd.strip()
    else: cache['_scene'] = scene_hdr + f'{n1}和{n2}在村中相遇。'

    p1 = f'{n1}是{role1}。对{n2}({role2})随口说句话，10-20字。只输出这句话。'
    line1 = llm_call(p1)
    if line1:
        cache[n1] = line1
        p2 = f'{n2}是{role2}。{n1}说：{line1}。随口回句大白话，10-20字。只输出这句话。'
        line2 = llm_call(p2)
        if line2: cache[n2] = line2
    ev.scope_vars['对话缓存'] = cache
    return TritValue(0)

from ops.registry import register
register('生成对话', _gen_dialogue)

# ── 加载游戏 ──
src = open('ternary_agent/runtime_v2/village_game.san',encoding='utf-8').read()
ast,_ = parse_code(src)
fixed = [s for s in ast[1:] if not(isinstance(s,list) and s[0]=='export') and not(isinstance(s,list) and len(s)==1 and s[0]=='游戏开始')]
try: e.eval(['do']+fixed)
except ReturnException: pass

src2 = open('ternary_agent/runtime_v2/village_observe.san',encoding='utf-8').read()
ast2,_ = parse_code(src2)
fixed2 = [s for s in ast2[1:] if not(isinstance(s,list) and s[0]=='export')]
try: e.eval(['do']+fixed2)
except ReturnException: pass

# ── 输出到文件 ──
log = open('village_log.txt','w',encoding='utf-8')
orig = sys.stdout
class Tee:
    def write(self,s): orig.write(s); log.write(s); log.flush()
    def flush(self): orig.flush(); log.flush()
sys.stdout = Tee()

max_days = 5  # 测试用，改大即可
print(f'桃花村 {max_days}天 输出到 village_log.txt  LLM:{"已启用" if has_llm else "未配置"}')

e.scope_vars['最大天数'] = max_days
try: e.eval(['开始观察'])
except (KeyboardInterrupt,ReturnException): print('结束')
except SystemExit: pass
finally: log.close()
