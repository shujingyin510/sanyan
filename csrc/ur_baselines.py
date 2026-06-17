#!/usr/bin/env python -X utf8
"""UR曲线 + beam/nucleus采样对比"""

import torch
import numpy as np
import tiktoken
import ctypes
import collections
import json
import os

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


def step_kv(tok, pos, kv, h_last):
    h_new = (emb_w[tok : tok + 1] + pos_w[pos : pos + 1]).astype(np.float32)
    for li, ws in enumerate(LWS):
        hn = c_ln(h_new[0], ws['ln_1.weight'], ws['ln_1.bias']).reshape(1, dim)
        qkv2 = (hn @ ws['attn.c_attn.weight'] + ws['attn.c_attn.bias']).astype(np.float32)
        q = qkv2[:, :dim].reshape(1, heads, hd).transpose(1, 0, 2)
        k = qkv2[:, dim : 2 * dim].reshape(1, heads, hd).transpose(1, 0, 2)
        v = qkv2[:, 2 * dim :].reshape(1, heads, hd).transpose(1, 0, 2)
        pk, pv = kv[li]
        kf = np.concatenate([pk, k], axis=1)
        vf = np.concatenate([pv, v], axis=1)
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
    return h_new


def logits(h):
    hf = c_ln(h[0], lfw, lfb)
    return (hf @ emb_w.T).astype(np.float32)


np.random.seed(42)

# ── Experiment A: UR curves ──
print('=' * 55)
print('实验 A: UR 随 token 位置的变化曲线')
print('=' * 55)

prompts = ['Once upon a time', 'The little boy went to the', 'A big dog']
ur_curves = {}

for pi, prompt in enumerate(prompts):
    ids = enc.encode(prompt)
    recent = collections.deque(maxlen=8)
    h_last, kv = prefill(ids)
    ur_history = []

    for step in range(50):
        lt = logits(h_last).copy()
        for t in recent:
            lt[t] /= 1.15
        lt /= 0.8
        lt -= lt.max()
        probs = np.exp(lt).astype(np.float32)
        probs /= probs.sum()
        topk = np.argsort(-probs)[:50]
        tp = probs[topk]
        tp /= tp.sum()
        tok = int(topk[np.random.choice(50, p=tp)])
        ids.append(tok)
        recent.append(tok)

        # UR at every step
        if len(ids) >= 8:
            r = ids[-32:] if len(ids) >= 32 else ids
            ur = len(set(r)) / len(r)
            ur_history.append(ur)

        h_last = step_kv(tok, len(ids) - 1, kv, h_last)

    ur_curves[prompt] = ur_history
    text = enc.decode(ids)
    # Print UR trajectory
    key_points = [(i, ur_history[i]) for i in [0, 4, 9, 14, 19, 24, 29, 34, 39] if i < len(ur_history)]
    pts_str = ' '.join([f't{t + 9}:{ur:.2f}' for t, ur in key_points])
    print(f'  [{prompt[:35]:35s}] {pts_str}')
    print(f'  Output: {text[:100]}')
    print()

# ── Experiment B: decoding strategy comparison ──
print('=' * 55)
print('实验 B: 采样策略对比 (GPT-2 124M, greedy / top-p / beam)')
print('=' * 55)


def generate_with_strategy(prompt, strategy, max_steps=50):
    ids = enc.encode(prompt)
    recent = collections.deque(maxlen=8)
    h_last, kv = prefill(ids)

    for step in range(max_steps):
        lt = logits(h_last).copy()

        if strategy == 'greedy':
            tok = int(np.argmax(lt))
        elif strategy == 'rep_penalty':
            for t in recent:
                lt[t] /= 1.15
            lt /= 0.8
            lt -= lt.max()
            probs = np.exp(lt).astype(np.float32)
            probs /= probs.sum()
            topk = np.argsort(-probs)[:50]
            tp = probs[topk]
            tp /= tp.sum()
            tok = int(topk[np.random.choice(50, p=tp)])
        elif strategy == 'nucleus':
            lt /= 0.8
            lt -= lt.max()
            probs = np.exp(lt).astype(np.float32)
            probs /= probs.sum()
            sorted_idx = np.argsort(-probs)
            cumsum = np.cumsum(probs[sorted_idx])
            cutoff = np.searchsorted(cumsum, 0.9) + 1
            nucleus = sorted_idx[:cutoff]
            np2 = probs[nucleus]
            np2 /= np2.sum()
            tok = int(nucleus[np.random.choice(len(nucleus), p=np2)])
        else:  # default: top-k sampling
            for t in recent:
                lt[t] /= 1.15
            lt /= 0.8
            lt -= lt.max()
            probs = np.exp(lt).astype(np.float32)
            probs /= probs.sum()
            topk = np.argsort(-probs)[:50]
            tp = probs[topk]
            tp /= tp.sum()
            tok = int(topk[np.random.choice(50, p=tp)])

        ids.append(tok)
        recent.append(tok)
        h_last = step_kv(tok, len(ids) - 1, kv, h_last)

    # Check degeneration
    r = ids[-32:] if len(ids) >= 32 else ids
    ur = len(set(r)) / max(len(r), 1)
    return ur, enc.decode(ids)


test_prompts = ['Once upon a time', 'The little', 'A big dog', 'I like to play']
for method in ['greedy', 'rep_penalty', 'nucleus']:
    degen = 0
    ur_total = []
    for p in test_prompts:
        ur, text = generate_with_strategy(p, method)
        ur_total.append(ur)
        if ur < 0.30:
            degen += 1
    print(f'  {method:15s}: degen={degen}/{len(test_prompts)} avg_UR={np.mean(ur_total):.3f}')

# ── Save ──
os.makedirs('benchmarks', exist_ok=True)
with open('benchmarks/ur_curves.json', 'w') as f:
    json.dump(ur_curves, f, indent=2)
print('\nSaved: benchmarks/ur_curves.json')
