#!/usr/bin/env python -X utf8
"""三态门控 vs 普通推理 对比基准 — 100 prompt统计"""

import torch
import numpy as np
import tiktoken
import ctypes
import collections
import time
import json
import os

weights = torch.load('csrc/tinystories_1m.bin', map_location='cpu', weights_only=True)
dim = 64
heads = 16
hd = dim // heads
layers = 8
lib_t = ctypes.CDLL('csrc/transformer_c.dll')
lib_t.layernorm.argtypes = [ctypes.c_void_p] * 4 + [ctypes.c_int, ctypes.c_float]
lib_t.gelu.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_int]
lib_s = ctypes.CDLL('csrc/softmax_c.dll')
lib_s.softmax_c.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_int]
enc = tiktoken.get_encoding('gpt2')
emb_w = weights['transformer.wte.weight'].numpy().astype(np.float32)
pos_w = weights['transformer.wpe.weight'].numpy().astype(np.float32)
rm = weights['transformer.h.0.attn.attention.bias'].numpy().astype(np.float32)
lfw = weights['transformer.ln_f.weight'].numpy().astype(np.float32)
lfb = weights['transformer.ln_f.bias'].numpy().astype(np.float32)

# 100 prompts from TinyStories style
PROMPTS = [
    'Once upon a time',
    'The little girl',
    'A big red',
    'I like to',
    'One day a small',
    'The sun was',
    'She went to',
    'He saw a',
    'There was a',
    'In the forest',
    'The old man',
    'A tiny bird',
    'On the farm',
    'The happy dog',
    'She looked at',
    'He wanted to',
    'It was a',
    'The cat sat',
    'They went to',
    'After the rain',
    'The magic wand',
    'A golden key',
    'Under the bed',
    'Behind the door',
    'The brave knight',
    'A friendly dragon',
    'On top of',
    'Inside the box',
    'She opened the',
    'He climbed the',
    'The river was',
    'A cloud shaped',
    'The wizard cast',
    'A butterfly landed',
    'She found a',
    'He built a',
    'The garden had',
    'A rainbow appeared',
    'She sang a',
    'He drew a',
    'The cookie jar',
    'A secret path',
    'The moonlight shone',
    'A sleepy bear',
    'The toy box',
    'A gentle breeze',
    'She whispered to',
    'He ran to',
    'The colorful fish',
    'A shiny stone',
    'She baked a',
    'He painted a',
    'The noisy crow',
    'A warm blanket',
    'The tall tree',
    'A sweet smell',
    'She danced with',
    'He played the',
    'The old clock',
    'A bright star',
    'She read a',
    'He wrote a',
    'The warm sun',
    'A cold wind',
    'She picked a',
    'He found the',
    'The deep well',
    'A fast horse',
    'She fed the',
    'He fixed the',
    'The broken toy',
    'A new friend',
    'She dreamed of',
    'He laughed at',
    'The soft pillow',
    'A loud noise',
    'She carried the',
    'He dropped the',
    'The empty room',
    'A full moon',
    'She saved the',
    'He lost his',
    'The hidden cave',
    'A silver bell',
    'She wore a',
    'He ate the',
    'The wooden bridge',
    'A paper boat',
    'She counted the',
    'He shared his',
    'The iron gate',
    'A glass window',
    'She waited for',
    'He listened to',
    'The dark tunnel',
    'A golden ring',
    'She followed the',
    'He called out',
    'The frozen lake',
    'A warm fire',
]


def process_prompt(ids):
    s = len(ids)
    h = emb_w[ids] + pos_w[:s]
    kvs = [None] * layers
    for li in range(layers):
        p = f'transformer.h.{li}'
        q = (h @ weights[f'{p}.attn.attention.q_proj.weight'].numpy().astype(np.float32).T).astype(np.float32)
        k = (h @ weights[f'{p}.attn.attention.k_proj.weight'].numpy().astype(np.float32).T).astype(np.float32)
        v = (h @ weights[f'{p}.attn.attention.v_proj.weight'].numpy().astype(np.float32).T).astype(np.float32)
        q_ = q.reshape(s, heads, hd).transpose(1, 0, 2)
        k_ = k.reshape(s, heads, hd).transpose(1, 0, 2)
        v_ = v.reshape(s, heads, hd).transpose(1, 0, 2)
        out = np.zeros((heads, s, hd), dtype=np.float32)
        for hi in range(heads):
            qh = q_[hi]
            kh = k_[hi]
            vh = v_[hi]
            sc = (qh @ kh.T / np.sqrt(hd)).astype(np.float32) + np.where(rm[0, 0, :s, :s] == 0, -1e9, 0.0).astype(
                np.float32
            )
            aw = np.zeros_like(sc)
            for i in range(s):
                lib_s.softmax_c(sc[i].ctypes.data, aw[i].ctypes.data, s)
            out[hi] = (aw @ vh).astype(np.float32)
        attn = out.transpose(1, 0, 2).reshape(s, dim)
        h1 = h + (attn @ weights[f'{p}.attn.attention.out_proj.weight'].numpy().astype(np.float32).T).astype(np.float32)
        lw = weights[f'{p}.ln_1.weight'].numpy().astype(np.float32)
        lb = weights[f'{p}.ln_1.bias'].numpy().astype(np.float32)
        h1l = np.zeros_like(h1)
        for i in range(s):
            lib_t.layernorm(h1[i].ctypes.data, lw.ctypes.data, lb.ctypes.data, h1l[i].ctypes.data, dim, 1e-5)
        w1 = weights[f'{p}.mlp.c_fc.weight'].numpy().astype(np.float32)
        b1 = weights[f'{p}.mlp.c_fc.bias'].numpy().astype(np.float32)
        w2 = weights[f'{p}.mlp.c_proj.weight'].numpy().astype(np.float32)
        b2 = weights[f'{p}.mlp.c_proj.bias'].numpy().astype(np.float32)
        ffnh = (h1l @ w1.T + b1).astype(np.float32)
        ffna = np.zeros_like(ffnh)
        for i in range(s):
            lib_t.gelu(ffnh[i].ctypes.data, ffna[i].ctypes.data, 256)
        h2 = h1l + (ffna @ w2.T + b2).astype(np.float32)
        l2w = weights[f'{p}.ln_2.weight'].numpy().astype(np.float32)
        l2b = weights[f'{p}.ln_2.bias'].numpy().astype(np.float32)
        for i in range(s):
            lib_t.layernorm(h2[i].ctypes.data, l2w.ctypes.data, l2b.ctypes.data, h2[i].ctypes.data, dim, 1e-5)
        h = h2
        kvs[li] = (k_, v_)
    return h[-1:], kvs


def layer_cached(h_new, li, past_kv):
    p = f'transformer.h.{li}'
    q = (
        (h_new @ weights[f'{p}.attn.attention.q_proj.weight'].numpy().astype(np.float32).T)
        .astype(np.float32)
        .reshape(1, heads, hd)
        .transpose(1, 0, 2)
    )
    k = (
        (h_new @ weights[f'{p}.attn.attention.k_proj.weight'].numpy().astype(np.float32).T)
        .astype(np.float32)
        .reshape(1, heads, hd)
        .transpose(1, 0, 2)
    )
    v = (
        (h_new @ weights[f'{p}.attn.attention.v_proj.weight'].numpy().astype(np.float32).T)
        .astype(np.float32)
        .reshape(1, heads, hd)
        .transpose(1, 0, 2)
    )
    if past_kv is not None:
        past_k, past_v = past_kv
        k_full = np.concatenate([past_k, k], axis=1)
        v_full = np.concatenate([past_v, v], axis=1)
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
    h1 = h_new + (attn @ weights[f'{p}.attn.attention.out_proj.weight'].numpy().astype(np.float32).T).astype(np.float32)
    lw = weights[f'{p}.ln_1.weight'].numpy().astype(np.float32)
    lb = weights[f'{p}.ln_1.bias'].numpy().astype(np.float32)
    h1l = np.zeros_like(h1)
    lib_t.layernorm(h1[0].ctypes.data, lw.ctypes.data, lb.ctypes.data, h1l[0].ctypes.data, dim, 1e-5)
    w1 = weights[f'{p}.mlp.c_fc.weight'].numpy().astype(np.float32)
    b1 = weights[f'{p}.mlp.c_fc.bias'].numpy().astype(np.float32)
    w2 = weights[f'{p}.mlp.c_proj.weight'].numpy().astype(np.float32)
    b2 = weights[f'{p}.mlp.c_proj.bias'].numpy().astype(np.float32)
    ffnh = (h1l @ w1.T + b1).astype(np.float32)
    ffna = np.zeros_like(ffnh)
    lib_t.gelu(ffnh[0].ctypes.data, ffna[0].ctypes.data, 256)
    h2 = h1l + (ffna @ w2.T + b2).astype(np.float32)
    l2w = weights[f'{p}.ln_2.weight'].numpy().astype(np.float32)
    l2b = weights[f'{p}.ln_2.bias'].numpy().astype(np.float32)
    lib_t.layernorm(h2[0].ctypes.data, l2w.ctypes.data, l2b.ctypes.data, h2[0].ctypes.data, dim, 1e-5)
    return h2, (k_full, v_full)


def trajectory_check(ids, window=32):
    recent = ids[-window:] if len(ids) >= window else ids
    n = len(recent)
    if n < 8:
        return 'OK', 0.0, ''
    unique_ratio = len(set(recent)) / n
    reasons = []
    if unique_ratio < 0.15:
        reasons.append('重复率过高')
    for period in range(2, min(9, n // 2 + 1)):
        matches = 0
        for i in range(period, n):
            if recent[i] == recent[i - period]:
                matches += 1
        if matches > (n - period) * 0.7:
            reasons.append(f'周期{period}')
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
    if sum(1 for t in recent if t in func_set) > n * 0.7:
        reasons.append('功能词密集')
    if n >= 16:
        first = set(recent[: n // 2])
        second = set(recent[n // 2 :])
        if len(second - first) == 0:
            reasons.append('无新词')
    info_parts = reasons.copy() if reasons else []
    info_parts.append(f'ur={unique_ratio:.2f}')
    if len(reasons) >= 2:
        return 'NEGATE', unique_ratio, ','.join(info_parts)
    elif len(reasons) == 1:
        return 'UNCERTAIN', unique_ratio, ','.join(info_parts)
    return 'OK', unique_ratio, ','.join(info_parts)


def ternary_sample(logits, recent, ids):
    lt = logits.copy()
    for tid in recent:
        lt[tid] /= 1.15
    lt /= 0.8
    lt -= lt.max()
    probs = np.exp(lt)
    probs /= probs.sum()
    top_prob = probs.max()
    traj, score, reason = trajectory_check(ids)
    if traj == 'NEGATE':
        return None, top_prob, 'traj_negate'
    if top_prob > 0.9:
        return int(np.argmax(probs)), top_prob, 'affirm'
    elif top_prob > 0.3:
        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        return int(idx[np.random.choice(50, p=tp)]), top_prob, 'maybe'
    return None, top_prob, 'conf_negate'


def plain_sample(logits, recent):
    """对照组: 普通EOS + repetition penalty"""
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


def run_one(prompt, use_ternary=True):
    ids = enc.encode(prompt)
    recent = collections.deque(maxlen=8)
    _, kvs = process_prompt(ids)
    stop_reason = 'max_steps'
    uncertain_count = 0
    for step in range(64):
        pos_idx = len(ids)
        h_new = emb_w[ids[-1:]] + pos_w[pos_idx : pos_idx + 1]
        for li in range(layers):
            h_new, kvs[li] = layer_cached(h_new, li, kvs[li])
        fn = h_new.copy()
        lib_t.layernorm(fn[0].ctypes.data, lfw.ctypes.data, lfb.ctypes.data, fn[0].ctypes.data, dim, 1e-5)
        logits = (fn @ emb_w.T)[0]
        if use_ternary:
            tok, conf, reason = ternary_sample(logits, recent, ids)
            if tok is None:
                stop_reason = reason
                break
            if reason in ('maybe', 'traj_negate'):
                uncertain_count += 1
            else:
                uncertain_count = 0
            if uncertain_count >= 4:
                stop_reason = f'persist_{uncertain_count}'
                break
        else:
            tok = plain_sample(logits, recent)
        ids.append(int(tok))
        recent.append(int(tok))
    w = min(len(ids), 32)
    rw = ids[-w:]
    ur = len(set(rw)) / max(w, 1)
    gen_len = len(ids) - len(enc.encode(prompt))
    return {'gen_len': gen_len, 'stop_reason': stop_reason, 'ur': ur, 'ids': ids}


# Run benchmark
np.random.seed(42)
results_ternary = []
results_plain = []
print(f'Benchmark: {len(PROMPTS)} prompts × 2 modes')
t0 = time.perf_counter()
for i, prompt in enumerate(PROMPTS):
    r = run_one(prompt, use_ternary=True)
    results_ternary.append(r)
    if (i + 1) % 20 == 0:
        print(f'  ternary {i + 1}/{len(PROMPTS)}')
dt_ternary = time.perf_counter() - t0

t0 = time.perf_counter()
for i, prompt in enumerate(PROMPTS):
    r = run_one(prompt, use_ternary=False)
    results_plain.append(r)
    if (i + 1) % 20 == 0:
        print(f'  plain   {i + 1}/{len(PROMPTS)}')
dt_plain = time.perf_counter() - t0


# Stats
def stats(rs, name):
    lens = [r['gen_len'] for r in rs]
    stops = [r for r in rs if r['stop_reason'] != 'max_steps']
    urns = [r['ur'] for r in rs]
    loops = [r for r in rs if r['ur'] < 0.3]
    print(f'\n{name}:')
    print(f'  平均生成长度: {np.mean(lens):.1f} token')
    print(f'  主动停止率:   {len(stops) / len(rs) * 100:.1f}% ({len(stops)}/{len(rs)})')
    print(f'  循环率(ur<0.3): {len(loops) / len(rs) * 100:.1f}% ({len(loops)}/{len(rs)})')
    print(f'  平均 unique_ratio: {np.mean(urns):.2f}')
    print(f'  耗时:          {dt_ternary if "ternary" in name else dt_plain:.1f}s')
    return {
        'avg_len': np.mean(lens),
        'stop_rate': len(stops) / len(rs),
        'loop_rate': len(loops) / len(rs),
        'avg_ur': np.mean(urns),
    }


s_t = stats(results_ternary, '三态门控')
s_p = stats(results_plain, '普通推理(对照组)')

print(f'\n{"=" * 50}')
print('  对比')
print(f'{"=" * 50}')
print(f'  生成字长:     三态 {s_t["avg_len"]:.0f} vs 普通 {s_p["avg_len"]:.0f}')
print(f'  主动停止率:   三态 {s_t["stop_rate"] * 100:.0f}% vs 普通 {s_p["stop_rate"] * 100:.0f}%')
print(f'  循环率:       三态 {s_t["loop_rate"] * 100:.0f}% vs 普通 {s_p["loop_rate"] * 100:.0f}%')

# Save
os.makedirs('benchmarks', exist_ok=True)
with open('benchmarks/ternary_vs_plain.json', 'w') as f:
    json.dump({'ternary': s_t, 'plain': s_p, 'n': len(PROMPTS)}, f, indent=2)
print('\nSaved: benchmarks/ternary_vs_plain.json')
