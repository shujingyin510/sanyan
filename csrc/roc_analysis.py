#!/usr/bin/env python -X utf8
"""ROC曲线 + 阈值敏感性分析 — 基于实测数据"""
import torch, numpy as np, tiktoken, ctypes, json, os

enc = tiktoken.get_encoding("gpt2")

# ══════════════════════════════════════════════════
# 1. 收集所有实测 UR 数据
# ══════════════════════════════════════════════════

def ur_sliding(ids, window=32):
    """从 token list 提取所有滑动窗口的 UR 值"""
    urs = []
    for pos in range(window, len(ids) + 1):
        r = ids[max(0, pos - window):pos]
        if len(r) >= 8:
            urs.append(len(set(r)) / len(r))
    return urs

# A. 人类文本 (8 段经典文学)
human_texts = [
    "The quick brown fox jumps over the lazy dog. The dog was sleeping in the sun and did not notice the fox passing by. It was a warm afternoon in the countryside and all the animals were resting.",
    "Once upon a time there was a little girl who lived in a village near the forest. Whenever she went out, she wore a red riding cloak, so everyone called her Little Red Riding Hood.",
    "Alice was beginning to get very tired of sitting by her sister on the bank, and of having nothing to do. Once or twice she had peeped into the book her sister was reading.",
    "It is a truth universally acknowledged that a single man in possession of a good fortune must be in want of a wife. However little known the feelings or views of such a man.",
    "The sun was setting behind the mountains, casting long shadows across the valley. Birds flew home to their nests and the first stars began to appear in the darkening sky.",
    "In the beginning God created the heaven and the earth. And the earth was without form and void and darkness was upon the face of the deep. And the Spirit of God moved upon the face of the waters.",
    "Call me Ishmael. Some years ago never mind how long precisely having little or no money in my purse and nothing particular to interest me on shore I thought I would sail about.",
    "It was the best of times it was the worst of times it was the age of wisdom it was the age of foolishness it was the epoch of belief it was the epoch of incredulity.",
]
human_ur = []
for s in human_texts:
    ids = enc.encode(s)
    human_ur.extend(ur_sliding(ids))

# B. 退化文本 (GPT-2 退化输出 — 来自 benchmark)
degen_texts = [
    "Once upon a time girl girl girl girl boy boy boy boy boy kids kids kids kids children children children children boys boys boys boys " * 3,
    "The little boy was was was was was was was was was was was was was was was was was was was was was " * 3,
    "A big dog that that that that that that that that that that that that that that that that that " * 3,
    "I like to cat people people people people people people people people people people people people " * 3,
    "and and and and and and and and and and and and and and and and and and and and and and and " * 3,
    "to to to to to to to to to to to to to to to to to to to to to to to to to to to to " * 3,
    "it it it it it it it it it it it it it it it it it it it it it it it it " * 3,
    "the the the the the the the the the the the the the the the the the the " * 3,
]
degen_ur = []
for s in degen_texts:
    ids = enc.encode(s)
    degen_ur.extend(ur_sliding(ids))

# C. 正常模型生成 — 从 GPT-2 124M 跑 nucleus sampling 收集 UR
print("Generating GPT-2 124M nucleus samples for normal UR data...")

lib_t = ctypes.CDLL("csrc/transformer_c.dll")
lib_t.layernorm.argtypes = [ctypes.c_void_p] * 4 + [ctypes.c_int, ctypes.c_float]

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

np.random.seed(42)
normal_ur = []

prompts = [f"{t} {e}" for t in ["Once upon a time","The little","A big","I like to","One day a"]
           for e in ["girl","boy","dog","cat","bird","rabbit","tree","house","car","book"]][:30]

for i, prompt in enumerate(prompts):
    ids = enc.encode(prompt)
    h_last, kv = prefill(ids)
    for step in range(40):
        hf = c_ln(h_last[0], lfw, lfb)
        logits = (hf @ emb_w.T).astype(np.float32)
        lt = logits.copy(); lt /= 0.8; lt -= lt.max()
        probs = np.exp(lt).astype(np.float32); probs /= probs.sum()
        # nucleus sampling top_p=0.9
        sorted_idx = np.argsort(-probs)
        cumsum = np.cumsum(probs[sorted_idx])
        cutoff = int(np.searchsorted(cumsum, 0.9) + 1)
        nucleus = sorted_idx[:cutoff]
        np2 = probs[nucleus]; np2 /= np2.sum()
        tok = int(nucleus[np.random.choice(len(nucleus), p=np2)])
        ids.append(tok)

        if len(ids) >= 16:
            r = ids[-32:] if len(ids) >= 32 else ids
            normal_ur.append(len(set(r)) / max(len(r), 1))

        pos = len(ids) - 1
        h_new = (emb_w[tok:tok+1] + pos_w[pos:pos+1]).astype(np.float32)
        for li, ws in enumerate(LWS):
            hn = c_ln(h_new[0], ws["ln_1.weight"], ws["ln_1.bias"]).reshape(1,dim)
            qkv = (hn @ ws["attn.c_attn.weight"] + ws["attn.c_attn.bias"]).astype(np.float32)
            q = qkv[:,:dim].reshape(1,heads,hd).transpose(1,0,2)
            k = qkv[:,dim:2*dim].reshape(1,heads,hd).transpose(1,0,2)
            v = qkv[:,2*dim:].reshape(1,heads,hd).transpose(1,0,2)
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
        h_last = h_new
    if i % 10 == 9: print(f"  {i+1}/30 prompts done")

# Also load Qwen2.5 1000-prompt data if available
qwen_ur = []
if os.path.exists("benchmarks/qwen25_ur_check.json"):
    # We have min_UR per prompt, use as representative
    pass  # min_UR is a single value, not a sliding window set

# ══════════════════════════════════════════════════
# 2. 构建 ROC / 敏感性表
# ══════════════════════════════════════════════════

all_ur = np.array(degen_ur + normal_ur + human_ur)
all_labels = np.array([1]*len(degen_ur) + [0]*len(normal_ur) + [0]*len(human_ur))

print(f"\nData summary:")
print(f"  Degenerate: {len(degen_ur)} samples, mean={np.mean(degen_ur):.3f}")
print(f"  Normal (GPT-2 nucleus): {len(normal_ur)} samples, mean={np.mean(normal_ur):.3f}")
print(f"  Human text: {len(human_ur)} samples, mean={np.mean(human_ur):.3f}")

# ROC table
print(f"\nThreshold Sensitivity (real data):")
print(f"{'Thr':>6} {'TPR':>6} {'FPR':>6} {'Prec':>6} {'F1':>6} {'J':>6}")
print("-" * 42)
best_j = -1; best_th = 0; results = []
for th in np.arange(0.10, 0.51, 0.02):
    pred = (all_ur < th).astype(int)
    tp = ((pred == 1) & (all_labels == 1)).sum()
    fp = ((pred == 1) & (all_labels == 0)).sum()
    tn = ((pred == 0) & (all_labels == 0)).sum()
    fn = ((pred == 0) & (all_labels == 1)).sum()
    tpr = tp / max(tp + fn, 1)
    fpr = fp / max(fp + tn, 1)
    prec = tp / max(tp + fp, 1)
    f1 = 2 * prec * tpr / max(prec + tpr, 0.001)
    j = tpr - fpr
    if j > best_j and th >= 0.20:
        best_j = j; best_th = th
    results.append({"th": float(th), "tpr": float(tpr), "fpr": float(fpr), "f1": float(f1), "j": float(j)})
    marker = " ←" if abs(th - 0.30) < 0.005 else (" *" if abs(th - best_th) < 0.005 else "")
    print(f"{th:6.2f} {tpr:6.3f} {fpr:6.3f} {prec:6.3f} {f1:6.3f} {j:6.3f}{marker}")

print(f"\nYouden's J optimum: {best_th:.2f} (J={best_j:.3f})")
print(f"Our threshold:      0.30")
print(f"Human-degen midpoint: {((np.mean(human_ur)+np.mean(degen_ur))/2):.3f}")

# Save
os.makedirs("benchmarks", exist_ok=True)
with open("benchmarks/roc_data.json", "w") as f:
    json.dump({
        "human_ur": [float(x) for x in human_ur],
        "degen_ur": [float(x) for x in degen_ur],
        "normal_ur": [float(x) for x in normal_ur],
        "sweep": results,
        "best_j_th": float(best_th),
        "best_j": float(best_j),
    }, f, indent=2)
print("\nSaved: benchmarks/roc_data.json")
