#!/usr/bin/env python -X utf8
"""GPT-Neo 125M 推理引擎 — 支持 global/local attention"""

import torch
import numpy as np
import tiktoken
import ctypes

lib_t = ctypes.CDLL('csrc/transformer_c.dll')
lib_t.layernorm.argtypes = [ctypes.c_void_p] * 4 + [ctypes.c_int, ctypes.c_float]
lib_t.gelu.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_int]
lib_s = ctypes.CDLL('csrc/softmax_c.dll')
lib_s.softmax_c.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_int]
enc = tiktoken.get_encoding('gpt2')


def load(path='csrc/gpt_neo_125m/pytorch_model.bin'):
    w = torch.load(path, map_location='cpu', weights_only=True)
    dim = w['transformer.wte.weight'].shape[1]  # 768
    heads = 12
    hd = dim // heads  # 64
    layers = 12
    inter = w['transformer.h.0.mlp.c_fc.weight'].shape[0]  # 3072
    # attention_types: [['global', 'local'], 6] means layers 0-5 are one type, 6-11 the other
    # But each pair alternates: 0=global,1=local,2=global,...,5=global,6=local,...,11=local
    # Wait: ['global','local'],6 means 6 pairs, not 6 alternating
    # Actually in GPT-Neo config, it means: first 6 are 'global' type, last 6 are 'local' type? Or alternating?
    # Let me just hardcode from the official config: global=[0,2,4,6,8,10], local=[1,3,5,7,9,11]
    attn_type = ['global' if i % 2 == 0 else 'local' for i in range(layers)]
    return w, dim, heads, hd, layers, inter, attn_type


def make_engine(w, dim, heads, hd, layers, inter, attn_type, window=256):
    emb_w = w['transformer.wte.weight'].numpy().astype(np.float32)
    pos_w = w['transformer.wpe.weight'].numpy().astype(np.float32)
    # attention bias: [1,1,2048,2048]
    bias_key = 'transformer.h.0.attn.attention.bias'
    rm = w[bias_key].numpy().astype(np.float32) if bias_key in w else None
    lfw = w['transformer.ln_f.weight'].numpy().astype(np.float32)
    lfb = w['transformer.ln_f.bias'].numpy().astype(np.float32)

    def gelu_new(x):
        return 0.5 * x * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (x + 0.044715 * x**3)))

    def get_ws(lidx):
        p = f'transformer.h.{lidx}'
        return {k[len(p) + 1 :]: w[k].numpy().astype(np.float32) for k in w if k.startswith(p + '.')}

    def process(ids):
        s = len(ids)
        h = emb_w[ids] + pos_w[:s]
        kvs = [None] * layers
        for li in range(layers):
            ws = get_ws(li)
            q = (h @ ws['attn.attention.q_proj.weight'].T).reshape(s, heads, hd).transpose(1, 0, 2)
            k = (h @ ws['attn.attention.k_proj.weight'].T).reshape(s, heads, hd).transpose(1, 0, 2)
            v = (h @ ws['attn.attention.v_proj.weight'].T).reshape(s, heads, hd).transpose(1, 0, 2)
            out = np.zeros((heads, s, hd), dtype=np.float32)
            for hi in range(heads):
                qh = q[hi]
                kh = k[hi]
                vh = v[hi]
                sc = (qh @ kh.T / np.sqrt(hd)).astype(np.float32)
                # causal mask
                if rm is not None and rm.shape[2] >= s:
                    sc += np.where(rm[0, 0, :s, :s] == 0, -1e9, 0.0).astype(np.float32)
                else:
                    mask = np.triu(np.ones((s, s), dtype=np.float32), k=1) * -1e9
                    sc += mask
                aw = np.zeros((s, s), dtype=np.float32)
                for i in range(s):
                    lib_s.softmax_c(sc[i].ctypes.data, aw[i].ctypes.data, s)
                out[hi] = (aw @ vh).astype(np.float32)
            attn = out.transpose(1, 0, 2).reshape(s, dim)
            h1 = h + (attn @ ws['attn.attention.out_proj.weight'].T + ws.get('attn.attention.out_proj.bias', 0)).astype(
                np.float32
            )
            lw = ws['ln_1.weight']
            lb = ws['ln_1.bias']
            h1l = np.zeros_like(h1)
            for i in range(s):
                lib_t.layernorm(h1[i].ctypes.data, lw.ctypes.data, lb.ctypes.data, h1l[i].ctypes.data, dim, 1e-5)
            w1 = ws['mlp.c_fc.weight']
            b1 = ws['mlp.c_fc.bias']
            w2 = ws['mlp.c_proj.weight']
            b2 = ws['mlp.c_proj.bias']
            ffnh = (h1l @ w1.T + b1).astype(np.float32)
            ffna = gelu_new(ffnh)
            h2 = h1l + (ffna @ w2.T + b2).astype(np.float32)
            l2w = ws['ln_2.weight']
            l2b = ws['ln_2.bias']
            for i in range(s):
                lib_t.layernorm(h2[i].ctypes.data, l2w.ctypes.data, l2b.ctypes.data, h2[i].ctypes.data, dim, 1e-5)
            h = h2
            kvs[li] = (k, v)
        return h[-1:], kvs

    def cached_step(h_new, li, past_kv):
        ws = get_ws(li)
        q = (h_new @ ws['attn.attention.q_proj.weight'].T).reshape(1, heads, hd).transpose(1, 0, 2)
        k = (h_new @ ws['attn.attention.k_proj.weight'].T).reshape(1, heads, hd).transpose(1, 0, 2)
        v = (h_new @ ws['attn.attention.v_proj.weight'].T).reshape(1, heads, hd).transpose(1, 0, 2)
        if past_kv is not None:
            pk, pv = past_kv
            k_full = np.concatenate([pk, k], axis=1)
            v_full = np.concatenate([pv, v], axis=1)
        else:
            k_full = k
            v_full = v
        tl = k_full.shape[1]
        out = np.zeros((heads, 1, hd), dtype=np.float32)
        is_local = attn_type[li] == 'local'
        for hi in range(heads):
            qh = q[hi]
            kh = k_full[hi]
            vh = v_full[hi]
            sc = (qh @ kh.T / np.sqrt(hd)).astype(np.float32)
            if is_local and tl > window:
                # local attention: mask outside window
                for j in range(tl):
                    if tl - 1 - j > window:
                        sc[0, j] = -1e9
            aw = np.zeros((1, tl), dtype=np.float32)
            lib_s.softmax_c(sc[0].ctypes.data, aw[0].ctypes.data, tl)
            out[hi] = (aw @ vh).astype(np.float32)
        attn = out.transpose(1, 0, 2).reshape(1, dim)
        h1 = h_new + (attn @ ws['attn.attention.out_proj.weight'].T + ws.get('attn.attention.out_proj.bias', 0)).astype(
            np.float32
        )
        lw = ws['ln_1.weight']
        lb = ws['ln_1.bias']
        h1l = np.zeros_like(h1)
        lib_t.layernorm(h1[0].ctypes.data, lw.ctypes.data, lb.ctypes.data, h1l[0].ctypes.data, dim, 1e-5)
        w1 = ws['mlp.c_fc.weight']
        b1 = ws['mlp.c_fc.bias']
        w2 = ws['mlp.c_proj.weight']
        b2 = ws['mlp.c_proj.bias']
        ffnh = (h1l @ w1.T + b1).astype(np.float32)
        ffna = gelu_new(ffnh)
        h2 = h1l + (ffna @ w2.T + b2).astype(np.float32)
        l2w = ws['ln_2.weight']
        l2b = ws['ln_2.bias']
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

    return process, forward_step


if __name__ == '__main__':
    import collections
    import time

    print('Loading GPT-Neo 125M...')
    w, dim, heads, hd, layers, inter, attn_type = load()
    process, fwd = make_engine(w, dim, heads, hd, layers, inter, attn_type)
    print(f'  dim={dim} heads={heads} hd={hd} layers={layers} inter={inter}')
    print(f'  attention: {attn_type}')

    # Quick test
    prompt = 'Once upon a time'
    ids = enc.encode(prompt)
    recent = collections.deque(maxlen=8)
    print(f'\nPrompt: {prompt}')
    t0 = time.perf_counter()
    _, kvs = process(ids)
    for step in range(30):
        logits, kvs = fwd(ids, kvs)
        lt = logits.copy()
        lt /= 0.8
        lt -= lt.max()
        probs = np.exp(lt)
        probs /= probs.sum()
        idx = np.argsort(-probs)[:50]
        tp = probs[idx]
        tp /= tp.sum()
        tok = int(idx[np.random.choice(50, p=tp)])
        ids.append(tok)
        recent.append(tok)
    dt = time.perf_counter() - t0
    print(enc.decode(ids))
    print(f'\n{30} tokens in {dt:.1f}s ({dt / 30 * 1000:.0f}ms/token)')
