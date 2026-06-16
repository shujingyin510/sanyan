#!/usr/bin/env python -X utf8
"""GPT-2 124M 1000 prompt 全量基准"""

import torch
import numpy as np
import tiktoken
import ctypes
import collections
import time
import json
import os
import random

lib_t = ctypes.CDLL('csrc/transformer_c.dll')
lib_t.layernorm.argtypes = [ctypes.c_void_p] * 4 + [ctypes.c_int, ctypes.c_float]
enc = tiktoken.get_encoding('gpt2')


def gelu_new(x):
    return (0.5 * x * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (x + 0.044715 * x**3)))).astype(np.float32)


w_pt = torch.load('csrc/gpt2/pytorch_model.bin', map_location='cpu', weights_only=True)
dim = w_pt['wte.weight'].shape[1]
heads = 12
hd = dim // heads
layers = 12
inter = w_pt['h.0.mlp.c_fc.weight'].shape[1]
emb_w = w_pt['wte.weight'].numpy().astype(np.float32)
pos_w = w_pt['wpe.weight'].numpy().astype(np.float32)
lfw = w_pt['ln_f.weight'].numpy().astype(np.float32)
lfb = w_pt['ln_f.bias'].numpy().astype(np.float32)
LWS = []
for li in range(layers):
    pref = f'h.{li}.'
    LWS.append({k[len(pref) :]: w_pt[k].numpy().astype(np.float32) for k in w_pt if k.startswith(pref)})


def c_ln(x, g, b, eps=1e-5):
    y = np.zeros(dim, dtype=np.float32)
    lib_t.layernorm(x.ctypes.data, g.ctypes.data, b.ctypes.data, y.ctypes.data, dim, eps)
    return y


def prefill(ids):
    s = len(ids)
    h = (emb_w[ids] + pos_w[:s]).astype(np.float32)
    kv = []
    for ws in LWS:
        hn = np.array([c_ln(h[i], ws['ln_1.weight'], ws['ln_1.bias']) for i in range(s)])
        qkv = (hn @ ws['attn.c_attn.weight'] + ws['attn.c_attn.bias']).astype(np.float32)
        q = qkv[:, :dim].reshape(s, heads, hd).transpose(1, 0, 2)
        k = qkv[:, dim : 2 * dim].reshape(s, heads, hd).transpose(1, 0, 2)
        v = qkv[:, 2 * dim :].reshape(s, heads, hd).transpose(1, 0, 2)
        kv.append((k, v))
        mask = ws['attn.bias'][0, 0, :s, :s]
        out = np.zeros((heads, s, hd), dtype=np.float32)
        for hi in range(heads):
            sc = (q[hi] @ k[hi].T / np.sqrt(hd)).astype(np.float32)
            sc += np.where(mask == 0, -1e9, 0.0).astype(np.float32)
            sm = sc.max(1, keepdims=True)
            es = np.exp(sc - sm).astype(np.float32)
            out[hi] = ((es / es.sum(1, keepdims=True)) @ v[hi]).astype(np.float32)
        attn = out.transpose(1, 0, 2).reshape(s, dim)
        h = (h + attn @ ws['attn.c_proj.weight'] + ws['attn.c_proj.bias']).astype(np.float32)
        hn2 = np.array([c_ln(h[i], ws['ln_2.weight'], ws['ln_2.bias']) for i in range(s)])
        mlp_h = (hn2 @ ws['mlp.c_fc.weight'] + ws['mlp.c_fc.bias']).astype(np.float32)
        h = (h + gelu_new(mlp_h) @ ws['mlp.c_proj.weight'] + ws['mlp.c_proj.bias']).astype(np.float32)
    return h[-1:], kv


UR_TH = 0.30


def traject(ids):
    r = ids[-32:] if len(ids) >= 32 else ids
    n = len(r)
    if n < 8:
        return 'OK', 1.0, ''
    ur = len(set(r)) / n
    if ur < UR_TH:
        return 'NEGATE', ur, f'UR={ur:.2f}'
    reasons = []
    for p in range(2, min(9, n // 2 + 1)):
        m = sum(1 for i in range(p, n) if r[i] == r[i - p])
        if m > (n - p) * 0.7:
            reasons.append(f'CYC{p}')
            break
    fs = {
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
    if sum(1 for t in r if t in fs) > n * 0.7:
        reasons.append('FUNC')
    if n >= 16 and len(set(r[n // 2 :]) - set(r[: n // 2])) == 0:
        reasons.append('NONEW')
    reasons.append(f'UR={ur:.2f}')
    if len(reasons) >= 3:
        return 'NEGATE', ur, ';'.join(reasons)
    if len(reasons) >= 2:
        return 'UNCERTAIN', ur, ';'.join(reasons)
    return 'OK', ur, ';'.join(reasons)


def generate(prompt, strategy, max_steps=64):
    ids = enc.encode(prompt)
    recent = collections.deque(maxlen=8)
    unc = 0
    h_last, kv = prefill(ids)

    for _ in range(max_steps):
        hf = c_ln(h_last[0], lfw, lfb)
        logits = (hf @ emb_w.T).astype(np.float32)
        lt = logits.copy()
        for tid in recent:
            lt[tid] /= 1.15
        lt /= 0.8
        lt -= lt.max()
        probs = np.exp(lt).astype(np.float32)
        probs /= probs.sum()

        if strategy == 'ternary':
            g, _, _ = traject(ids)
            if g == 'NEGATE':
                break
            if g == 'UNCERTAIN':
                unc += 1
            else:
                unc = 0
            if unc >= 4:
                break

        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        tok = int(idx[np.random.choice(50, p=tp)])
        ids.append(tok)
        recent.append(tok)

        pos = len(ids) - 1
        h_new = (emb_w[tok : tok + 1] + pos_w[pos : pos + 1]).astype(np.float32)
        for li, ws in enumerate(LWS):
            hn = c_ln(h_new[0], ws['ln_1.weight'], ws['ln_1.bias']).reshape(1, dim)
            qkv = (hn @ ws['attn.c_attn.weight'] + ws['attn.c_attn.bias']).astype(np.float32)
            q = qkv[:, :dim].reshape(1, heads, hd).transpose(1, 0, 2)
            k = qkv[:, dim : 2 * dim].reshape(1, heads, hd).transpose(1, 0, 2)
            v = qkv[:, 2 * dim :].reshape(1, heads, hd).transpose(1, 0, 2)
            pk, pv = kv[li]
            kf = np.concatenate([pk, k], axis=1)
            vf = np.concatenate([pv, v], axis=1)
            kf.shape[1]
            out = np.zeros((heads, 1, hd), dtype=np.float32)
            for hi in range(heads):
                sc = (q[hi] @ kf[hi].T / np.sqrt(hd)).astype(np.float32)
                sm = sc.max()
                es = np.exp(sc - sm).astype(np.float32)
                out[hi] = ((es / es.sum()) @ vf[hi]).astype(np.float32)
            attn = out.transpose(1, 0, 2).reshape(1, dim)
            h1 = (h_new + attn @ ws['attn.c_proj.weight'] + ws['attn.c_proj.bias']).astype(np.float32)
            hn2 = c_ln(h1[0], ws['ln_2.weight'], ws['ln_2.bias']).reshape(1, dim)
            mlp_h = (hn2 @ ws['mlp.c_fc.weight'] + ws['mlp.c_fc.bias']).astype(np.float32)
            h_new = (h1 + gelu_new(mlp_h) @ ws['mlp.c_proj.weight'] + ws['mlp.c_proj.bias']).astype(np.float32)
            kv[li] = (kf, vf)
        h_last = h_new

    return len(ids) - len(enc.encode(prompt))


print('GPT-2 124M — 1000 prompt 基准')
print(f'  dim={dim} heads={heads} layers={layers}')

np.random.seed(42)
random.seed(42)

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
N = 1000
prompts = [f'{templates[i % len(templates)]} {extras[(i // len(templates)) % len(extras)]}' for i in range(N)]

results = []
for strategy, name in [('ternary', '三态门控'), ('eos', 'EOS-only')]:
    lengths = []
    stops = 0
    t0 = time.perf_counter()
    for i, p in enumerate(prompts):
        rl = generate(p, strategy)
        lengths.append(rl)
        if rl < 64:
            stops += 1
        if i % 100 == 99:
            print(f'  {name} {i + 1}/{N}')
    dt = time.perf_counter() - t0
    entry = {
        'model': 'GPT-2 124M',
        'strategy': name,
        'N': N,
        'avg_len': float(np.mean(lengths)),
        'stop_rate': float(stops / N * 100),
        'time': dt,
    }
    results.append(entry)
    print(f'  {name}: avg_len={entry["avg_len"]:.1f} stop={entry["stop_rate"]:.0f}% time={dt:.0f}s')

os.makedirs('benchmarks', exist_ok=True)
with open('benchmarks/ternary_scale_gpt2.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print('\nSaved: benchmarks/ternary_scale_gpt2.json')
for r in results:
    print(f'  {r["strategy"]}: avg_len={r["avg_len"]:.1f} stop={r["stop_rate"]:.0f}% time={r["time"]:.0f}s')
