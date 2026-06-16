import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import numpy as np

model = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-0.5B', torch_dtype='auto')
tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B')
np.random.seed(42)
torch.manual_seed(42)

bad_prompts = [
    'cat cat cat cat cat cat',
    'dog dog dog dog dog dog dog dog',
    'the the the the the the the the the',
    'was was was was was was was was was was',
    'asdf qwer zxcv poiu lkjh mnbv',
    'aaaaaaaa bbbbbbbb cccccccc dddddddd',
    'The went to a with in the',
    'She he it they we us me them',
    'And but or so because however therefore',
]
UR_TH = 0.30
print('Qwen2.5 induced degeneration test')
for prompt in bad_prompts:
    inputs = tokenizer(prompt, return_tensors='pt')
    plen = inputs['input_ids'].shape[1]
    with torch.no_grad():
        outputs = model.generate(
            **inputs, max_new_tokens=40, do_sample=True, temperature=0.8, top_k=50, pad_token_id=tokenizer.eos_token_id
        )
    ids = outputs[0].tolist()
    ur_min = 1.0
    negate_at = -1
    for pos in range(plen + 8, len(ids)):
        r = ids[max(0, pos - 32) : pos]
        n = len(r)
        ur = len(set(r)) / n
        if ur < ur_min:
            ur_min = ur
        if ur < UR_TH and negate_at < 0:
            negate_at = pos - plen + 1
    text = tokenizer.decode(ids, skip_special_tokens=True)
    status = 'NEGATE' if negate_at > 0 else 'OK'
    print(f'  [{prompt[:40]:40s}] min_UR={ur_min:.3f} stop_at={negate_at} {status}')
    print(f'    -> {text[:150]}')
