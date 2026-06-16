#!/usr/bin/env python -X utf8
"""生成质量 + 长文本实验"""

import torch
import numpy as np
import tiktoken
import ctypes
import collections
import random

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


def process(ids):
    s = len(ids)
    h = emb_w[ids] + pos_w[:s]
    kvs = [None] * layers
    for li in range(layers):
        p = f'transformer.h.{li}'
        q = (
            (h @ weights[f'{p}.attn.attention.q_proj.weight'].numpy().astype(np.float32).T)
            .astype(np.float32)
            .reshape(s, heads, hd)
            .transpose(1, 0, 2)
        )
        k = (
            (h @ weights[f'{p}.attn.attention.k_proj.weight'].numpy().astype(np.float32).T)
            .astype(np.float32)
            .reshape(s, heads, hd)
            .transpose(1, 0, 2)
        )
        v = (
            (h @ weights[f'{p}.attn.attention.v_proj.weight'].numpy().astype(np.float32).T)
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
        kvs[li] = (k, v)
    return h[-1:], kvs


def step(h_new, kvs):
    for li in range(layers):
        p = f'transformer.h.{li}'
        pk = kvs[li]
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
        if pk is not None:
            pk_, pv_ = pk
            k_full = np.concatenate([pk_, k], axis=1)
            v_full = np.concatenate([pv_, v], axis=1)
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
        h1 = h_new + (attn @ weights[f'{p}.attn.attention.out_proj.weight'].numpy().astype(np.float32).T).astype(
            np.float32
        )
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
        kvs[li] = (k_full, v_full)
    return h2


def traj(ids):
    r = ids[-32:] if len(ids) >= 32 else ids
    n = len(r)
    if n < 8:
        return 'OK'
    ur = len(set(r)) / n
    reasons = []
    if ur < 0.18:
        reasons.append('REPEAT')
    for p in range(2, min(9, n // 2 + 1)):
        m = sum(1 for i in range(p, n) if r[i] == r[i - p])
        if m > (n - p) * 0.7:
            reasons.append(f'CYCLE{p}')
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
    if len(reasons) >= 2:
        return 'NEGATE'
    if len(reasons) == 1:
        return 'UNCERTAIN'
    return 'OK'


def ternary_sample(logits, recent, ids, unc):
    lt = logits.copy()
    for tid in recent:
        lt[tid] /= 1.15
    lt /= 0.8
    lt -= lt.max()
    probs = np.exp(lt)
    probs /= probs.sum()
    t = traj(ids)
    if t == 'NEGATE':
        return None, 'traj'
    if t == 'UNCERTAIN':
        if unc >= 3:
            return None, 'persist'
        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        return int(idx[np.random.choice(50, p=tp)]), 'maybe'
    if probs.max() > 0.9:
        return int(np.argmax(probs)), 'affirm'
    elif probs.max() > 0.3:
        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        return int(idx[np.random.choice(50, p=tp)]), 'maybe'
    return None, 'conf'


def plain_sample(logits, recent):
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


# 实验1: 质量评估
print('=' * 60)
print('  实验1: 生成质量对比 (20 prompts x 2 modes)')
print('=' * 60)
random.seed(42)
np.random.seed(42)
quality = {'ternary': {'complete': 0, 'total': 0}, 'plain': {'complete': 0, 'total': 0}}
prompts = [
    'Once upon a time there was',
    'The little girl went',
    'A big red dog',
    'I like to go',
    'She opened the door and',
    'He looked up at the',
    'The old man sat',
    'A tiny bird sang',
    'On the farm lived a',
    'The happy cat jumped',
    'She found a small',
    'He built a tall',
    'The sun came out and',
    'A rainbow appeared in',
    'She whispered softly to',
    'He ran quickly to',
    'The magic wand sparkled',
    'A golden key unlocked',
    'Under the old bridge',
    'Behind the big tree',
]
for prompt in prompts:
    for mode, fn in [('ternary', ternary_sample), ('plain', None)]:
        ids = enc.encode(prompt)
        recent = collections.deque(maxlen=8)
        _, kvs = process(ids)
        unc = 0
        for _ in range(64):
            pos = len(ids)
            h_new = emb_w[ids[-1:]] + pos_w[pos : pos + 1]
            h_new = step(h_new, kvs)
            fn2 = h_new.copy()
            lib_t.layernorm(fn2[0].ctypes.data, lfw.ctypes.data, lfb.ctypes.data, fn2[0].ctypes.data, dim, 1e-5)
            logits = (fn2 @ emb_w.T)[0]
            if mode == 'ternary':
                tok, reason = fn(logits, recent, ids, unc)
                if tok is None:
                    break
                if reason in ('maybe', 'traj'):
                    unc += 1
                else:
                    unc = 0
            else:
                tok = plain_sample(logits, recent)
            ids.append(int(tok))
            recent.append(int(tok))
        text = enc.decode(ids)
        gen_len = len(ids) - len(enc.encode(prompt))
        ends_well = text.rstrip().endswith(('.', '!', '?'))
        quality[mode]['total'] += 1
        if ends_well:
            quality[mode]['complete'] += 1
        print(f'  [{mode:7s}] ({gen_len:2d}tk) {text[:80]}...')
        print()

for m in ['ternary', 'plain']:
    q = quality[m]
    print(f'{m}: 完整句号率={q["complete"]}/{q["total"]} ({q["complete"] / q["total"] * 100:.0f}%)')

# 实验2: 长文本
print('\n' + '=' * 60)
print('  实验2: 长文本场景')
print('=' * 60)
long_prompts = [
    'Write a story about a brave knight who',
    'Explain how to make a cake step by step',
    'Describe a beautiful garden with many flowers',
    'Tell me about the history of computers',
    'Write a letter to a friend about your day',
    'Explain what makes a good story',
    'Describe your favorite place in detail',
    'Tell a story about a magical adventure',
]
for prompt in long_prompts:
    ids = enc.encode(prompt)
    recent = collections.deque(maxlen=8)
    _, kvs = process(ids)
    unc = 0
    for _ in range(64):
        pos = len(ids)
        h_new = emb_w[ids[-1:]] + pos_w[pos : pos + 1]
        h_new = step(h_new, kvs)
        fn = h_new.copy()
        lib_t.layernorm(fn[0].ctypes.data, lfw.ctypes.data, lfb.ctypes.data, fn[0].ctypes.data, dim, 1e-5)
        logits = (fn @ emb_w.T)[0]
        tok, reason = ternary_sample(logits, recent, ids, unc)
        if tok is None:
            break
        if reason in ('maybe', 'traj'):
            unc += 1
        else:
            unc = 0
        ids.append(int(tok))
        recent.append(int(tok))
    gl = len(ids) - len(enc.encode(prompt))
    text = enc.decode(ids)
    ends_well = text.rstrip().endswith(('.', '!', '?'))
    print(f'  ({gl:2d}tk, ends_well={ends_well}) {text[:120]}')
    print()
