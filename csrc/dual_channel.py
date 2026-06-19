#!/usr/bin/env python -X utf8
"""双通道检测器: UR (词法) + SBERT (语义) — 检测语义循环"""

import torch
import numpy as np
import tiktoken
import ctypes
import collections
import json
import os

print('Loading models...')
# SBERT for semantic similarity
from sentence_transformers import SentenceTransformer  # noqa: E402

sbert = SentenceTransformer('all-MiniLM-L6-v2')  # 80MB, fast

# GPT-2 engine
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


def logits_from(h):
    hf = c_ln(h[0], lfw, lfb)
    return (hf @ emb_w.T).astype(np.float32)


# ── 双通道检测器 ──
class DualDetector:
    def __init__(self):
        self.ur_history = []
        self.sim_history = []
        self.segments = []  # (token_pos, text_segment, embedding)

    def check(self, ids, enc, sbert, window=32):
        # Channel 1: UR
        r = ids[-window:] if len(ids) >= window else ids
        ur = len(set(r)) / max(len(r), 1) if len(r) >= 8 else 1.0
        self.ur_history.append(ur)

        # Channel 2: Semantic similarity (every 8 tokens)
        result = 'OK'
        sim = 0.0
        if len(ids) >= 24 and len(ids) % 8 == 0:
            recent = enc.decode(ids[-20:])
            past = enc.decode(ids[-40:-20]) if len(ids) >= 40 else ''
            if past and recent:
                emb_recent = sbert.encode([recent])[0]
                emb_past = sbert.encode([past])[0]
                sim = float(
                    np.dot(emb_recent, emb_past) / (np.linalg.norm(emb_recent) * np.linalg.norm(emb_past) + 1e-8)
                )
                self.sim_history.append(sim)

                if ur > 0.30 and sim > 0.85:
                    result = 'SEMANTIC_LOOP'  # 词不同但意重复
                elif ur < 0.30:
                    result = 'LEXICAL_LOOP'
                elif sim > 0.90 and ur < 0.50:
                    result = 'DEEP_LOOP'  # 强语义+中词法 = 严重循环
        return ur, sim, result


# ── 测试 ──
np.random.seed(42)
prompts = [
    'Once upon a time there was a little girl who',
    'The old man walked slowly through the forest and',
    'She looked up at the stars and wondered about',
    'In the distant mountains there lived a wise',
    'The river flowed gently past the village where',
]

detector = DualDetector()

print('双通道检测: UR (词法) + SBERT (语义)')
print('=' * 55)

for pi, prompt in enumerate(prompts):
    ids = enc.encode(prompt)
    recent = collections.deque(maxlen=8)
    h_last, kv = prefill(ids)
    events = []

    for step in range(50):
        lt = logits_from(h_last).copy()
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

        ur, sim, status = detector.check(ids, enc, sbert)
        if status != 'OK':
            events.append((step, status, ur, sim))

    text = enc.decode(ids)
    final_ur = detector.ur_history[-1] if detector.ur_history else 1.0
    avg_sim = np.mean(detector.sim_history) if detector.sim_history else 0

    print(f'\n{prompt}')
    print(f'  Final UR: {final_ur:.3f} | Avg semantic sim: {avg_sim:.3f}')
    if events:
        for step, status, ur, sim in events:
            print(f'  t={step}: [{status}] UR={ur:.2f} sim={sim:.2f}')
    print(f'  Output: {text[:150]}')

# ── 统计 ──
print(f'\n{"=" * 55}')
print(f'Channel 1 (UR): detected {sum(1 for u in detector.ur_history if u < 0.30)} lexical loops')
print(f'Channel 2 (SBERT): detected {sum(1 for s in detector.sim_history if s > 0.85)} semantic loops')
print(
    f'Combined: {len([1 for u, s in zip(detector.ur_history[-len(detector.sim_history) :], detector.sim_history) if u > 0.30 and s > 0.85])} semantic-only loops (UR masked)'
)

os.makedirs('benchmarks', exist_ok=True)
with open('benchmarks/dual_channel.json', 'w') as f:
    json.dump(
        {
            'ur_history': [float(x) for x in detector.ur_history],
            'sim_history': [float(x) for x in detector.sim_history],
        },
        f,
        indent=2,
    )
print('Saved: benchmarks/dual_channel.json')
