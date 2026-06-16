#!/usr/bin/env python -X utf8
"""GPT-2 124M 推理引擎（Conv1D + pre-norm）"""

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


def load(path='csrc/gpt2/pytorch_model.bin'):
    w = torch.load(path, map_location='cpu', weights_only=True)
    dim = w['wte.weight'].shape[1]  # 768
    heads = 12
    hd = dim // heads  # 64
    layers = 12
    inter = w['h.0.mlp.c_fc.weight'].shape[1]  # 3072
    return w, dim, heads, hd, layers, inter


def make_engine(w, dim, heads, hd, layers, inter):
    emb_w = w['wte.weight'].numpy().astype(np.float32)  # [50257, 768]
    pos_w = w['wpe.weight'].numpy().astype(np.float32)  # [1024, 768]
    lfw = w['ln_f.weight'].numpy().astype(np.float32)
    lfb = w['ln_f.bias'].numpy().astype(np.float32)

    def gelu_new(x):
        return 0.5 * x * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (x + 0.044715 * x**3)))

    def get_ws(lidx):
        p = f'h.{lidx}'
        return {k[len(p) + 1 :]: w[k].numpy().astype(np.float32) for k in w if k.startswith(p + '.')}

    # GPT-2 uses Conv1D: x @ weight + bias (NO transpose)
    def conv1d(x, weight, bias):
        return x @ weight + bias

    def process(ids):
        s = len(ids)
        h = emb_w[ids] + pos_w[:s]
        for li in range(layers):
            ws = get_ws(li)
            # Pre-norm → attention
            ln1_w = ws['ln_1.weight']
            ln1_b = ws['ln_1.bias']
            h_norm = np.zeros_like(h)
            for i in range(s):
                lib_t.layernorm(
                    h[i].ctypes.data, ln1_w.ctypes.data, ln1_b.ctypes.data, h_norm[i].ctypes.data, dim, 1e-5
                )
            # QKV projection (Conv1D: no transpose)
            qkv = conv1d(h_norm, ws['attn.c_attn.weight'], ws['attn.c_attn.bias'])  # [s, 2304]
            q = qkv[:, :dim].reshape(s, heads, hd).transpose(1, 0, 2)  # [heads, s, hd]
            k = qkv[:, dim : 2 * dim].reshape(s, heads, hd).transpose(1, 0, 2)
            v = qkv[:, 2 * dim :].reshape(s, heads, hd).transpose(1, 0, 2)
            attn_bias = ws['attn.bias']  # [1, 1, 1024, 1024]
            out = np.zeros((heads, s, hd), dtype=np.float32)
            for hi in range(heads):
                qh = q[hi]
                kh = k[hi]
                vh = v[hi]
                sc = (qh @ kh.T / np.sqrt(hd)).astype(np.float32)
                mask = attn_bias[0, 0, :s, :s]
                sc += np.where(mask == 0, -1e9, 0.0).astype(np.float32)
                aw = np.zeros((s, s), dtype=np.float32)
                for i in range(s):
                    lib_s.softmax_c(sc[i].ctypes.data, aw[i].ctypes.data, s)
                out[hi] = (aw @ vh).astype(np.float32)
            attn_out = out.transpose(1, 0, 2).reshape(s, dim)
            attn_proj = conv1d(attn_out, ws['attn.c_proj.weight'], ws['attn.c_proj.bias'])
            h = h + attn_proj
            # Pre-norm → MLP
            ln2_w = ws['ln_2.weight']
            ln2_b = ws['ln_2.bias']
            h_norm2 = np.zeros_like(h)
            for i in range(s):
                lib_t.layernorm(
                    h[i].ctypes.data, ln2_w.ctypes.data, ln2_b.ctypes.data, h_norm2[i].ctypes.data, dim, 1e-5
                )
            mlp_hidden = conv1d(h_norm2, ws['mlp.c_fc.weight'], ws['mlp.c_fc.bias'])
        mlp_act = gelu_new(mlp_hidden).astype(np.float32)
        mlp_out = conv1d(mlp_act, ws['mlp.c_proj.weight'], ws['mlp.c_proj.bias']).astype(np.float32)
        h = (h + mlp_out).astype(np.float32)
        # Final LN
        h_final = np.zeros_like(h[-1:])
        lib_t.layernorm(h[-1].ctypes.data, lfw.ctypes.data, lfb.ctypes.data, h_final[0].ctypes.data, dim, 1e-5)
        return h[-1:], None  # no KV cache for now

    def forward(ids):
        s = len(ids)
        h = emb_w[ids] + pos_w[:s]
        for li in range(layers):
            ws = get_ws(li)
            ln1_w = ws['ln_1.weight']
            ln1_b = ws['ln_1.bias']
            h_norm = np.zeros_like(h)
            for i in range(s):
                lib_t.layernorm(
                    h[i].ctypes.data, ln1_w.ctypes.data, ln1_b.ctypes.data, h_norm[i].ctypes.data, dim, 1e-5
                )
            qkv = conv1d(h_norm, ws['attn.c_attn.weight'], ws['attn.c_attn.bias'])
            q = qkv[:, :dim].reshape(s, heads, hd).transpose(1, 0, 2)
            k = qkv[:, dim : 2 * dim].reshape(s, heads, hd).transpose(1, 0, 2)
            v = qkv[:, 2 * dim :].reshape(s, heads, hd).transpose(1, 0, 2)
            attn_bias = ws['attn.bias']
            out = np.zeros((heads, s, hd), dtype=np.float32)
            for hi in range(heads):
                sc = (q[hi] @ k[hi].T / np.sqrt(hd)).astype(np.float32)
                mask = attn_bias[0, 0, :s, :s]
                sc += np.where(mask == 0, -1e9, 0.0).astype(np.float32)
                aw = np.zeros((s, s), dtype=np.float32)
                for i in range(s):
                    lib_s.softmax_c(sc[i].ctypes.data, aw[i].ctypes.data, s)
                out[hi] = (aw @ v[hi]).astype(np.float32)
            attn_out = out.transpose(1, 0, 2).reshape(s, dim)
            h = h + conv1d(attn_out, ws['attn.c_proj.weight'], ws['attn.c_proj.bias'])
            ln2_w = ws['ln_2.weight']
            ln2_b = ws['ln_2.bias']
            h_norm2 = np.zeros_like(h)
            for i in range(s):
                lib_t.layernorm(
                    h[i].ctypes.data, ln2_w.ctypes.data, ln2_b.ctypes.data, h_norm2[i].ctypes.data, dim, 1e-5
                )
            mlp_h = conv1d(h_norm2, ws['mlp.c_fc.weight'], ws['mlp.c_fc.bias'])
            h = h + conv1d(gelu_new(mlp_h).astype(np.float32), ws['mlp.c_proj.weight'], ws['mlp.c_proj.bias']).astype(
                np.float32
            )
        fn = h[-1:].copy()
        lib_t.layernorm(fn[0].ctypes.data, lfw.ctypes.data, lfb.ctypes.data, fn[0].ctypes.data, dim, 1e-5)
        return (fn @ emb_w.T)[0]

    return forward


if __name__ == '__main__':
    print('Loading GPT-2 124M...')
    w, dim, heads, hd, layers, inter = load()
    forward = make_engine(w, dim, heads, hd, layers, inter)
    print(f'  dim={dim} heads={heads} layers={layers} inter={inter}')

    for prompt in ['Once upon a time', 'The quick brown fox jumps over', 'I believe the future of AI is']:
        ids = enc.encode(prompt)
        print(f'\nPrompt: {prompt}')
        np.random.seed(42)
        for step in range(40):
            logits = forward(ids)
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
        print(enc.decode(ids))
