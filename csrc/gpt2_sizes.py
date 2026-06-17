"""GPT-2 small/medium/large — nucleus sampling UR 稳定性"""

import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import numpy as np

prompts = ['Once upon a time', 'The little girl went to the', 'A big dog ran through', 'I like to play with']
np.random.seed(42)
torch.manual_seed(42)

models = {
    'GPT-2 (124M)': 'openai-community/gpt2',
    'GPT-2 Medium (355M)': 'openai-community/gpt2-medium',
    'GPT-2 Large (774M)': 'openai-community/gpt2-large',
}

print('GPT-2 跨规模 nucleus sampling UR 稳定性')
print('=' * 55)

for name, model_id in models.items():
    print(f'\nLoading {name}...')
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype='auto')
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.pad_token = tokenizer.eos_token

    ur_values = []
    for p in prompts:
        inputs = tokenizer(p, return_tensors='pt')
        with torch.no_grad():
            o = model.generate(
                **inputs,
                max_new_tokens=50,
                do_sample=True,
                temperature=0.8,
                top_p=0.9,
                top_k=0,
                pad_token_id=tokenizer.eos_token_id,
            )
        ids = o[0].tolist()
        # UR at last 32 tokens
        r = ids[-32:] if len(ids) >= 32 else ids
        ur = len(set(r)) / max(len(r), 1)
        ur_values.append(ur)
        text = tokenizer.decode(ids, skip_special_tokens=True)[:100]
        print(f'  [{p[:30]:30s}] UR={ur:.3f}  -> {text}')

    avg_ur = np.mean(ur_values)
    min_ur = min(ur_values)
    below_03 = sum(1 for u in ur_values if u < 0.30)
    print(f'  => avg_UR={avg_ur:.3f}  min={min_ur:.3f}  <0.30: {below_03}/{len(prompts)}')

    # Free memory
    del model
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
