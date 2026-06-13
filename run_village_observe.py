"""桃花村 观察模式 — NPC 自主生活，LLM 驱动对话，输出 village_log.txt
--verbose: 显示三态置信度推理链"""

import os
import sys
import json
import urllib.request
import urllib.error
import time
import signal
import random

from ternary_engine import TernaryEngine

# 三态引擎：追踪村庄全局信任演化
_village_ternary = TernaryEngine(max_hesitation=5, min_gain=0.03)
# 每个 NPC 独立的信任追踪
_npc_ternary: dict = {}
# 记忆链：谁对谁说了什么
_memory_chain: list = []


# 视觉宽度：中文字符占两个终端列宽
def _vpad(s, w):  # 把字符串垫到视觉宽度 w
    v = sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))
    return str(s) + ' ' * max(0, w - v)


os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')

_verbose = '--verbose' in sys.argv


def _stop(sig, frame):
    os._exit(0)


signal.signal(signal.SIGINT, _stop)

from sugar.parser import parse_code  # noqa: E402
from evaluator import SanyanEvaluator  # noqa: E402
from ops.file_ops import clear_cache  # noqa: E402
from values import ReturnException, TritValue  # noqa: E402
from eval_utils import to_float  # noqa: E402

clear_cache()


def _register_aliases():
    from ops.registry import register_alias

    for a, t in [
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
    ]:
        try:
            register_alias(a, t)
        except Exception:
            pass  # 目标操作尚未注册时静默跳过（延迟加载机制）


e = SanyanEvaluator(max_loop_steps=9999999)
_register_aliases()

# ── 配置 ──
cfg = {'url': '', 'model': '', 'key': ''}
cp = 'ternary_agent/runtime_v2/village_config.san'
if os.path.exists(cp):
    with open(cp, encoding='utf-8') as f:
        for line in f:
            if '模型URL' in line:
                cfg['url'] = line.split('"')[1]
            elif '模型名' in line:
                cfg['model'] = line.split('"')[1]
            elif 'API密钥' in line:
                cfg['key'] = line.split('"')[1]
cfg['url'] = cfg['url'] or os.environ.get('LLM_URL', 'https://api.deepseek.com/v1/chat/completions')
cfg['model'] = cfg['model'] or os.environ.get('LLM_MODEL', 'deepseek-v4-pro')
cfg['key'] = cfg['key'] or os.environ.get('LLM_KEY', '')
has_llm = cfg['key'] and len(cfg['key']) > 10 and '你的' not in cfg['key'] and cfg['key'] != 'sk-你的key'
if not has_llm:
    print('提示: 未配置有效 API 密钥。设置环境变量 LLM_KEY 或在 village_config.san 中填入密钥。')

_llm_calls: int = 0  # LLM 调用计数
_llm_times: dict = {}  # {类别: [总次数, 总耗时]}
_t_start = time.time()


def llm_call(prompt):
    global _llm_calls
    if not has_llm:
        return None
    _llm_calls += 1
    t0 = time.time()
    body = json.dumps(
        {'model': cfg['model'], 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.8, 'max_tokens': 40}
    ).encode()
    req = urllib.request.Request(
        cfg['url'], body, {'Content-Type': 'application/json', 'Authorization': f'Bearer {cfg["key"]}'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            text = json.loads(r.read())['choices'][0]['message']['content'].strip()
            dt = time.time() - t0
            # 分类统计
            if '对话语气' in prompt:
                cat = '语气检测'
            elif '语气是' in prompt:
                cat = '行为分类'
            elif '回应' in prompt or '顶回去' in prompt or '接话' in prompt:
                cat = 'NPC回应'
            elif '对' in prompt and '说句话' in prompt:
                cat = 'NPC说话'
            else:
                cat = '其他'
            _llm_times[cat] = (_llm_times.get(cat, [0, 0.0])[0] + 1, _llm_times.get(cat, [0, 0.0])[1] + dt)
            # 去所有引号
            for c in '\'"\u201c\u2018\u201d\u2019\u300c\u300d\u300e\u300f':
                text = text.replace(c, '')
            # 去名字前缀（仅当后面是冒号且前缀 <= 4字）
            for sep in ['：', ':']:
                if sep in text and len(text.split(sep)[0]) <= 4:
                    text = text.split(sep, 1)[1].strip()
                    break
            return text.strip()
    except Exception:
        return None


def _gen_dialogue(ev, args):
    if not has_llm:
        return TritValue(0)
    try:
        n1 = str(ev.eval(args[0]))
        n2 = str(ev.eval(args[1]))
        if isinstance(ev.eval(args[0]), TritValue):
            v = ev.eval(args[0])
            n1 = v.to_payload() if v.is_string() else str(v.to_int())
        if isinstance(ev.eval(args[1]), TritValue):
            v = ev.eval(args[1])
            n2 = v.to_payload() if v.is_string() else str(v.to_int())
    except Exception:
        return TritValue(0)

    # ── #6 NPC出场均衡：跟踪每日出场 ──
    _npc_daily[n1] = _npc_daily.get(n1, 0) + 1
    _npc_daily[n2] = _npc_daily.get(n2, 0) + 1

    trust_map = {'夫妻': 0.95, '朋友': 0.75, '邻居': 0.55, '熟人': 0.35, '陌生人': 0.10}

    period = ev.eval(['取时段名'])
    _v = ev.get_var('_V') if ev.has_var('_V') else {}
    # 解开 TritValue 包装（求值器可能返回 TritValue(dict)）
    if hasattr(_v, 'is_dict') and hasattr(_v, 'to_payload') and _v.is_dict():
        _v = _v.to_payload()
    weather = _v.get('天气', '晴天') if isinstance(_v, dict) else '晴天'
    if hasattr(weather, 'to_payload') and hasattr(weather, 'is_string') and weather.is_string():
        weather = weather.to_payload()
    weather = str(weather)
    wdesc = {'下雨': '雨淅淅沥沥下着', '阴天': '天阴沉沉的', '晴天': '阳光很好'}.get(weather, weather)
    tdesc = {'早晨': '清晨', '中午': '正午', '下午': '午后', '晚上': '傍晚', '深夜': '深夜'}.get(period, period)
    scene_hdr = f'{tdesc}，{wdesc}。'

    npc_data = ev.get_var('NPC数据') if ev.has_var('NPC数据') else {}
    if hasattr(npc_data, 'is_dict') and hasattr(npc_data, 'to_payload') and npc_data.is_dict():
        npc_data = npc_data.to_payload()
    d1 = npc_data.get(n1, {}) if isinstance(npc_data, dict) else {}
    d2 = npc_data.get(n2, {}) if isinstance(npc_data, dict) else {}
    rel = ev.eval(['取关系', n1, n2])
    cache = ev.get_var('对话缓存') if ev.has_var('对话缓存') else {}
    if hasattr(cache, 'is_dict') and hasattr(cache, 'to_payload') and cache.is_dict():
        cache = cache.to_payload()

    # 场景描述：用 NPC 日程数据，不靠 LLM 乱编
    try:
        act1 = str(ev.eval(['取NPC行为', n1]))
        act2 = str(ev.eval(['取NPC行为', n2]))
    except Exception:
        act1 = '在忙'
        act2 = '在忙'
    cache['_scene'] = f'{scene_hdr}{n1}{act1}，{n2}{act2}。'

    role1 = d1.get('角色', '村民')
    role2 = d2.get('角色', '村民')
    pers1 = d1.get('性格', '')
    pers2 = d2.get('性格', '')
    # 根据天气和关系决定对话语气方向
    rel_str = str(rel) if rel else '陌生人'
    # tone_hint = {'夫妻': '家常', '朋友': '随意', '邻居': '寒暄', '熟人': '客套', '陌生人': '客气'}.get(rel_str, '客气')
    # 两步：先定语气，再生成。关键区分：
    # 打趣=开玩笑（无恶意）、抱怨=对天气/生活不满（非对人）、冲突=直接针对对方人身攻击
    tone = llm_call(
        f'{n1}({role1},{pers1})和{n2}({role2},{pers2})在{period}{weather}天相遇。'
        f'语气：友好、打趣、抱怨、冲突、平淡？'
        f'（打趣=玩笑无恶意。抱怨=对天气/生活的牢骚，非针对对方。冲突=针对对方的人身攻击或翻旧账）只答一个词。'
    )
    if not tone:
        tone = '平淡'
    # 语气多样性：高互信时偏向积极语气，低互信时维持平淡/冲突
    existing_trust = 0.5
    tk = f'{min(n1, n2)}_{max(n1, n2)}'
    pt = ev._scopes[0].get('NPC信任', {}) or {}
    existing_trust = pt.get(tk, trust_map.get(rel_str, 0.10))
    if hasattr(existing_trust, 'to_int'):
        existing_trust = float(existing_trust.to_int())
    # #12 性格冲突倾向：性格组合天生容易擦枪走火
    conflict_affinity = {
        '孤僻': 0.30,
        '直爽': 0.25,
        '爱打听': 0.20,
        '精明': 0.15,
        '爽朗': 0.10,
        '稳重': 0.05,
        '憨厚': 0.02,
        '和善': 0.02,
    }
    p1_aff = conflict_affinity.get(pers1, 0.05)
    p2_aff = conflict_affinity.get(pers2, 0.05)
    conflict_chance = (p1_aff + p2_aff) / 2 * 0.15
    if existing_trust < 0.3:
        conflict_chance *= 2.0
    if tone not in ('冲突', '欺骗') and random.random() < conflict_chance:
        tone = '冲突'
    # #11 保守决策：互信"可能"区间有50%概率压制冲突语气
    if existing_trust >= 0.3 and existing_trust < 0.7 and tone == '冲突' and random.random() < 0.50:
        tone = '抱怨'  # 降级为抱怨（对事），不惩罚信任
    if tone == '平淡' and existing_trust > 0.5 and random.random() < 0.4:
        tone = random.choice(['友好', '打趣', '抱怨'])
    elif tone == '平淡' and existing_trust < 0.2 and random.random() < 0.3:
        tone = '冲突'
    # #7 空间约束：同地点加成，异地惩罚
    loc_mult = 1.0
    try:
        _npc_pos = ev.get_var('NPC位置') if ev.has_var('NPC位置') else {}
        if hasattr(_npc_pos, 'is_dict') and hasattr(_npc_pos, 'to_payload') and _npc_pos.is_dict():
            _npc_pos = _npc_pos.to_payload()
        if isinstance(_npc_pos, dict):
            p1 = _npc_pos.get(n1, '')
            p2 = _npc_pos.get(n2, '')
            if hasattr(p1, 'to_payload'):
                p1 = str(p1.to_payload())
            if hasattr(p2, 'to_payload'):
                p2 = str(p2.to_payload())
            if p1 and p2 and p1 == p2:
                loc_mult = 1.2
            elif p1 and p2:
                loc_mult = 0.6
    except Exception:
        pass
    # #1 事件记忆：注入近期事件到对话提示
    event_ctx = ''
    for pd in sorted(_event_memory.keys(), reverse=True):
        if pd == '_chain':
            continue
        for evt in _event_memory.get(pd, []):
            if n1 in evt or n2 in evt:
                event_ctx += f'前几天:{evt};'
                if len(event_ctx) > 150:
                    break
        if len(event_ctx) > 150:
            break
    event_hint = f'（背景：{event_ctx}）' if event_ctx else ''
    # 只有"冲突"才降好感，抱怨和打趣算闲聊
    tone_label = {'友好': '赞扬', '打趣': '闲聊', '抱怨': '闲聊', '平淡': '问候', '冲突': '争吵'}.get(tone, '问候')
    tone_prompt = {
        '友好': '说句热情友善的话',
        '打趣': '说句玩笑打趣的话',
        '抱怨': '说句对天对事的抱怨',
        '平淡': '随便说句日常话',
        '冲突': '说句带刺的话（针对对方，但不要太恶毒）',
    }.get(tone, '说句话')
    p1 = (
        f'{n1}是{role1}，性格{pers1}，正在{act1}。天气{weather}。'
        f'对{n2}({role2}){tone_prompt}。{event_hint}要符合{role1}身份，10-30字。只输出这句话。'
    )
    line1 = llm_call(p1)
    line2 = None  # 防御：LLM 返回 None 时不报 UnboundLocalError
    if line1:
        cache[n1] = line1
        reply_tone = {
            '友好': '友善回应',
            '打趣': '接话逗回去',
            '抱怨': '附和或劝解',
            '平淡': '随口接话',
            '冲突': '回敬两句',
        }.get(tone, '回应')
        p2 = (
            f'{n2}是{role2}，性格{pers2}，正在{act2}。{n1}对你说："{line1}"。'
            f'{reply_tone}。要符合{role2}身份，10-30字。只输出回应。'
        )
        line2 = llm_call(p2)
        if line2:
            cache[n2] = line2

    # ── 行为标签分析 ──
    behave_delta = {
        '帮助': 0.060,
        '赞扬': 0.030,
        '交易': 0.015,
        '问候': 0.009,
        '争吵': -0.040,
        '欺骗': -0.240,
        '赠礼': 0.150,
        '闲聊': 0.003,
    }
    label = tone_label  # 语气预判 → 行为标签（打趣/抱怨→闲聊，冲突→争吵，友好→赞扬）
    full_text = (line1 or '') + (line2 or '')
    if full_text:
        # 关键词快速匹配
        for kw in ['帮你', '帮忙', '我来', '给你送', '分你']:
            if kw in full_text:
                label = '帮助'
                break
        for kw in ['真好', '厉害', '不错', '佩服', '多谢', '谢谢']:
            if kw in full_text and label == '问候':
                label = '赞扬'
                break
        for kw in ['多少钱', '卖', '买', '便宜', '换']:
            if kw in full_text and label == '问候':
                label = '交易'
                break
        for kw in [
            '骗',
            '撒谎',
            '胡说',
            '胡扯',
            '瞎说',
            '滚',
            '偷',
            '抢',
            '凭什么',
            '咋回事',
            '怎么搞的',
            '你啥意思',
            '管得宽',
        ]:
            if kw in full_text:
                label = '争吵'
                break
        for kw in ['送你', '拿着', '收下', '给你带']:
            if kw in full_text and label == '问候':
                label = '赠礼'
                break
        # LLM 分类：关键词未命中时用大模型判断对话语气
        if label == '问候' and has_llm:
            cls = llm_call(f'"{line1}" "{line2}" 这段对话是：问候、交易、争吵、帮助、赞扬、赠礼、闲聊？只输出一个词。')
            if cls and cls in behave_delta:
                label = cls

    # ── 动态 δ 加权：性格 + 天气 + 对话长度 ──
    p1 = d1.get('性格', '')
    p2 = d2.get('性格', '')
    # 性格组合：相关性格系数取平均（两个 NPC 的该标签系数均值）
    mult_vals = []
    for p in [p1, p2]:
        if p in personality_mult and label in personality_mult[p]:
            mult_vals.append((p, personality_mult[p][label]))
    mult_p = sum(v for _, v in mult_vals) / len(mult_vals) if mult_vals else 1.0
    # 天气加权：下雨对话短 → 影响打折；晴天社交活跃 → 影响放大
    mult_w = {'下雨': 0.7, '阴天': 1.0, '晴天': 1.2}.get(weather, 1.0)
    # 对话长度加权：长对话影响力更大 (基数 20 字，根号平滑)
    mult_l = min(2.0, max(0.5, (len(full_text) / 20) ** 0.5))
    delta = behave_delta.get(label, 0.001) * mult_p * mult_w * mult_l * loc_mult
    ev._scopes[0]['_last_label'] = label
    ev._scopes[0]['_last_delta'] = delta

    # 传闻生成：随机事件触发传闻
    if random.random() < 0.3 and n1 and n2:
        topics = [
            f'{n1}说{n2}家的庄稼今年特别好。',
            f'听说{n1}和{n2}在商量合伙做生意。',
            f'{n2}告诉{n1}山里最近有野猪出没。',
            f'{n1}听说{n2}最近身体不太好。',
        ]
        rumor = random.choice(topics)
        cache['_rumor'] = rumor

    # 更新 NPC 间关系值（存入根作用域，跨函数调用不丢失）
    trust_key = f'{min(n1, n2)}_{max(n1, n2)}'
    trust_dict = ev._scopes[0].get('NPC信任', {}) or {}
    old_trust = trust_dict.get(trust_key, trust_map.get(rel, 0.10))
    new_trust = max(0.01, min(1.0, old_trust + delta))
    trust_dict[trust_key] = new_trust
    ev._scopes[0]['NPC信任'] = trust_dict

    # ── 三态追踪：村庄全局信任演化 ──
    _village_ternary.step(
        f'对话({label})',
        f'{n1}↔{n2}={new_trust:.2f}',
        risk='低' if label in ('闲聊', '问候', '赞扬', '帮助', '赠礼') else '中',
    )
    # 每人独立追踪 + 记忆链
    for npc in (n1, n2):
        if npc not in _npc_ternary:
            _npc_ternary[npc] = TernaryEngine(max_hesitation=3, min_gain=0.03)
        _npc_ternary[npc].step(f'{label}', f'{delta:+.3f}')
    _memory_chain.append({'n1': n1, 'n2': n2, 'label': label, 'delta': delta, 'trust': new_trust})

    # ── #4 关系传递：A信任B高 + B信任C → A对C小量增益 ──
    chain_prop = []
    if new_trust > 0.5:
        all_npc = list((ev.get_var('NPC数据') if ev.has_var('NPC数据') else {}).keys() or [])
        for n3 in all_npc:
            if n3 in (n1, n2):
                continue
            tk_b = f'{min(n2, n3)}_{max(n2, n3)}'
            tk_a = f'{min(n1, n3)}_{max(n1, n3)}'
            trust_b3 = trust_dict.get(tk_b, 0.10)
            if trust_b3 < 0.3:
                continue
            old_a3 = trust_dict.get(tk_a, 0.10)
            transfer = (new_trust - 0.5) * (trust_b3 - 0.3) * 0.05
            if abs(transfer) < 0.001:
                continue
            new_a3 = max(0.01, min(1.0, old_a3 + transfer))
            trust_dict[tk_a] = new_a3
            chain_prop.append(f'{n1}↔{n3}: {old_a3:.3f}→{new_a3:.3f}({transfer:+.3f})')

    # 社交活跃度统计（次数 + 净Δ累计）
    _social_activity[n1] = _social_activity.get(n1, [0, 0.0])
    _social_activity[n2] = _social_activity.get(n2, [0, 0.0])
    _social_activity[n1][0] += 1
    _social_activity[n1][1] += delta
    _social_activity[n2][0] += 1
    _social_activity[n2][1] += delta

    # ── 三态间接传播：若对话提到第三方 NPC，衰减传播互信影响 ──
    indirect = []
    all_npc_names = list((ev.get_var('NPC数据') if ev.has_var('NPC数据') else {}).keys() or [])
    for name in all_npc_names:
        if name not in (n1, n2):
            if name in (line1 or '') or name in (line2 or ''):
                indirect.append(name)
    for n3 in indirect:
        # 衰减因子 = 说话者与第三方的互信 × 0.3
        tk1 = f'{min(n1, n3)}_{max(n1, n3)}'
        tk2 = f'{min(n2, n3)}_{max(n2, n3)}'
        trust_n1n3 = trust_dict.get(tk1, 0.10)
        trust_n2n3 = trust_dict.get(tk2, 0.10)
        rel_n1n3 = str(ev.eval(['取关系', n1, n3]))
        rel_n2n3 = str(ev.eval(['取关系', n2, n3]))
        decay = 0.3  # 间接传播衰减率
        indirect_delta = delta * decay * (trust_n1n3 if line1 and n3 in (line1 or '') else trust_n2n3)
        # 更新 n2↔n3（接收方与被提及方）
        old_n2n3 = trust_dict.get(tk2, trust_map.get(rel_n2n3, 0.10))
        new_n2n3 = max(0.01, min(1.0, old_n2n3 + indirect_delta))
        trust_dict[tk2] = new_n2n3
        # 也更新 n1↔n3（说话者与被提及方，如果说话者自己不是被提及方）
        old_n1n3 = trust_dict.get(tk1, trust_map.get(rel_n1n3, 0.10))
        new_n1n3 = max(0.01, min(1.0, old_n1n3 + indirect_delta * 0.5))
        trust_dict[tk1] = new_n1n3
        if _verbose:
            cache['_indirect'] = cache.get('_indirect', [])
            # 确定谁提到了第三方
            mentioner = n1 if (line1 and n3 in (line1 or '')) else n2
            cache['_indirect'].append(
                f'  ├ 间接传播: {mentioner}提到{n3} → '
                f'{n2}↔{n3}: {old_n2n3:.3f} → {new_n2n3:.3f} ({indirect_delta:+.3f}) '
                f'[链:{mentioner}→{n3} 衰减{decay}]\n'
            )

    # verbose 输出：三态推理链
    if _verbose and line1 and line2:
        # 获取位置
        try:
            pos1 = str(ev.eval(['取键', ['取', 'NPC位置', n1]]))
            pos2 = str(ev.eval(['取键', ['取', 'NPC位置', n2]]))
        except Exception:
            pos1 = '村中'
            pos2 = '村中'
        loc = pos1 if pos1 == pos2 else f'{pos1}↔{pos2}'
        # 三态区间：统一用真/可能/假
        if new_trust >= 0.7:
            zone = '真 ●●●'
        elif new_trust >= 0.3:
            zone = '可能 ◐◐◐'
        else:
            zone = '假 ○○○'
        # 判定来源
        src = 'LLM' if tone != '平淡' else ('关键词' if label != '问候' else 'LLM分类')
        # 加权信息：显示性格名 + 公式
        weight_parts = []
        for p, v in mult_vals:
            weight_parts.append(f'{p}({label}{v:.2f})')
        if abs(mult_w - 1.0) > 0.05:
            weight_parts.append(f'天气{weather}×{mult_w:.2f}')
        weight_str = ', '.join(weight_parts) if weight_parts else '无'
        base_delta = behave_delta.get(label, 0.001)
        formula = f'\n  │ Δ = {base_delta:+.3f} (基础{label})'
        if mult_vals:
            formula += f' × 性格{mult_p:.2f}'
        if mult_w != 1.0:
            formula += f' × 天气{mult_w:.2f}'
        if abs(mult_l - 1.0) > 0.1:
            formula += f' × 长度{mult_l:.2f}(字数≈{len(full_text)})'
        formula += f' = {delta:+.3f}'
        cache['_trit'] = (
            f'  ┌─ 第{_v["天数"]}天 {period} {weather} {loc}\n'
            f'  │ 行为判定: {label} ({src})' + (f'\n  │ 加权因子: {weight_str}' if weight_str else '') + formula + '\n'
            f'  │ 互信变化: {n1}↔{n2}: {old_trust:.3f} → {new_trust:.3f} ({delta:+.3f})\n'
            f'  │ 当前互信: {rel} = {new_trust:.3f} [三态: {zone}]\n'
            + (''.join(cache.get('_indirect', [])) + '\n' if cache.get('_indirect') else '')
            + (''.join(f'  ├ 关系传递: {c}\n' for c in chain_prop) if chain_prop else '')
            + (f'  ⚠ 警告: 互信={new_trust:.3f} 过低，后续判断不可靠\n' if new_trust < 0.15 else '')
            + (f'  ⛔ 断裂: 互信={new_trust:.3f} 低于最低阈值，关系已断裂\n' if new_trust < 0.02 else '')
            + '  └─'
        )
    if _verbose and not line1:
        cache['_trit'] = f'  ◈ {n1}↔{n2} LLM调用失败，降级为默认对话 [信度=0]'

    ev._scopes[0]['对话缓存'] = cache
    # 事件记忆：记录显著对话事件
    if label != '问候' and label != '闲聊':
        _v = ev.get_var('_V') if ev.has_var('_V') else {}
        # 处理 _V 可能是 TritValue 包装的字典
        if hasattr(_v, 'is_dict') and hasattr(_v, 'to_payload') and _v.is_dict():
            _v = _v.to_payload()
        day = _v.get('天数', 0) if isinstance(_v, dict) else 0
        d = str(to_float(day))
        # 加权摘要（始终显示，无加权时标 ×1.0）
        parts = []
        if mult_vals:
            labels = '/'.join(p for p, _ in mult_vals)
            parts.append(f'{labels}{mult_p:.2f}')
        else:
            parts.append('性格×1.0')
        parts.append(f'{weather}{mult_w:.2f}')
        w_summary = f'[{",".join(parts)}]'
        _event_memory.setdefault(d, []).append(f'{n1}↔{n2}对话: {label}(δ={delta:+.3f}{w_summary})')
        _event_memory.setdefault('_chain', []).append({'day': d, 'type': label, 'n1': n1, 'n2': n2, 'delta': delta})
    return TritValue(0)


from ops.registry import register  # noqa: E402

register('生成对话', _gen_dialogue)

# ── 性格加权表（模块级，启动信息和 _gen_dialogue 共用）──
personality_mult = {
    '憨厚': {'争吵': 0.5, '帮助': 1.3, '赠礼': 1.2, '赞扬': 1.2},
    '爽朗': {'闲聊': 1.5, '争吵': 0.7, '帮助': 1.2, '赞扬': 1.2},
    '直爽': {'争吵': 1.5, '赠礼': 0.7, '帮助': 1.2, '赞扬': 0.8},
    '稳重': {'争吵': 0.5, '帮助': 1.2, '交易': 1.2},
    '爱打听': {'闲聊': 1.5, '争吵': 1.3, '帮助': 0.8, '赞扬': 1.3},
    '和善': {'帮助': 1.4, '争吵': 0.5, '赠礼': 1.3, '赞扬': 1.3},
    '孤僻': {'闲聊': 0.5, '争吵': 1.3, '帮助': 0.7, '赠礼': 0.7, '赞扬': 0.7},
    '精明': {'交易': 1.5, '赠礼': 0.7, '争吵': 1.2, '赞扬': 0.8},
}

# ── 负反馈事件池 + 事件记忆 ──
# 格式: (文本模板, 标签, δ, 是否对称, {角色→位置约束})
_neg_events = [
    ('鸡进了{0}的菜地，踩坏了好几棵菜。', '菜地被踩', -0.060, True, {0: ['老农', '农妇']}),  # 只有种菜的才有菜地
    ('{0}找{1}借锄头，{1}说上次借了还没还。', '借物不还', -0.080, False, None),
    ('{0}传话说{1}在背后讲了坏话，{1}不承认。', '传错话', -0.050, True, None),
    ('村里有人说{0}家的粮食比别人多，{1}去追问真假。', '谣言', -0.090, False, None),
    ('{0}家的狗追了{1}家的鸡，{1}找上门来。', '家畜纠纷', -0.060, True, None),
    ('{0}说{1}卖东西缺斤短两，{1}很生气。', '生意纠纷', -0.080, True, {1: ['小贩', '铁匠']}),  # 只有做生意的才卖东西
    ('{0}借了{1}的钱一直没还，今天被当面问了。', '借钱不还', -0.100, False, None),
    (
        '{0}和{1}因为地界的事吵了一架。',
        '地界纠纷',
        -0.060,
        True,
        {0: ['老农', '农妇'], 1: ['老农', '农妇']},
    ),  # 地界纠纷只有种地的之间有
]
_event_memory: dict = {}  # {day: [事件描述, ...], 跨天因果链}
_social_activity: dict = {}  # {NPC名: [互动次数, 净Δ]}
_npc_daily: dict = {}  # {NPC名: 今日互动次数} 用于出场均衡
_npc_names_cache: list = []  # 缓存 NPC 名列表


def _night_events(ev, args):
    """夜间事件：氛围 + 随机负反馈 + 记忆"""
    r = random.randint(0, 100)
    # 氛围事件
    if r < 25:
        print('  远处传来几声狗叫。')
    elif r < 15:
        nd = ev.get_var('NPC数据') if ev.has_var('NPC数据') else {}
        if hasattr(nd, 'is_dict') and hasattr(nd, 'to_payload') and nd.is_dict():
            nd = nd.to_payload()
        keys = list(nd.keys()) if isinstance(nd, dict) else []
        if keys:
            print(f'  {random.choice(keys)} 半夜起来喂了趟牲口。')
    elif r < 8:
        nd = ev.get_var('NPC数据') if ev.has_var('NPC数据') else {}
        if hasattr(nd, 'is_dict') and hasattr(nd, 'to_payload') and nd.is_dict():
            nd = nd.to_payload()
        keys = list(nd.keys()) if isinstance(nd, dict) else []
        if len(keys) >= 2:
            a, b = random.sample(keys, 2)
            print(f'  {a} 提着灯笼在村子里巡逻，路过{b}家门口。')
    elif r < 4:
        print('  一只猫头鹰咕咕叫了几声。')
    elif r < 2:
        print('  有人家的门吱呀响了一声。')

    # 负反馈冲突事件：~25% 每晚触发一次
    if random.random() < 0.25:
        npc_data = ev.get_var('NPC数据') if ev.has_var('NPC数据') else {}
        if hasattr(npc_data, 'is_dict') and hasattr(npc_data, 'to_payload') and npc_data.is_dict():
            npc_data = npc_data.to_payload()
        npc_keys = list(npc_data.keys()) if isinstance(npc_data, dict) else []
        if len(npc_keys) >= 2:
            # 角色过滤：选符合事件约束的事件
            candidates = list(_neg_events)
            random.shuffle(candidates)
            event = None
            for evt in candidates:
                role_filter = evt[4] if len(evt) > 4 else None
                if role_filter:
                    valid = []
                    for k in npc_keys:
                        role = npc_data[k].get('角色', '') if isinstance(npc_data[k], dict) else ''
                        if 0 in role_filter and role not in role_filter[0]:
                            continue
                        if 1 in role_filter and role not in role_filter[1]:
                            continue
                        valid.append(k)
                    if len(valid) < 2:
                        continue
                    n1, n2 = random.sample(valid, 2)
                else:
                    n1, n2 = random.sample(npc_keys, 2)
                event = evt
                break
            if not event:
                n1, n2 = random.sample(npc_keys, 2)
                event = random.choice(_neg_events)
            text = event[0].format(n1, n2)
            if not event[3]:  # 非对称事件：交换方向
                text = event[0].format(n2, n1)
            # 性格加权（冲突类事件按 NPC 争吵系数加权）
            delta_e = event[2]
            behav = event[1]
            mult_p_night = 1.0
            mult_parts: list = []
            for n in [n1, n2]:
                nd = npc_data.get(n, {}) if isinstance(npc_data, dict) else {}
                pers = nd.get('性格', '') if isinstance(nd, dict) else ''
                # 冲突类事件映射到争吵系数
                mapped = {
                    '菜地被踩': '争吵',
                    '借物不还': '争吵',
                    '传错话': '争吵',
                    '谣言': '争吵',
                    '家畜纠纷': '争吵',
                    '生意纠纷': '争吵',
                    '借钱不还': '争吵',
                    '地界纠纷': '争吵',
                }.get(behav, behav)
                if pers in personality_mult and mapped in personality_mult[pers]:
                    v = personality_mult[pers][mapped]
                    mult_p_night = (mult_p_night + v) / 2 if mult_parts else v
                    mult_parts.append(f'{pers}({mapped}{v:.2f})')
            delta_e *= mult_p_night if mult_parts else 1.0
            print(f'  * {text}')
            # 更新 NPC 互信（根作用域持久化）
            trust_dict = ev._scopes[0].get('NPC信任', {}) or {}
            tk = f'{min(n1, n2)}_{max(n1, n2)}'
            old = trust_dict.get(tk, 0.30)
            new = max(0.01, old + delta_e)
            ev._scopes[0]['NPC信任'] = trust_dict
            if _verbose:
                rel = '邻居'
                try:
                    rel = str(ev.eval(['取关系', n1, n2]))
                except Exception:
                    pass
                if new >= 0.7:
                    zone = '真 ●●●'
                elif new >= 0.3:
                    zone = '可能 ◐◐◐'
                else:
                    zone = '假 ○○○'
                try:
                    period = str(ev.eval(['取时段名']))
                    _v = ev.get_var('_V') if ev.has_var('_V') else {}
                    if hasattr(_v, 'is_dict') and hasattr(_v, 'to_payload') and _v.is_dict():
                        _v = _v.to_payload()
                    weather = _v.get('天气', '') if isinstance(_v, dict) else ''
                except Exception:
                    period = '深夜'
                    weather = ''
                print(f'  ┌─ 第{_v["天数"]}天 {period} {weather} 夜间事件')
                print(f'  │ 行为判定: {event[1]} (冲突池)')
                if mult_p_night != 1.0:
                    print(
                        f'  │ Δ = {event[2]:+.3f}(固定) × 性格{mult_p_night:.2f}({",".join(mult_parts)}) = {delta_e:+.3f}'
                    )
                else:
                    print(f'  │ Δ = {event[2]:+.3f} (固定δ)')
                print(f'  │ 互信变化: {n1}↔{n2}: {old:.3f} → {new:.3f} ({delta_e:+.3f})')
                print(f'  │ 当前互信: {rel} = {new:.3f} [三态: {zone}]')
                print('  └─')
            # 事件记忆
            _v = ev.get_var('_V') if ev.has_var('_V') else {}
            if hasattr(_v, 'is_dict') and hasattr(_v, 'to_payload') and _v.is_dict():
                _v = _v.to_payload()
            day = _v.get('天数', 0) if isinstance(_v, dict) else 0
            d = str(to_float(day))
            _event_memory.setdefault(d, []).append(f'{n1}与{n2}: {event[1]}(δ={delta_e:+.3f})[冲突池]')
            _event_memory.setdefault('_chain', []).append(
                {'day': d, 'type': event[1], 'n1': n1, 'n2': n2, 'delta': delta_e}
            )
    return TritValue(0)


register('夜间冲突事件', _night_events)
register('夜间事件', _night_events)  # 别名，兼容旧代码

# ── 加载游戏 ──
src = open('ternary_agent/runtime_v2/village_game.san', encoding='utf-8').read()
ast, _ = parse_code(src)
fixed = [
    s
    for s in ast[1:]
    if not (isinstance(s, list) and s[0] == 'export')
    and not (isinstance(s, list) and len(s) == 1 and s[0] == '游戏开始')
]
try:
    e.eval(['do'] + fixed)
except ReturnException:
    pass

src2 = open('ternary_agent/runtime_v2/village_observe.san', encoding='utf-8').read()
ast2, _ = parse_code(src2)
fixed2 = [s for s in ast2[1:] if not (isinstance(s, list) and s[0] == 'export')]
try:
    e.eval(['do'] + fixed2)
except ReturnException:
    pass

# ── 输出到文件 ──
log = open('village_log.txt', 'w', encoding='utf-8')
orig = sys.stdout


class Tee:
    def write(self, s):
        # 睡眠状态行：剥掉 => 前缀，NPC 名对齐
        out = s
        if s.startswith('  => ') and '— 💤' in s:
            s2 = s[6:].rstrip('\n')  # 剥掉 '  => ' 和尾部换行
            out = '      ' + _vpad(s2.split(' —')[0].strip(), 6) + ' — 💤\n'
        elif s.startswith('  => ') and '—' in s and '💤' not in s:
            s2 = s[6:].rstrip('\n')
            parts = s2.split(' — ', 1)
            if len(parts) == 2:
                out = '      ' + _vpad(parts[0].strip(), 6) + ' — ' + parts[1]
        orig.write(out)
        log.write(out)
        try:
            log.flush()
        except ValueError:
            pass

    def flush(self):
        orig.flush()
        try:
            log.flush()
        except ValueError:
            pass  # 文件已关闭时忽略


sys.stdout = Tee()

max_days = 5  # 测试用，改大即可
_seed = int(time.time() * 1000) % 1000000
random.seed(_seed)
print(f'桃花村 {max_days}天 输出到 village_log.txt  LLM:{"已启用" if has_llm else "未配置"}  随机种子: {_seed}')
print()
print('══ 配置说明 ══')
print('基础Δ映射: 闲聊+0.003 问候+0.009 交易+0.015 赞扬+0.030 帮助+0.060 赠礼+0.150 争吵-0.040 欺骗-0.240')
print('三态阈值: 假<0.3  可能0.3~0.7  真≥0.7')
print('性格加权: 两人性格系数取平均，缺失行为默认×1.0')
print('天气加权: 下雨×0.7  阴天×1.0  晴天×1.2')
print('长度因子: min(2.0, max(0.5, √(对话字数/20)))')
# 夜间冲突池 δ
neg_info = ', '.join(f'{e[1]}{e[2]:+.3f}' for e in _neg_events)
print(f'夜间冲突池: {neg_info}')
print()
print('角色性格表:')
npc_data = e.scope_vars.get('NPC数据', {}) or {}
if hasattr(npc_data, 'is_dict') and hasattr(npc_data, 'to_payload') and npc_data.is_dict():
    npc_data = npc_data.to_payload()
npc_keys = list(npc_data.keys()) if isinstance(npc_data, dict) else []
all_behaviors = ['闲聊', '帮助', '争吵', '交易', '赠礼', '赞扬']
COL_W = 8  # 每列视觉宽度
header = _vpad('', 16)
for b in all_behaviors:
    header += _vpad(b, COL_W)
print(header)
for name in sorted(npc_keys):
    d = npc_data.get(name, {}) if isinstance(npc_data, dict) else {}
    pers = d.get('性格', '')
    label = f'{name}({pers})'
    row = _vpad(f'  {label}', 16)
    if pers in personality_mult:
        for b in all_behaviors:
            v = personality_mult[pers].get(b, 1.0)
            row += _vpad(f'{v:.2f}', COL_W)
    else:
        for b in all_behaviors:
            row += _vpad('1.00', COL_W)
    print(row)
print('════════════')

e.scope_vars['最大天数'] = max_days
_trust_timeline = []  # [[day, {trust_key: val, ...}], ...]

try:
    for day in range(max_days):
        e.eval(['观察一日'])
        # 快照当天 NPC 互信数据（从根作用域读取，跨函数不丢失）
        td = e.scope_vars.get('NPC信任', {}) or {}
        snapshot = {k: v for k, v in td.items()}
        _trust_timeline.append((day + 1, snapshot))
        # 每日社交活跃排名（次数 + 净Δ）
        if _social_activity:
            ranked = sorted(_social_activity.items(), key=lambda x: -x[1][0])
            top = ' > '.join(f'{n}({c[0]}次, Δ{"+" if c[1] >= 0 else ""}{c[1]:.3f})' for n, c in ranked[:3])
            print(f'  今日活跃: {top}')
            _social_activity.clear()
        # #9 凝聚力指数
        td_now = e.scope_vars.get('NPC信任', {}) or {}
        vals = []
        for v in td_now.values():
            try:
                vals.append(to_float(v))
            except Exception:
                pass
        if vals:
            avg = sum(vals) / len(vals)
            active_vals = [v for v in vals if v > 0.01]
            active_avg = sum(active_vals) / len(active_vals) if active_vals else 0
            false_n = sum(1 for v in vals if v < 0.3)
            maybe_n = sum(1 for v in vals if 0.3 <= v < 0.7)
            true_n = sum(1 for v in vals if v >= 0.7)
            print(
                f'  凝聚力: {avg:.3f}(全部{len(vals)}对平均)  活跃:{active_avg:.3f}(已互动{len(active_vals)}对)  假:{false_n} 可能:{maybe_n} 真:{true_n}'
            )
            print(
                f'  三态: {_village_ternary.summary()}  {_village_ternary.trit_display(*_village_ternary.history[-1]) if _village_ternary.history else ""}'
            )
        # #3 每日矩阵（verbose 模式）
        if _verbose and _trust_timeline:
            td_now = _trust_timeline[-1][1]
            tkeys = list(td_now.keys())
            if tkeys:
                all_n = sorted(set(k.split('_')[0] for k in tkeys) | set(k.split('_')[1] for k in tkeys))
                if len(all_n) >= 2:
                    print(f'  ┌─ 第{day + 1}天互信矩阵')
                    for n1 in all_n:
                        row = '  │ ' + _vpad(n1[:6], 8)
                        for n2 in all_n:
                            if n1 == n2:
                                row += _vpad('·', 7)
                            else:
                                k = f'{min(n1, n2)}_{max(n1, n2)}'
                                v_raw = td_now.get(k, 0)
                                try:
                                    v = to_float(v_raw)
                                except Exception:
                                    v = 0.0
                                row += _vpad(f'{v:.2f}', 7)
                        print(row)
                    print('  └─')
        # #6 出场分布
        if _npc_daily:
            dist = ' '.join(f'{n}({c}次)' for n, c in sorted(_npc_daily.items(), key=lambda x: -x[1]))
            print(f'  出场分布: {dist}')
            _npc_daily.clear()
except (KeyboardInterrupt, ReturnException):
    print('结束')
except SystemExit:
    pass
finally:
    # ── 宏观趋势分析 ──
    if _trust_timeline and len(_trust_timeline) >= 2:
        print()
        print('══ 宏观趋势分析 ══')
        first = _trust_timeline[0][1]
        last = _trust_timeline[-1][1]
        # 只比较首末天均存在的键，避免单侧键污染总变动
        common = set(first.keys()) & set(last.keys())
        new_keys = set(last.keys()) - set(first.keys())
        gone_keys = set(first.keys()) - set(last.keys())
        # 找最长键名，统一列宽
        all_output_keys = list(common) + list(new_keys) + list(gone_keys)
        max_k_len = max(len(k) for k in all_output_keys) if all_output_keys else 10
        shown = 0
        unchanged_list = []
        for k in sorted(common):
            v0 = to_float(first.get(k, 0))
            vn = to_float(last.get(k, 0))
            delta = vn - v0
            if abs(delta) < 0.004:
                unchanged_list.append(f'  {k:<{max_k_len}} {v0:.3f}→{vn:.3f} ({delta:+.3f})')
                continue
            shown += 1
            arrow = '↗' if delta > 0.005 else ('↘' if delta < -0.005 else '→')
            print(f'  {k:<{max_k_len}} {v0:.3f} → {vn:.3f} {arrow} {delta:+.3f}')
        if shown == 0:
            print('  (无显著变动)')
        for item in unchanged_list:
            print(f'  微小变动: {item.strip()}')
        # 末天新出现 / 首天后消失的关系（同一列宽）
        if new_keys:
            for k in sorted(new_keys):
                print(f'  {k:<{max_k_len}} 新增={to_float(last[k]):.3f}')
        if gone_keys:
            for k in sorted(gone_keys):
                print(f'  {k:<{max_k_len}} 消失 (原{to_float(first[k]):.3f})')
        # 统计：仅按 common 键计算总变动
        total_days = len(_trust_timeline)
        total_delta = sum(to_float(last.get(k, 0)) - to_float(first.get(k, 0)) for k in common)
        warm = sum(1 for v in last.values() if to_float(v) >= 0.6)
        cold = sum(1 for v in last.values() if to_float(v) < 0.3)
        print(
            f'  共 {total_days} 天，{len(common)} 组持续关系'
            + (f'（+{len(new_keys)} 新增/-{len(gone_keys)} 消失）' if (new_keys or gone_keys) else '')
        )
        print(f'  总互信变动: {total_delta:+.3f}')
        print(f'  亲密(≥0.6): {warm}  冷淡(<0.3): {cold}')
        if total_delta > 0.03:
            print('  趋势: 村庄关系整体向好 ↑')
        elif total_delta < -0.03:
            print('  趋势: 村庄关系趋于冷淡 ↓')
        else:
            print('  趋势: 村庄关系基本稳定 →')
        print('══════════════════')
        # ── 事件时间线 ──
        event_days = sorted([k for k in _event_memory.keys() if k not in ('_chain',) and k.lstrip('-').isdigit()])
        if event_days:
            print()
            print('══ 事件时间线 ══')
            for d in event_days:
                for evt in _event_memory[d]:
                    print(f'  第{d}天  {evt}')
            # 因果链：同对 NPC 跨天重复出现
            chain = _event_memory.get('_链', [])
            pairs: dict = {}
            for c in chain:
                k = f'{min(c["n1"], c["n2"])}_{max(c["n1"], c["n2"])}'
                pairs.setdefault(k, []).append(c)
            has_causal = False
            for k, events in pairs.items():
                if len(events) >= 2:
                    if not has_causal:
                        print()
                        print('══ 因果链 ══')
                        has_causal = True
                    n1, n2 = events[0]['n1'], events[0]['n2']
                    chain_str = ' → '.join(
                        f'D{e["day"]}:{e["type"]}' for e in sorted(events, key=lambda x: int(x['day']))
                    )
                    print(f'  {n1}↔{n2}: {chain_str}')
            print('══════════════')
        # ── JSON 导出 ──
        json_out = []
        for day, snap in _trust_timeline:
            day_events = _event_memory.get(str(day), [])
            json_out.append(
                {
                    'day': day,
                    'trust': {k: float(to_float(v)) for k, v in snap.items()},
                    'events': day_events,
                }
            )
        with open('village_log.json', 'w', encoding='utf-8') as jf:
            json.dump(json_out, jf, ensure_ascii=False, indent=2)
        print('JSON 已导出到 village_log.json')
        # ── 三态演化报告 ──
        print('\n══ 三态演化报告 ══')
        print(f'  全局: {_village_ternary.summary()}  犹豫{_village_ternary.hesitation}次')
        for npc, eng in sorted(_npc_ternary.items()):
            if eng.history:
                print(f'  {npc[:4]:4s}: {eng.summary():>10s}  {eng.trit_display(*eng.history[-1])}')
        if _memory_chain:
            from collections import Counter

            pairs = Counter(f'{m["n1"][:2]}↔{m["n2"][:2]}' for m in _memory_chain)
            top_pairs = pairs.most_common(3)
            print(f'  活跃组合: {", ".join(f"{p}({c}次)" for p, c in top_pairs)}')
            conflicts = [m for m in _memory_chain if m['label'] == '争吵']
            print(
                f'  冲突事件: {len(conflicts)}起'
                + (f' ({", ".join(c["n1"][:2] + "↔" + c["n2"][:2] for c in conflicts[:3])})' if conflicts else '')
            )
        print('══════════════════')
        # ── #8 热力图：互信矩阵 ──
        if _trust_timeline:
            final = _trust_timeline[-1][1]
            all_names = sorted(set(k.split('_')[0] for k in final.keys()) | set(k.split('_')[1] for k in final.keys()))
            if len(all_names) >= 2:
                print()
                print('══ 互信矩阵 ══')
                M_W = 9  # 每列视觉宽度
                header = _vpad('', 10)
                for n in all_names:
                    header += _vpad(n[:4], M_W)
                print(header)
                for n1 in all_names:
                    row = _vpad(n1[:6], 10)
                    for n2 in all_names:
                        if n1 == n2:
                            row += _vpad('---', M_W)
                        else:
                            key = f'{min(n1, n2)}_{max(n1, n2)}'
                            v = to_float(final.get(key, 0))
                            if v >= 0.7:
                                mark = f'{v:.2f}●'
                            elif v >= 0.3:
                                mark = f'{v:.2f}◐'
                            else:
                                mark = f'{v:.2f}○'
                            row += _vpad(mark, M_W)
                    print(row)
                print('════════════')
        # ── 互信演化图（纯 HTML+SVG，零依赖）──
        chart_pairs: dict = {}  # {pair_name: [day_values]}
        all_days = set()
        for entry in json_out:
            all_days.add(entry['day'])
            for k, v in entry['trust'].items():
                chart_pairs.setdefault(k, []).append(v)
        if len(all_days) >= 2 and chart_pairs:
            days = sorted(all_days)
            n_days = len(days)
            # 筛选有变化的 pair，按末值排序
            active_pairs = []
            for pair, vals in sorted(chart_pairs.items()):
                if len(vals) < 2 or max(vals) - min(vals) < 0.002:
                    continue
                active_pairs.append((pair, vals))
            if active_pairs:
                w, h = 1300, 180 + 28 * len(active_pairs) + 22 * ((len(active_pairs) + 3) // 4)
                pad_l, pad_r, pad_t, pad_b = 140, 140, 30, 40
                plot_w = w - pad_l - pad_r
                plot_h = h - pad_t - pad_b
                # 颜色
                colors = [
                    '#e74c3c',
                    '#3498db',
                    '#2ecc71',
                    '#9b59b6',
                    '#f39c12',
                    '#1abc9c',
                    '#e67e22',
                    '#34495e',
                    '#e91e63',
                    '#00bcd4',
                    '#4caf50',
                    '#ff9800',
                ]
                # Y 轴自动适配数据范围（至少留 0.05 边距）
                all_vals = [v for _, vals in active_pairs for v in vals]
                y_min = max(0, min(all_vals) - 0.03)
                y_max = min(1.0, max(all_vals) + 0.05)
                if y_max - y_min < 0.1:
                    y_min, y_max = 0, 0.3  # 数据太集中时放大到 0~0.3
                y_range = y_max - y_min
                svg_parts = [
                    f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                    f'style="font-family:Microsoft YaHei,sans-serif;background:#1a1a2e">',
                ]
                # 三态背景色带（按数据范围映射）
                for lo, hi, color, label in [
                    (0, 0.3, '#ff444422', '假'),
                    (0.3, 0.7, '#ffaa0022', '可能'),
                    (0.7, 1.0, '#44ff4422', '真'),
                ]:
                    if hi <= y_min or lo >= y_max:
                        continue
                    b_lo = pad_t + plot_h * (1 - min(hi, y_max) / y_max)
                    b_hi = pad_t + plot_h * (1 - max(lo, y_min) / y_max)
                    if b_hi - b_lo < 1:
                        continue
                    svg_parts.append(
                        f'<rect x="{pad_l}" y="{b_lo:.0f}" width="{plot_w}" height="{b_hi - b_lo:.0f}" fill="{color}"/>'
                    )
                    svg_parts.append(
                        f'<text x="{pad_l + 5}" y="{b_lo + 14:.0f}" fill="{color[:7]}88" font-size="10">{label}</text>'
                    )
                # 网格
                for i in range(5):
                    y_val = y_min + i * y_range / 4
                    y = pad_t + plot_h * (1 - (y_val - y_min) / y_range)
                    svg_parts.append(
                        f'<line x1="{pad_l}" y1="{y:.0f}" x2="{w - pad_r}" y2="{y:.0f}" stroke="#ffffff15"/>'
                    )
                    svg_parts.append(
                        f'<text x="{pad_l - 8}" y="{y + 4:.0f}" fill="#aaa" font-size="10" text-anchor="end">{y_val:.2f}</text>'
                    )
                for di, d in enumerate(days):
                    x = pad_l + plot_w * di / max(n_days - 1, 1)
                    svg_parts.append(
                        f'<text x="{x:.0f}" y="{h - pad_b + 18}" fill="#aaa" font-size="10" text-anchor="middle">D{d}</text>'
                    )
                # 折线 + 交互悬停
                legend_items = []
                for ci, (pair, vals) in enumerate(active_pairs):
                    color = colors[ci % len(colors)]
                    gid = f'line_{ci}'
                    svg_parts.append(f'<g id="{gid}">')
                    pts = []
                    for di, v in enumerate(vals):
                        x = pad_l + plot_w * di / max(n_days - 1, 1)
                        y = pad_t + plot_h * (1 - (v - y_min) / y_range)
                        pts.append(f'{x:.1f},{y:.1f}')
                    svg_parts.append(
                        f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2.5"/>'
                    )
                    for di, v in enumerate(vals):
                        x = pad_l + plot_w * di / max(n_days - 1, 1)
                        y = pad_t + plot_h * (1 - (v - y_min) / y_range)
                        svg_parts.append(
                            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="#fff" stroke-width="1">'
                        )
                        svg_parts.append(f'<title>D{days[di]}: {pair} = {v:.3f}</title>')
                        svg_parts.append('</circle>')
                    svg_parts.append('</g>')
                    # 末值标注
                    x_last = pad_l + plot_w * (len(vals) - 1) / max(n_days - 1, 1)
                    y_last = pad_t + plot_h * (1 - vals[-1])
                    svg_parts.append(
                        f'<text x="{x_last + 5:.0f}" y="{y_last + 4:.0f}" fill="{color}" font-size="11">{pair}</text>'
                    )
                    legend_items.append((gid, color, pair))
                # 交互图例（网格布局）
                legend_y = pad_t + plot_h + 10
                for ci, (gid, color, pair) in enumerate(legend_items):
                    row = ci // 4
                    col = ci % 4
                    lx = pad_l + col * 170
                    ly = legend_y + row * 22
                    cb_id = f'cb_{gid}'
                    svg_parts.append(f'<foreignObject x="{lx}" y="{ly}" width="165" height="22">')
                    svg_parts.append(
                        f'<label xmlns="http://www.w3.org/1999/xhtml" style="color:{color};font-size:11px;cursor:pointer;white-space:nowrap">'
                    )
                    svg_parts.append(
                        f'<input type="checkbox" id="{cb_id}" checked onchange="document.getElementById(\'{gid}\').style.display=this.checked?\'block\':\'none\'" style="accent-color:{color};vertical-align:middle"/>'
                    )
                    svg_parts.append(f' {pair}</label></foreignObject>')
                # 标题
                svg_parts.append(
                    f'<text x="{w / 2:.0f}" y="20" fill="#fff" font-size="16" text-anchor="middle">桃花村 {max_days}天 互信演化</text>'
                )
                svg_parts.append('</svg>')
                with open('village_trust.html', 'w', encoding='utf-8') as hf:
                    hf.write(
                        '<html><head><meta charset="utf-8"><style>'
                        'body{margin:0;background:#1a1a2e;display:flex;justify-content:center;align-items:center;min-height:100vh}'
                        'svg{max-width:95vw;max-height:95vh}'
                        '</style></head><body>' + ''.join(svg_parts) + '</body></html>'
                    )
                print('互信演化图已保存到 village_trust.html')
        # ── 性能统计 ──
        elapsed = time.time() - _t_start
        print(f'\n模拟耗时: {elapsed:.1f}s  LLM调用: {_llm_calls}次')
        if _llm_times:
            for cat, (cnt, total_t) in sorted(_llm_times.items(), key=lambda x: -x[1][0]):
                avg_t = total_t / cnt if cnt > 0 else 0
                print(f'  LLM[{cat}]: {cnt}次 共{total_t:.1f}s 均{avg_t:.2f}s')
        log.close()
