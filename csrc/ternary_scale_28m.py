#!/usr/bin/env python -X utf8
"""三态门控大基准 — 28M 1000 prompt（修正 UR=0.30 阈值）"""

import torch
import numpy as np
import tiktoken
import ctypes
import collections
import time
import json
import os

lib_t = ctypes.CDLL('csrc/transformer_c.dll')
lib_t.layernorm.argtypes = [ctypes.c_void_p] * 4 + [ctypes.c_int, ctypes.c_float]
lib_t.gelu.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_int]
lib_s = ctypes.CDLL('csrc/softmax_c.dll')
lib_s.softmax_c.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_int]
enc = tiktoken.get_encoding('gpt2')

w, dim, heads, hd = torch.load('csrc/tinystories_28m.bin', map_location='cpu', weights_only=True), 512, 16, 32
layers = 8
inter = 2048
emb_w = w['transformer.wte.weight'].numpy().astype(np.float32)
pos_w = w['transformer.wpe.weight'].numpy().astype(np.float32)
rm = w['transformer.h.0.attn.attention.bias'].numpy().astype(np.float32)
lfw = w['transformer.ln_f.weight'].numpy().astype(np.float32)
lfb = w['transformer.ln_f.bias'].numpy().astype(np.float32)


# ── 推理引擎 ──
def process(ids):
    s = len(ids)
    h = emb_w[ids] + pos_w[:s]
    kvs = [None] * layers
    for li in range(layers):
        p = f'transformer.h.{li}'
        q = (
            (h @ w[f'{p}.attn.attention.q_proj.weight'].numpy().astype(np.float32).T)
            .astype(np.float32)
            .reshape(s, heads, hd)
            .transpose(1, 0, 2)
        )
        k = (
            (h @ w[f'{p}.attn.attention.k_proj.weight'].numpy().astype(np.float32).T)
            .astype(np.float32)
            .reshape(s, heads, hd)
            .transpose(1, 0, 2)
        )
        v = (
            (h @ w[f'{p}.attn.attention.v_proj.weight'].numpy().astype(np.float32).T)
            .astype(np.float32)
            .reshape(s, heads, hd)
            .transpose(1, 0, 2)
        )
        out = np.zeros((heads, s, hd), dtype=np.float32)
        for hi in range(heads):
            qh = q[hi]
            kh = k[hi]
            vh = v[hi]
            sc = (qh @ kh.T / np.sqrt(hd)).astype(np.float32) + np.where(rm[0, 0, :s, :s] == 0, -1e9, 0.0).astype(
                np.float32
            )
            aw = np.zeros_like(sc)
            for i in range(s):
                lib_s.softmax_c(sc[i].ctypes.data, aw[i].ctypes.data, s)
            out[hi] = (aw @ vh).astype(np.float32)
        attn = out.transpose(1, 0, 2).reshape(s, dim)
        h1 = h + (attn @ w[f'{p}.attn.attention.out_proj.weight'].numpy().astype(np.float32).T).astype(np.float32)
        lw = w[f'{p}.ln_1.weight'].numpy().astype(np.float32)
        lb = w[f'{p}.ln_1.bias'].numpy().astype(np.float32)
        h1l = np.zeros_like(h1)
        for i in range(s):
            lib_t.layernorm(h1[i].ctypes.data, lw.ctypes.data, lb.ctypes.data, h1l[i].ctypes.data, dim, 1e-5)
        w1 = w[f'{p}.mlp.c_fc.weight'].numpy().astype(np.float32)
        b1 = w[f'{p}.mlp.c_fc.bias'].numpy().astype(np.float32)
        w2 = w[f'{p}.mlp.c_proj.weight'].numpy().astype(np.float32)
        b2 = w[f'{p}.mlp.c_proj.bias'].numpy().astype(np.float32)
        ffnh = (h1l @ w1.T + b1).astype(np.float32)
        ffna = np.zeros_like(ffnh)
        for i in range(s):
            lib_t.gelu(ffnh[i].ctypes.data, ffna[i].ctypes.data, inter)
        h2 = h1l + (ffna @ w2.T + b2).astype(np.float32)
        l2w = w[f'{p}.ln_2.weight'].numpy().astype(np.float32)
        l2b = w[f'{p}.ln_2.bias'].numpy().astype(np.float32)
        for i in range(s):
            lib_t.layernorm(h2[i].ctypes.data, l2w.ctypes.data, l2b.ctypes.data, h2[i].ctypes.data, dim, 1e-5)
        h = h2
        kvs[li] = (k, v)
    return h[-1:], kvs


def cached_step(h_new, li, past_kv):
    p = f'transformer.h.{li}'
    q = (
        (h_new @ w[f'{p}.attn.attention.q_proj.weight'].numpy().astype(np.float32).T)
        .astype(np.float32)
        .reshape(1, heads, hd)
        .transpose(1, 0, 2)
    )
    k = (
        (h_new @ w[f'{p}.attn.attention.k_proj.weight'].numpy().astype(np.float32).T)
        .astype(np.float32)
        .reshape(1, heads, hd)
        .transpose(1, 0, 2)
    )
    v = (
        (h_new @ w[f'{p}.attn.attention.v_proj.weight'].numpy().astype(np.float32).T)
        .astype(np.float32)
        .reshape(1, heads, hd)
        .transpose(1, 0, 2)
    )
    if past_kv is not None:
        pk, pv = past_kv
        k_full = np.concatenate([pk, k], axis=1)
        v_full = np.concatenate([pv, v], axis=1)
    else:
        k_full = k
        v_full = v
    tl = k_full.shape[1]
    out = np.zeros((heads, 1, hd), dtype=np.float32)
    for hi in range(heads):
        qh = q[hi]
        kh = k_full[hi]
        vh = v_full[hi]
        sc = (qh @ kh.T / np.sqrt(hd)).astype(np.float32)
        aw = np.zeros((1, tl), dtype=np.float32)
        lib_s.softmax_c(sc[0].ctypes.data, aw[0].ctypes.data, tl)
        out[hi] = (aw @ vh).astype(np.float32)
    attn = out.transpose(1, 0, 2).reshape(1, dim)
    h1 = h_new + (attn @ w[f'{p}.attn.attention.out_proj.weight'].numpy().astype(np.float32).T).astype(np.float32)
    lw = w[f'{p}.ln_1.weight'].numpy().astype(np.float32)
    lb = w[f'{p}.ln_1.bias'].numpy().astype(np.float32)
    h1l = np.zeros_like(h1)
    lib_t.layernorm(h1[0].ctypes.data, lw.ctypes.data, lb.ctypes.data, h1l[0].ctypes.data, dim, 1e-5)
    w1 = w[f'{p}.mlp.c_fc.weight'].numpy().astype(np.float32)
    b1 = w[f'{p}.mlp.c_fc.bias'].numpy().astype(np.float32)
    w2 = w[f'{p}.mlp.c_proj.weight'].numpy().astype(np.float32)
    b2 = w[f'{p}.mlp.c_proj.bias'].numpy().astype(np.float32)
    ffnh = (h1l @ w1.T + b1).astype(np.float32)
    ffna = np.zeros_like(ffnh)
    lib_t.gelu(ffnh[0].ctypes.data, ffna[0].ctypes.data, inter)
    h2 = h1l + (ffna @ w2.T + b2).astype(np.float32)
    l2w = w[f'{p}.ln_2.weight'].numpy().astype(np.float32)
    l2b = w[f'{p}.ln_2.bias'].numpy().astype(np.float32)
    lib_t.layernorm(h2[0].ctypes.data, l2w.ctypes.data, l2b.ctypes.data, h2[0].ctypes.data, dim, 1e-5)
    return h2, (k_full, v_full)


def forward_step(ids, kvs):
    pos_idx = len(ids)
    h_new = emb_w[ids[-1:]] + pos_w[pos_idx : pos_idx + 1]
    for li in range(layers):
        h_new, kvs[li] = cached_step(h_new, li, kvs[li])
    fn = h_new.copy()
    lib_t.layernorm(fn[0].ctypes.data, lfw.ctypes.data, lfb.ctypes.data, fn[0].ctypes.data, dim, 1e-5)
    return (fn @ emb_w.T)[0], kvs


# ── 轨迹检测（UR=0.30，多信号综合） ──
UR_TH = 0.30


def traject(ids):
    r = ids[-32:] if len(ids) >= 32 else ids
    n = len(r)
    if n < 8:
        return 'OK', 1.0, 'short'
    ur = len(set(r)) / n
    reasons = []
    if ur < UR_TH:
        return 'NEGATE', ur, f'UR={ur:.2f}'
    for period in range(2, min(9, n // 2 + 1)):
        m = sum(1 for i in range(period, n) if r[i] == r[i - period])
        if m > (n - period) * 0.7:
            reasons.append(f'CYC{period}')
            break
    func_set = {
        345,
        346,
        347,
        348,
        349,
        350,
        351,
        352,
        353,
        354,
        355,
        356,
        286,
        287,
        257,
        261,
        262,
        263,
        264,
        265,
        266,
        267,
        268,
        319,
        320,
        321,
        322,
        616,
        617,
        660,
    }
    if sum(1 for t in r if t in func_set) > n * 0.7:
        reasons.append('FUNC')
    if n >= 16 and len(set(r[n // 2 :]) - set(r[: n // 2])) == 0:
        reasons.append('NONEW')
    reasons.append(f'UR={ur:.2f}')
    if len(reasons) >= 3:
        return 'NEGATE', ur, ';'.join(reasons)
    if len(reasons) >= 2:
        return 'UNCERTAIN', ur, ';'.join(reasons)
    return 'OK', ur, ';'.join(reasons)


# ── 三种策略 ──
TER_STATS = {'reasons': collections.Counter(), 'stop_urs': []}


def sample_ternary(logits, recent, ids, unc_count):
    lt = logits.copy()
    for tid in recent:
        lt[tid] /= 1.15
    lt /= 0.8
    lt -= lt.max()
    probs = np.exp(lt)
    probs /= probs.sum()
    g, ur, reason = traject(ids)
    if g == 'NEGATE':
        TER_STATS['reasons'][reason] += 1
        TER_STATS['stop_urs'].append(ur)
        return None, 'traj:' + reason.split(';')[0]
    if g == 'UNCERTAIN':
        if unc_count >= 4:
            TER_STATS['reasons']['persist:' + reason.split(';')[0]] += 1
            return None, 'persist'
        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        return int(idx[np.random.choice(50, p=tp)]), 'maybe'
    idx = np.argsort(-probs)[:50]
    tp = probs[idx]
    tp /= tp.sum()
    return int(idx[np.random.choice(50, p=tp)]), 'ok'


REP_STATS = {'loops': 0}


def sample_rep_penalty(logits, recent):
    lt = logits.copy()
    for tid in recent:
        lt[tid] /= 1.15
    lt /= 0.8
    lt -= lt.max()
    probs = np.exp(lt)
    probs /= probs.sum()
    idx = np.argsort(-probs)[:50]
    tp = probs[idx]
    tp /= tp.sum()
    return int(idx[np.random.choice(50, p=tp)])


EOS_STATS = {'loops': 0}


def sample_eos(logits):
    lt = logits.copy()
    lt /= 0.8
    lt -= lt.max()
    probs = np.exp(lt)
    probs /= probs.sum()
    idx = np.argsort(-probs)[:50]
    tp = probs[idx]
    tp /= tp.sum()
    return int(idx[np.random.choice(50, p=tp)])


# ── 循环检测（用于 plain 策略） ──
def has_loop(ids):
    recent = ids[-32:] if len(ids) >= 32 else ids
    n = len(recent)
    if n < 16:
        return False
    for period in range(2, 6):
        m = sum(1 for i in range(period, n) if recent[i] == recent[i - period])
        if m > (n - period) * 0.85:
            return True
    return False


# ── 运行 ──
def run_one(prompt, strategy, max_steps=64):
    ids = enc.encode(prompt)
    recent = collections.deque(maxlen=8)
    _, kvs = process(ids)
    unc = 0
    for step in range(max_steps):
        logits, kvs = forward_step(ids, kvs)
        if strategy == 'ternary':
            tok, reason = sample_ternary(logits, recent, ids, unc)
            if tok is None:
                return step, reason
            if reason == 'maybe':
                unc += 1
            else:
                unc = 0
        elif strategy == 'rep_penalty':
            tok = sample_rep_penalty(logits, recent)
        else:
            tok = sample_eos(logits)
        ids.append(int(tok))
        recent.append(int(tok))
    if strategy != 'ternary' and has_loop(ids):
        stats = REP_STATS if strategy == 'rep_penalty' else EOS_STATS
        stats['loops'] += 1
    return max_steps, 'max_steps'


# ── 1000 prompts ──
np.random.seed(42)
templates = [
    'Once upon a time',
    'The little',
    'A big',
    'I like to',
    'One day a',
    'The sun was',
    'She went to',
    'He saw a',
    'There was a',
    'In the forest',
    'The old',
    'A tiny',
    'On the farm',
    'The happy',
    'She looked at',
    'He wanted to',
    'It was a',
    'The cat',
    'They went to',
    'After the rain',
    'The magic',
    'A golden',
    'Under the',
    'Behind the',
    'The brave',
    'A friendly',
    'On top of',
    'Inside the',
]
extras = [
    'girl',
    'boy',
    'dog',
    'cat',
    'bird',
    'rabbit',
    'tree',
    'house',
    'car',
    'book',
    'river',
    'mountain',
    'star',
    'moon',
    'sun',
    'cloud',
    'flower',
    'fish',
    'bear',
    'mouse',
]
prompts_1000 = []
for i in range(1000):
    t = templates[i % len(templates)]
    e = extras[(i // len(templates)) % len(extras)]
    prompts_1000.append(f'{t} {e}')

print(f'Benchmark: 28M, {len(prompts_1000)} prompts × 3 strategies, UR_TH={UR_TH}')
results = []

for strategy, name in [('ternary', '三态门控'), ('rep_penalty', '重复惩罚'), ('eos', 'EOS-only')]:
    lengths = []
    stops = 0
    if strategy == 'ternary':
        TER_STATS['reasons'].clear()
        TER_STATS['stop_urs'].clear()
    t0 = time.perf_counter()
    for i, p in enumerate(prompts_1000):
        rl, reason = run_one(p, strategy)
        lengths.append(rl)
        if reason != 'max_steps':
            stops += 1
        if i % 100 == 99:
            print(f'  {name} {i + 1}/{len(prompts_1000)}')
    dt = time.perf_counter() - t0
    avg_len = np.mean(lengths)
    stop_rate = stops / len(prompts_1000) * 100
    entry = {'model': '28M', 'strategy': name, 'avg_len': float(avg_len), 'stop_rate': float(stop_rate), 'time': dt}
    if strategy == 'ternary':
        entry['stop_reasons'] = len(TER_STATS['stop_urs'])
        entry['top_reasons'] = TER_STATS['reasons'].most_common(10)
    elif strategy in ('rep_penalty', 'eos'):
        s = REP_STATS if strategy == 'rep_penalty' else EOS_STATS
        entry['loops'] = s['loops']
    results.append(entry)
    loops = REP_STATS.get('loops', EOS_STATS.get('loops', 0))
    print(f'  {name:8s}: avg_len={avg_len:.1f} stop={stop_rate:.0f}% loops={loops} time={dt:.0f}s')

os.makedirs('benchmarks', exist_ok=True)
with open('benchmarks/ternary_scale_28m.json', 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print('\nSaved: benchmarks/ternary_scale_28m.json')
print(f'  UR_TH={UR_TH}')
print(f'  Stop reasons: {dict(TER_STATS["reasons"].most_common())}')
