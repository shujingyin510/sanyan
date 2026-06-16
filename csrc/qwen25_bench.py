#!/usr/bin/env python -X utf8
"""Qwen2.5-0.5B 1000 prompt — 验证 UR=0.30 零误报"""

import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import time
import numpy as np
import json

print('Loading Qwen2.5-0.5B...')
model = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-0.5B', torch_dtype='auto')
tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B')
print(f'Params: {sum(p.numel() for p in model.parameters()) / 1e6:.1f}M')

UR_TH = 0.30
np.random.seed(42)
torch.manual_seed(42)

templates = [
    'Once upon a time',
    'The little',
    'A big',
    'I like to',
    'One day a',
    'The sun was',
    'She went to',
    'He saw a',
    'There was a',
    'In the forest',
    'The old',
    'A tiny',
    'On the farm',
    'The happy',
    'She looked at',
    'He wanted to',
    'It was a',
    'The cat',
    'They went to',
    'After the rain',
    'The magic',
    'A golden',
    'Under the',
    'Behind the',
    'The brave',
    'A friendly',
    'On top of',
    'Inside the',
]
extras = [
    'girl',
    'boy',
    'dog',
    'cat',
    'bird',
    'rabbit',
    'tree',
    'house',
    'car',
    'book',
    'river',
    'mountain',
    'star',
    'moon',
    'sun',
    'cloud',
    'flower',
    'fish',
    'bear',
    'mouse',
]
N = 1000
prompts = [f'{templates[i % len(templates)]} {extras[(i // len(templates)) % len(extras)]}' for i in range(N)]

results = {'false_positives': 0, 'ur_mins': [], 'avg_len': [], 'total_time': 0}
t0_total = time.perf_counter()

for i, prompt in enumerate(prompts):
    inputs = tokenizer(prompt, return_tensors='pt')
    prompt_len = inputs['input_ids'].shape[1]

    with torch.no_grad():
        outputs = model.generate(
            **inputs, max_new_tokens=40, do_sample=True, temperature=0.8, top_k=50, pad_token_id=tokenizer.eos_token_id
        )
    ids = outputs[0].tolist()

    ur_min = 1.0
    negate_step = -1
    # Check UR at each position after prompt
    for pos in range(prompt_len + 8, len(ids)):
        r = ids[max(0, pos - 32) : pos]
        n = len(r)
        ur = len(set(r)) / n
        if ur < ur_min:
            ur_min = ur
        if ur < UR_TH and negate_step < 0:
            negate_step = pos - prompt_len + 1

    if negate_step > 0:
        results['false_positives'] += 1

    results['ur_mins'].append(ur_min)
    results['avg_len'].append(len(ids) - prompt_len)

    if i % 100 == 99:
        dt = time.perf_counter() - t0_total
        fp = results['false_positives']
        print(f'  {i + 1}/{N}  min_UR={np.mean(results["ur_mins"][-100:]):.3f}  FP={fp}/{i + 1}  time={dt:.0f}s')

dt_total = time.perf_counter() - t0_total
results['total_time'] = dt_total

print('\nQwen2.5-0.5B — 1000 prompt UR 零误报验证')
print(f'  UR threshold: {UR_TH}')
print(f'  False positives: {results["false_positives"]}/{N}')
print(f'  Min UR (avg): {np.mean(results["ur_mins"]):.3f}')
print(f'  Min UR (min): {min(results["ur_mins"]):.3f}')
print(f'  Total time: {dt_total:.0f}s')

with open('benchmarks/qwen25_ur_check.json', 'w', encoding='utf-8') as f:
    json.dump(
        {
            'N': N,
            'UR_TH': UR_TH,
            'false_positives': results['false_positives'],
            'min_UR_mean': float(np.mean(results['ur_mins'])),
            'min_UR_min': float(min(results['ur_mins'])),
            'time': dt_total,
        },
        f,
        indent=2,
    )

# Show worst-case prompts (lowest UR)
worst_idx = sorted(range(N), key=lambda i: results['ur_mins'][i])[:5]
print('\nLowest UR prompts:')
for idx in worst_idx:
    print(f"  UR={results['ur_mins'][idx]:.3f}  prompt='{prompts[idx]}'")
