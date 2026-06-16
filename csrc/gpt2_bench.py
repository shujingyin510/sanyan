#!/usr/bin/env python -X utf8
"""GPT-2 124M 三态门控基准 — 全量前向（已验证正确）"""

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


def forward(ids):
    s = len(ids)
    h = (emb_w[ids] + pos_w[:s]).astype(np.float32)
    for ws in LWS:
        hn = np.array([c_ln(h[i], ws['ln_1.weight'], ws['ln_1.bias']) for i in range(s)])
        qkv = (hn @ ws['attn.c_attn.weight'] + ws['attn.c_attn.bias']).astype(np.float32)
        q = qkv[:, :dim].reshape(s, heads, hd).transpose(1, 0, 2)
        k = qkv[:, dim : 2 * dim].reshape(s, heads, hd).transpose(1, 0, 2)
        v = qkv[:, 2 * dim :].reshape(s, heads, hd).transpose(1, 0, 2)
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
        mlp = (hn2 @ ws['mlp.c_fc.weight'] + ws['mlp.c_fc.bias']).astype(np.float32)
        h = (h + gelu_new(mlp) @ ws['mlp.c_proj.weight'] + ws['mlp.c_proj.bias']).astype(np.float32)
    hf = c_ln(h[-1], lfw, lfb)
    return (hf @ emb_w.T).astype(np.float32)


UR_TH = 0.30


def traject(ids):
    r = ids[-32:] if len(ids) >= 32 else ids
    n = len(r)
    if n < 8:
        return 'OK', 1.0, ''
    ur = len(set(r)) / n
    reasons = []
    if ur < UR_TH:
        return 'NEGATE', ur, f'UR={ur:.2f}'
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
    for _ in range(max_steps):
        logits = forward(ids)
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
    return len(ids) - len(enc.encode(prompt)), enc.decode(ids), ids


print('GPT-2 124M — 20 prompt (full forward, verified)')
np.random.seed(42)
random.seed(42)
prompts = [
    f'{t} {e}'
    for t in ['Once upon a time', 'The little', 'A big', 'I like to', 'One day a']
    for e in ['girl', 'boy', 'dog', 'cat']
]

pairs = []
for i, p in enumerate(prompts):
    t0 = time.perf_counter()
    len_eos, text_eos, _ = generate(p, 'eos')
    len_ter, text_ter, _ = generate(p, 'ternary')
    dt = time.perf_counter() - t0
    if random.random() < 0.5:
        a, b, al, bl = text_eos, text_ter, 'eos', 'ternary'
    else:
        a, b, al, bl = text_ter, text_eos, 'ternary', 'eos'
    pairs.append({'id': i + 1, 'prompt': p, 'A': a, 'B': b, 'A_label': al, 'B_label': bl})
    print(f'  {i + 1}/20 eos={len_eos}tk ter={len_ter}tk ({dt:.0f}s)')

ae = np.mean([x['A_len'] if x['A_label'] == 'eos' else x['B_len'] for x in pairs])
at = np.mean([x['A_len'] if x['A_label'] == 'ternary' else x['B_len'] for x in pairs])
print(f'\nAvg: EOS={ae:.1f} TER={at:.1f}')

os.makedirs('benchmarks', exist_ok=True)
with open('benchmarks/gpt2_blind_20.json', 'w', encoding='utf-8') as f:
    json.dump(pairs, f, indent=2, ensure_ascii=False)

for pi in [0, 5, 10, 15]:
    p = pairs[pi]
    print(f'\n{p["id"]}. {p["prompt"]}')
    print(f'  A({p["A_label"]}): {p["A"][:200]}')
    print(f'  B({p["B_label"]}): {p["B"][:200]}')
