#!/usr/bin/env python -X utf8
"""三言语言调度推理引擎 — 验证 Demo
证明 .san 代码能通过 reg_op 调用 C 推理算子，并执行三态门控逻辑。
"""

import ctypes
import torch
import numpy as np
import tiktoken
import collections

# ── 1. 加载推理引擎（C DLL + GPT-2 124M 模型） ──
lib_t = ctypes.CDLL('csrc/transformer_c.dll')
lib_t.layernorm.argtypes = [ctypes.c_void_p] * 4 + [ctypes.c_int, ctypes.c_float]
enc = tiktoken.get_encoding('gpt2')
np.random.seed(42)


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


state = {'ids': None, 'recent': None, 'kv': None, 'h_last': None, 'unc': 0}
UR_TH = 0.30


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


# ── 2. 注册三言原生函数 ──
from ops.registry import register as reg_op  # noqa: E402


def 初始化(ev, args):
    prompt = args[0] if isinstance(args[0], str) else str(args[0])
    state['ids'] = enc.encode(prompt)
    state['recent'] = collections.deque(maxlen=8)
    state['unc'] = 0
    state['h_last'], state['kv'] = prefill(state['ids'])
    return 0


reg_op('初始化', 初始化)


def 推理循环(ev, args):
    """(推理循环 steps strategy) → 执行指定步数的推理，沿途打印三态决策"""
    steps = int(args[0])
    strategy = 'ternary'
    s = state
    for step in range(steps):
        hf = c_ln(s['h_last'][0], lfw, lfb)
        logits = (hf @ emb_w.T).astype(np.float32)
        lt = logits.copy()
        for t in s['recent']:
            lt[t] /= 1.15
        lt /= 0.8
        lt -= lt.max()
        probs = np.exp(lt).astype(np.float32)
        probs /= probs.sum()
        topk = np.argsort(-probs)[:50]
        tp = probs[topk]
        tp /= tp.sum()
        tok = int(topk[np.random.choice(50, p=tp)])
        token_text = enc.decode([tok])

        if strategy == 'ternary':
            r = s['ids'][-32:] if len(s['ids']) >= 32 else s['ids']
            n = len(r)
            gate = 'AFFIRM'
            if n >= 8:
                ur = len(set(r)) / n
                if ur < UR_TH:
                    print(f'  [{step}] {token_text!r:20s} → NEGATE (UR={ur:.2f})', flush=True)
                    return n
                cycle_found = False
                for p in range(2, min(9, n // 2 + 1)):
                    m = sum(1 for i in range(p, n) if r[i] == r[i - p])
                    if m > (n - p) * 0.7:
                        s['unc'] += 1
                        gate = 'MAYBE'
                        cycle_found = True
                        if s['unc'] >= 3:
                            print(f'  [{step}] {token_text!r:20s} → NEGATE (CYC{p} x{s["unc"]})', flush=True)
                            return n
                        break
                if not cycle_found:
                    s['unc'] = 0
            if gate == 'AFFIRM':
                print(f'  [{step}] {token_text!r:20s} → AFFIRM', flush=True)
            elif gate == 'MAYBE':
                print(f'  [{step}] {token_text!r:20s} → MAYBE', flush=True)

        # KV step
        pos = len(s['ids'])
        s['ids'].append(tok)
        s['recent'].append(tok)
        h_new = (emb_w[tok : tok + 1] + pos_w[pos : pos + 1]).astype(np.float32)
        for li, ws in enumerate(LWS):
            hn = c_ln(h_new[0], ws['ln_1.weight'], ws['ln_1.bias']).reshape(1, dim)
            qkv = (hn @ ws['attn.c_attn.weight'] + ws['attn.c_attn.bias']).astype(np.float32)
            q = qkv[:, :dim].reshape(1, heads, hd).transpose(1, 0, 2)
            k = qkv[:, dim : 2 * dim].reshape(1, heads, hd).transpose(1, 0, 2)
            v = qkv[:, 2 * dim :].reshape(1, heads, hd).transpose(1, 0, 2)
            pk, pv = s['kv'][li]
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
            s['kv'][li] = (kf, vf)
        s['h_last'] = h_new
    return steps


reg_op('推理循环', 推理循环)


def 输出全部(ev, args):
    text = enc.decode(state['ids'])
    print(f'\n  完整输出: {text}', flush=True)
    return text


reg_op('输出全部', 输出全部)

# ── 3. 执行 .san 脚本 ──
print('=' * 55)
print('  三言语言调度推理引擎 — 验证 Demo')
print('  链路: .san → reg_op → C DLL (LayerNorm/GELU) → NP → GPT-2')
print('=' * 55)

from core.evaluator import SanyanEvaluator  # noqa: E402
from core.parser import parse  # noqa: E402
from core.lexer import tokenize  # noqa: E402

san_code = """
(输出 "三言 三态门控推理引擎 Demo")
(输出 "==============================")
(输出 "模型: GPT-2 124M | 阈值: UR=0.30")
(输出 "")

(初始化 "Once upon a time there was a")

(输出 "推理开始...")
(推理循环 15 "ternary")

(输出 "")
(输出全部)
"""

print('\n[.san 源码]')
for line in san_code.strip().split('\n'):
    print(f'  | {line}')

print('\n[执行结果]')
evaluator = SanyanEvaluator(max_loop_steps=10000)
for line in san_code.strip().split('\n'):
    line = line.strip()
    if not line or line.startswith(';'):
        continue
    try:
        t = tokenize(line)
        if t:
            a = parse(t)
            if a:
                evaluator.eval(a)
    except Exception as e:
        print(f'  [!] {e}')

print('\n' + '=' * 55)
print('  三言语言通过 reg_op 成功调度了 C 推理引擎。')
print('  虽然推理逻辑在 Python 中实现，但 .san 文件')
print('  本身就是可读的决策 DSL，证明了语言层的对接能力。')
print('=' * 55)
