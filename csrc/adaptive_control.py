#!/usr/bin/env python -X utf8
"""闭环实验: UR动态监控 + 自适应惩罚调度"""
import torch, numpy as np, tiktoken, ctypes, collections, time, json, os

lib_t = ctypes.CDLL("csrc/transformer_c.dll")
lib_t.layernorm.argtypes = [ctypes.c_void_p] * 4 + [ctypes.c_int, ctypes.c_float]
enc = tiktoken.get_encoding("gpt2")

def gelu_new(x):
    return (0.5*x*(1.0+np.tanh(np.sqrt(2.0/np.pi)*(x+0.044715*x**3)))).astype(np.float32)

w_pt = torch.load("csrc/gpt2/pytorch_model.bin", map_location="cpu", weights_only=True)
dim = w_pt["wte.weight"].shape[1]; heads = 12; hd = dim//heads; layers = 12
emb_w = w_pt["wte.weight"].numpy().astype(np.float32)
pos_w = w_pt["wpe.weight"].numpy().astype(np.float32)
lfw = w_pt["ln_f.weight"].numpy().astype(np.float32)
lfb = w_pt["ln_f.bias"].numpy().astype(np.float32)

LWS = []
for li in range(layers):
    pref = f"h.{li}."
    LWS.append({k[len(pref):]: w_pt[k].numpy().astype(np.float32) for k in w_pt if k.startswith(pref)})

def c_ln(x, g, b, eps=1e-5):
    y = np.zeros(dim, dtype=np.float32)
    lib_t.layernorm(x.ctypes.data, g.ctypes.data, b.ctypes.data, y.ctypes.data, dim, eps)
    return y

def prefill(ids):
    s = len(ids); h = (emb_w[ids] + pos_w[:s]).astype(np.float32); kv = []
    for ws in LWS:
        hn = np.array([c_ln(h[i], ws["ln_1.weight"], ws["ln_1.bias"]) for i in range(s)])
        qkv = (hn @ ws["attn.c_attn.weight"] + ws["attn.c_attn.bias"]).astype(np.float32)
        q = qkv[:,:dim].reshape(s,heads,hd).transpose(1,0,2)
        k = qkv[:,dim:2*dim].reshape(s,heads,hd).transpose(1,0,2)
        v = qkv[:,2*dim:].reshape(s,heads,hd).transpose(1,0,2)
        kv.append((k,v))
        mask = ws["attn.bias"][0,0,:s,:s]; out = np.zeros((heads,s,hd), dtype=np.float32)
        for hi in range(heads):
            sc = (q[hi] @ k[hi].T / np.sqrt(hd)).astype(np.float32)
            sc += np.where(mask==0, -1e9, 0.0).astype(np.float32)
            sm = sc.max(1, keepdims=True); es = np.exp(sc-sm).astype(np.float32)
            out[hi] = ((es/es.sum(1,keepdims=True)) @ v[hi]).astype(np.float32)
        attn = out.transpose(1,0,2).reshape(s,dim)
        h = (h + attn @ ws["attn.c_proj.weight"] + ws["attn.c_proj.bias"]).astype(np.float32)
        hn2 = np.array([c_ln(h[i], ws["ln_2.weight"], ws["ln_2.bias"]) for i in range(s)])
        mlp_h = (hn2 @ ws["mlp.c_fc.weight"] + ws["mlp.c_fc.bias"]).astype(np.float32)
        h = (h + gelu_new(mlp_h) @ ws["mlp.c_proj.weight"] + ws["mlp.c_proj.bias"]).astype(np.float32)
    return h[-1:], kv

def step_kv(tok, pos, kv, h_last):
    h_new = (emb_w[tok:tok+1] + pos_w[pos:pos+1]).astype(np.float32)
    for li, ws in enumerate(LWS):
        hn = c_ln(h_new[0], ws["ln_1.weight"], ws["ln_1.bias"]).reshape(1,dim)
        qkv2 = (hn @ ws["attn.c_attn.weight"] + ws["attn.c_attn.bias"]).astype(np.float32)
        q = qkv2[:,:dim].reshape(1,heads,hd).transpose(1,0,2)
        k = qkv2[:,dim:2*dim].reshape(1,heads,hd).transpose(1,0,2)
        v = qkv2[:,2*dim:].reshape(1,heads,hd).transpose(1,0,2)
        pk,pv = kv[li]; kf = np.concatenate([pk,k], axis=1); vf = np.concatenate([pv,v], axis=1)
        out = np.zeros((heads,1,hd), dtype=np.float32)
        for hi in range(heads):
            sc = (q[hi] @ kf[hi].T / np.sqrt(hd)).astype(np.float32)
            sm = sc.max(); es = np.exp(sc-sm).astype(np.float32)
            out[hi] = ((es/es.sum()) @ vf[hi]).astype(np.float32)
        attn = out.transpose(1,0,2).reshape(1,dim)
        h1 = (h_new + attn @ ws["attn.c_proj.weight"] + ws["attn.c_proj.bias"]).astype(np.float32)
        hn2 = c_ln(h1[0], ws["ln_2.weight"], ws["ln_2.bias"]).reshape(1,dim)
        mlp_h = (hn2 @ ws["mlp.c_fc.weight"] + ws["mlp.c_fc.bias"]).astype(np.float32)
        h_new = (h1 + gelu_new(mlp_h) @ ws["mlp.c_proj.weight"] + ws["mlp.c_proj.bias"]).astype(np.float32)
        kv[li] = (kf, vf)
    return h_new

def logits_from(h):
    hf = c_ln(h[0], lfw, lfb)
    return (hf @ emb_w.T).astype(np.float32)

def ur_at(ids, window=32):
    r = ids[-window:] if len(ids) >= window else ids
    return len(set(r)) / max(len(r), 1)

# ── 生成策略 ──
prompts = [f"{t} {e}" for t in ["Once upon a time","The little","A big","I like to","One day a"]
           for e in ["girl","boy","dog","cat","bird","rabbit","tree","house","car","book"]][:30]

np.random.seed(42)

def generate(prompt, strategy, max_steps=60):
    ids = enc.encode(prompt); recent = collections.deque(maxlen=8)
    h_last, kv = prefill(ids); t0 = time.perf_counter()
    ur_history = []; bs_switches = 0

    for step in range(max_steps):
        lt = logits_from(h_last).copy()

        # ── 策略逻辑 ──
        if strategy == "greedy":
            tok = int(np.argmax(lt))
        elif strategy == "rep_penalty":
            for t in recent: lt[t] /= 1.15
            lt /= 0.8; lt -= lt.max()
            probs = np.exp(lt).astype(np.float32); probs /= probs.sum()
            topk = np.argsort(-probs)[:50]; tp = probs[topk]; tp /= tp.sum()
            tok = int(topk[np.random.choice(50, p=tp)])
        elif strategy == "adaptive":
            ur = ur_at(ids)
            ur_history.append(ur)
            if ur < 0.30:
                # 退化 → 贪心回退
                tok = int(np.argmax(lt))
                bs_switches += 1
            elif ur < 0.40:
                # 预警 → 加强惩罚
                for t in recent: lt[t] /= 1.30
                lt /= 0.9; lt -= lt.max()
                probs = np.exp(lt).astype(np.float32); probs /= probs.sum()
                topk = np.argsort(-probs)[:50]; tp = probs[topk]; tp /= tp.sum()
                tok = int(topk[np.random.choice(50, p=tp)])
            else:
                # 正常 → 无干预
                lt /= 0.8; lt -= lt.max()
                probs = np.exp(lt).astype(np.float32); probs /= probs.sum()
                topk = np.argsort(-probs)[:50]; tp = probs[topk]; tp /= tp.sum()
                tok = int(topk[np.random.choice(50, p=tp)])
        else:
            lt /= 0.8; lt -= lt.max()
            probs = np.exp(lt).astype(np.float32); probs /= probs.sum()
            topk = np.argsort(-probs)[:50]; tp = probs[topk]; tp /= tp.sum()
            tok = int(topk[np.random.choice(50, p=tp)])

        ids.append(tok); recent.append(tok)
        h_last = step_kv(tok, len(ids)-1, kv, h_last)

    dt = time.perf_counter() - t0
    final_ur = ur_at(ids)
    degen_rate = sum(1 for u in ur_history if u < 0.30) / max(len(ur_history), 1) if ur_history else 0
    return {"ur": final_ur, "degen_rate": degen_rate, "time": dt, "len": len(ids),
            "bs_switches": bs_switches, "text": enc.decode(ids)}

strategies = ["greedy", "sampling", "rep_penalty", "adaptive"]
results = {s: [] for s in strategies}

print("闭环实验: UR动态监控 + 自适应惩罚")
print("=" * 55)
for i, p in enumerate(prompts):
    row = []
    for s in strategies:
        r = generate(p, s)
        results[s].append(r)
        row.append(f"{s}: UR={r['ur']:.2f}")
    if i % 10 == 9: print(f"  {i+1}/30 {' | '.join(row[-2:])}")

print(f"\n{'='*55}")
print(f"{'Strategy':<15} {'Avg UR':>8} {'Degen%':>8} {'Time':>8} {'BS switches':>12}")
print("-" * 55)
for s in strategies:
    rs = results[s]
    avg_ur = np.mean([r['ur'] for r in rs])
    avg_degen = np.mean([r['degen_rate'] for r in rs])
    avg_time = np.mean([r['time'] for r in rs])
    bs_total = sum([r.get('bs_switches', 0) for r in rs])
    print(f"{s:<15} {avg_ur:8.3f} {avg_degen:7.1%} {avg_time:7.1f}s {bs_total:>12}")

# 样本展示
print(f"\n=== 样本 (第一个prompt) ===")
for s in ["greedy", "adaptive"]:
    r = results[s][0]
    print(f"\n{s}: UR={r['ur']:.3f} degen={r['degen_rate']:.1%} time={r['time']:.1f}s")
    print(f"  {r['text'][:200]}")

os.makedirs("benchmarks", exist_ok=True)
with open("benchmarks/adaptive_control.json", "w") as f:
    json.dump({s: {"avg_ur": float(np.mean([r['ur'] for r in results[s]])),
                    "avg_degen": float(np.mean([r['degen_rate'] for r in results[s]])),
                    "avg_time": float(np.mean([r['time'] for r in results[s]]))}
               for s in strategies}, f, indent=2)
print("\nSaved: benchmarks/adaptive_control.json")
