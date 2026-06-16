#!/usr/bin/env python -X utf8
"""三态门控大基准 — 1000 prompt × 3模型 × 3策略"""

import torch
import numpy as np
import tiktoken
import ctypes
import collections
import time
import json
import os


# ── 模型加载 ──
def load_model(path):
    w = torch.load(path, map_location='cpu', weights_only=True)
    dim = w['transformer.wte.weight'].shape[1]
    heads = 16
    hd = dim // heads
    layers = len([k for k in w.keys() if 'ln_1.weight' in k and 'h.' in k])
    intermediate = w['transformer.h.0.mlp.c_fc.weight'].shape[0]
    return w, dim, heads, hd, layers, intermediate


# ── 推理函数(参数化) ──
lib_t = ctypes.CDLL('csrc/transformer_c.dll')
lib_t.layernorm.argtypes = [ctypes.c_void_p] * 4 + [ctypes.c_int, ctypes.c_float]
lib_t.gelu.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_int]
lib_s = ctypes.CDLL('csrc/softmax_c.dll')
lib_s.softmax_c.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_int]
enc = tiktoken.get_encoding('gpt2')


def make_engine(w, dim, heads, hd, layers, intermediate):
    emb_w = w['transformer.wte.weight'].numpy().astype(np.float32)
    pos_w = w['transformer.wpe.weight'].numpy().astype(np.float32)
    rm = w['transformer.h.0.attn.attention.bias'].numpy().astype(np.float32)
    lfw = w['transformer.ln_f.weight'].numpy().astype(np.float32)
    lfb = w['transformer.ln_f.bias'].numpy().astype(np.float32)

    def process(ids):
        s = len(ids)
        h = emb_w[ids] + pos_w[:s]
        kvs = [None] * layers
        for li in range(layers):
            p = f'transformer.h.{li}'
            q = (h @ w[f'{p}.attn.attention.q_proj.weight'].numpy().astype(np.float32).T).astype(np.float32)
            k = (h @ w[f'{p}.attn.attention.k_proj.weight'].numpy().astype(np.float32).T).astype(np.float32)
            v = (h @ w[f'{p}.attn.attention.v_proj.weight'].numpy().astype(np.float32).T).astype(np.float32)
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
                lib_t.gelu(ffnh[i].ctypes.data, ffna[i].ctypes.data, intermediate)
            h2 = h1l + (ffna @ w2.T + b2).astype(np.float32)
            l2w = w[f'{p}.ln_2.weight'].numpy().astype(np.float32)
            l2b = w[f'{p}.ln_2.bias'].numpy().astype(np.float32)
            for i in range(s):
                lib_t.layernorm(h2[i].ctypes.data, l2w.ctypes.data, l2b.ctypes.data, h2[i].ctypes.data, dim, 1e-5)
            h = h2
            kvs[li] = (k_, v_)
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
        lib_t.gelu(ffnh[0].ctypes.data, ffna[0].ctypes.data, intermediate)
        h2 = h1l + (ffna @ w2.T + b2).astype(np.float32)
        l2w = w[f'{p}.ln_2.weight'].numpy().astype(np.float32)
        l2b = w[f'{p}.ln_2.bias'].numpy().astype(np.float32)
        lib_t.layernorm(h2[0].ctypes.data, l2w.ctypes.data, l2b.ctypes.data, h2[0].ctypes.data, dim, 1e-5)
        return h2, (k_full, v_full)

    def forward(ids, kvs):
        pos_idx = len(ids)
        h_new = emb_w[ids[-1:]] + pos_w[pos_idx : pos_idx + 1]
        for li in range(layers):
            h_new, kvs[li] = cached_step(h_new, li, kvs[li])
        fn = h_new.copy()
        lib_t.layernorm(fn[0].ctypes.data, lfw.ctypes.data, lfb.ctypes.data, fn[0].ctypes.data, dim, 1e-5)
        return (fn @ emb_w.T)[0], kvs

    return process, forward


# ── 轨迹检测 ──
def trajectory_check(ids, window=32):
    recent = ids[-window:] if len(ids) >= window else ids
    n = len(recent)
    if n < 8:
        return 'OK', 0.0, ''
    ur = len(set(recent)) / n
    reasons = []
    if ur < 0.15:
        reasons.append('重复率过高')
    for period in range(2, min(9, n // 2 + 1)):
        m = sum(1 for i in range(period, n) if recent[i] == recent[i - period])
        if m > (n - period) * 0.7:
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
        f = set(recent[: n // 2])
        s = set(recent[n // 2 :])
        if len(s - f) == 0:
            reasons.append('无新词')
    info = ','.join(reasons) if reasons else f'ur={ur:.2f}'
    if len(reasons) >= 2:
        return 'NEGATE', ur, info
    elif len(reasons) == 1:
        return 'UNCERTAIN', ur, info
    return 'OK', ur, info


# ── 三种策略 ──
def sample_ternary(logits, recent, ids, uncertain_count):
    lt = logits.copy()
    for tid in recent:
        lt[tid] /= 1.15
    lt /= 0.8
    lt -= lt.max()
    probs = np.exp(lt)
    probs /= probs.sum()
    traj, _, _ = trajectory_check(ids)
    if traj == 'NEGATE':
        return None, 0, 'traj'
    if traj == 'UNCERTAIN':
        if uncertain_count >= 3:
            return None, 0, 'persist'
        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        return int(idx[np.random.choice(50, p=tp)]), probs.max(), 'maybe'
    if probs.max() > 0.9:
        return int(np.argmax(probs)), probs.max(), 'affirm'
    elif probs.max() > 0.3:
        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        return int(idx[np.random.choice(50, p=tp)]), probs.max(), 'maybe'
    return None, probs.max(), 'conf'


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


# ── 运行 ──
def run(engine, prompt, strategy, max_steps=64):
    process, forward = engine
    ids = enc.encode(prompt)
    recent = collections.deque(maxlen=8)
    _, kvs = process(ids)
    uncertain_count = 0
    for step in range(max_steps):
        logits, kvs = forward(ids, kvs)
        if strategy == 'ternary':
            tok, _, reason = sample_ternary(logits, recent, ids, uncertain_count)
            if tok is None:
                return step, reason
            if reason in ('maybe', 'traj'):
                uncertain_count += 1
            else:
                uncertain_count = 0
        elif strategy == 'rep_penalty':
            tok = sample_rep_penalty(logits, recent)
        else:
            tok = sample_eos(logits)
        ids.append(int(tok))
        recent.append(int(tok))
    return max_steps, 'max_steps'


# ── 生成1000 prompt ──
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

print(f'Benchmark: {len(prompts_1000)} prompts × 3 strategies')
model_sizes = []

# 只跑3.6M (28M太慢)
for model_name, path in [('3.6M', 'csrc/tinystories_1m.bin')]:
    if not os.path.exists(path):
        continue
    print(f'\n{"=" * 50}\n  Model: {model_name}\n{"=" * 50}')
    w, dim, heads, hd, layers, intermediate = load_model(path)
    engine = make_engine(w, dim, heads, hd, layers, intermediate)

    for strategy, name in [('ternary', '三态门控'), ('rep_penalty', '重复惩罚'), ('eos', 'EOS-only')]:
        lengths = []
        stops = 0
        t0 = time.perf_counter()
        for i, p in enumerate(prompts_1000):
            rl, reason = run(engine, p, strategy)
            lengths.append(rl)
            if reason != 'max_steps':
                stops += 1
        dt = time.perf_counter() - t0

        avg_len = np.mean(lengths)
        stop_rate = stops / len(prompts_1000) * 100
        model_sizes.append(
            {'model': model_name, 'strategy': name, 'avg_len': avg_len, 'stop_rate': stop_rate, 'time': dt}
        )
        print(f'  {name:8s}: avg_len={avg_len:.1f} stop={stop_rate:.0f}% time={dt:.0f}s')

os.makedirs('benchmarks', exist_ok=True)
with open('benchmarks/ternary_scale.json', 'w') as f:
    json.dump(model_sizes, f, indent=2)
print('\nSaved: benchmarks/ternary_scale.json')
