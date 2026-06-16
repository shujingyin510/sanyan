#!/usr/bin/env python -X utf8
"""三言 三态门控推理 — 置信度 + 轨迹质量 决策采样策略"""

import torch
import numpy as np
import tiktoken
import ctypes
import collections

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


def ternary_sample(logits, recent):
    lt = logits.copy()
    for tid in recent:
        lt[tid] /= 1.15
    lt /= 0.8
    lt -= lt.max()
    probs = np.exp(lt)
    probs /= probs.sum()
    top_prob = probs.max()

    if top_prob > 0.9:
        idx = int(np.argmax(probs))
        return idx, 'AFFIRM', top_prob
    elif top_prob > 0.3:
        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        return int(idx[np.random.choice(50, p=tp)]), 'MAYBE', top_prob
    else:
        return None, 'NEGATE', top_prob


def trajectory_check(ids, window=32):
    """轨迹质量检测 — 纯符号统计, 无 embedding"""
    recent = ids[-window:] if len(ids) >= window else ids
    n = len(recent)
    if n < 8:
        return 'OK', 0.0, ''

    unique = set(recent)
    unique_ratio = len(unique) / n
    reasons = []

    # 1. 严重重复: 独特词太少
    if unique_ratio < 0.15:
        return 'NEGATE', unique_ratio, '重复率过高'

    # 2. 周期检测: 找最短重复周期
    for period in range(2, min(9, n // 2 + 1)):
        matches = 0
        for i in range(period, n):
            if recent[i] == recent[i - period]:
                matches += 1
        if matches > (n - period) * 0.7:
            reasons.append(f'周期{period}')
            break

    # 3. 词类单一: 函数词/代词占比高
    func_set = {  # 常见功能词 + 代词 (GPT-2 token ids)
        345,
        346,
        347,
        348,
        349,
        350,  # my, me, our, your, his, her
        351,
        352,
        353,
        354,
        355,
        356,  # its, their, them, us, him
        286,
        287,
        257,
        261,
        262,
        263,  # the, a, to, of, in, is
        264,
        265,
        266,
        267,
        268,  # was, are, be, been, has
        319,
        320,
        321,
        322,  # I, you, he, she
        616,
        617,
        660,  # his, him, us (duplicates)
    }
    func_count = sum(1 for t in recent if t in func_set)
    if func_count > n * 0.7:
        reasons.append('功能词密集')

    # 4. 新词停滞: 最近 8 个无新词
    if n >= 16:
        first_half = set(recent[: n // 2])
        second_half = set(recent[n // 2 :])
        new_in_second = second_half - first_half
        if len(new_in_second) == 0:
            reasons.append('无新词')

    # 综合判断
    # 总是返回可解释信息
    info_parts = []
    if len(reasons) > 0:
        info_parts = reasons.copy()
    info_parts.append(f'ur={unique_ratio:.2f}')
    info = ','.join(info_parts)
    if not info:
        info = f'ur={unique_ratio:.2f}'

    if len(reasons) >= 2:
        return 'NEGATE', unique_ratio, info
    elif len(reasons) == 1:
        return 'UNCERTAIN', unique_ratio, info
    return 'OK', unique_ratio, info


def ternary_sample_v2(logits, recent, ids):
    """v2: 局部置信度 + 轨迹质量"""
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
        return None, f'NEGATE({reason})', top_prob
    if traj == 'UNCERTAIN':
        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        return int(idx[np.random.choice(50, p=tp)]), f'MAYBE({reason})', top_prob

    if top_prob > 0.9:
        return int(np.argmax(probs)), 'AFFIRM', top_prob
    elif top_prob > 0.3:
        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        return int(idx[np.random.choice(50, p=tp)]), 'MAYBE', top_prob
    return None, 'NEGATE', top_prob


np.random.seed(42)
texts = [
    'Once upon a time there was a little girl',
    'The sun was shining and the birds were singing',
    'I went to the store to buy some',
]
for text in texts:
    ids = enc.encode(text)
    recent = collections.deque(maxlen=8)
    h_last, kvs = process_prompt(ids)
    result = [text]
    steps = 0
    max_steps = 64
    uncertain_count = 0  # 持续不确定计数
    while steps < max_steps:
        pos_idx = len(ids)
        h_new = emb_w[ids[-1:]] + pos_w[pos_idx : pos_idx + 1]
        for li in range(layers):
            h_new, kvs[li] = layer_cached(h_new, li, kvs[li])
        fn = h_new.copy()
        lib_t.layernorm(fn[0].ctypes.data, lfw.ctypes.data, lfb.ctypes.data, fn[0].ctypes.data, dim, 1e-5)
        logits = (fn @ emb_w.T)[0]
        tok, state_label, conf = ternary_sample_v2(logits, recent, ids)
        if tok is None:
            w = min(len(ids), 32)
            rw = ids[-w:]
            ur = len(set(rw)) / max(w, 1)
            _, _, reason = trajectory_check(ids)
            result.append(f' [NEGATE: conf={conf:.2f}, {reason}, unique_ratio={ur:.2f}, steps={steps}]')
            break
        ids.append(tok)
        recent.append(tok)
        result.append(enc.decode([tok]))
        if 'UNCERTAIN' in state_label or 'MAYBE' in state_label:
            uncertain_count += 1
        else:
            uncertain_count = 0
        if uncertain_count >= 4:
            w = min(len(ids), 32)
            rw = ids[-w:]
            ur = len(set(rw)) / max(w, 1)
            _, _, reason = trajectory_check(ids)
            result.append(f' [NEGATE: 不确定{uncertain_count}步, {reason}, unique_ratio={ur:.2f}]')
            break
        steps += 1
    print(''.join(result))
    print()
