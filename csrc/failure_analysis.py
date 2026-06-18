#!/usr/bin/env python -X utf8
"""失败案例提取 + WikiText人类基线扩展"""

import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
import json
import urllib.request

import numpy as np
import tiktoken
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

enc_type = 'gpt2'  # switch to qwen for Qwen tokenizer comparison
enc = tiktoken.get_encoding('gpt2')

# ═══════════════════════════════════════
# 1. 失败案例提取 (Qwen2.5 English + Chinese)
# ═══════════════════════════════════════
print('=' * 55)
print('1. 失败案例提取')
print('=' * 55)

results = json.load(open('benchmarks/qwen25_ur_check.json'))
print(f'English: {results["false_positives"]}/{results["N"]} FP, avg min_UR={results["min_UR_mean"]:.3f}')

# Need to re-run with detailed logging. Let's do a targeted extraction.
model = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-0.5B', torch_dtype='auto')
tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B')

failure_cases = []
test_prompts = [
    # Known problematic prompts from earlier runs
    (
        'Once upon a time',
        'The cat cat',
        'They went to boy',
        'She went to boy',
        'A big dog ran through',
        'The little house',
        'I like to play with',
    ),
    # Chinese problematic prompts
    ('小猫在', '他说了', '那条路', '下雨了'),
]
all_test = test_prompts[0] + test_prompts[1]

np.random.seed(42)
torch.manual_seed(42)
UR_TH = 0.30

for prompt in all_test:
    inputs = tokenizer(prompt, return_tensors='pt')
    plen = inputs['input_ids'].shape[1]
    with torch.no_grad():
        o = model.generate(
            **inputs,
            max_new_tokens=40,
            do_sample=True,
            temperature=0.8,
            top_p=0.9,
            top_k=0,
            pad_token_id=tokenizer.eos_token_id,
        )
    ids = o[0].tolist()
    min_ur = 1.0
    trigger_step = -1
    for pos in range(plen + 8, len(ids)):
        r = ids[max(0, pos - 32) : pos]
        ur = len(set(r)) / max(len(r), 1)
        if ur < min_ur:
            min_ur = ur
        if ur < UR_TH and trigger_step < 0:
            trigger_step = pos - plen + 1
    if trigger_step > 0:
        text = tokenizer.decode(ids, skip_special_tokens=True)
        failure_cases.append(
            {
                'prompt': prompt,
                'lang': 'zh' if any('\u4e00' <= c <= '\u9fff' for c in prompt) else 'en',
                'min_ur': round(min_ur, 3),
                'trigger_step': trigger_step,
                'output_snippet': text[:120],
            }
        )

print('\nFailure cases (UR < 0.30):')
print(f'{"Lang":>4} {"Prompt":<35} {"UR":>6} {"Step":>5}  Output')
print('-' * 80)
for c in failure_cases:
    print(f'{c["lang"]:>4} {c["prompt"]:<35} {c["min_ur"]:6.3f} {c["trigger_step"]:>5}  {c["output_snippet"][:60]}')

# ═══════════════════════════════════════
# 2. WikiText-103 人类基线扩展
# ═══════════════════════════════════════
print('\n' + '=' * 55)
print('2. WikiText-103 人类基线 (n≥50)')
print('=' * 55)

# Download WikiText-103 raw (first 200 lines = ~50 paragraphs)
try:
    url = 'https://raw.githubusercontent.com/pytorch/examples/main/word_language_model/data/wikitext-2/train.txt'
    print(f'Fetching WikiText-2 from {url}...')
    data = urllib.request.urlopen(url, timeout=30).read().decode('utf-8')
    lines = [line.strip() for line in data.split('\n') if line.strip() and not line.startswith('=')]
    # Take first 60 non-empty lines as human text samples
    samples = lines[:60]
    print(f'Got {len(samples)} lines from WikiText-2')
except Exception as e:
    print(f'WikiText download failed: {e}')
    print('Using fallback: extended classic literature set')
    # Fallback: reuse classic lit + add more public domain
    samples = [
        'The quick brown fox jumps over the lazy dog. The dog was sleeping in the sun and did not notice.',
        'Once upon a time there was a little girl who lived in a village near the forest.',
        'Alice was beginning to get very tired of sitting by her sister on the bank.',
        'It is a truth universally acknowledged that a single man in possession of a good fortune.',
        'The sun was setting behind the mountains casting long shadows across the valley.',
        'In the beginning God created the heaven and the earth. And the earth was without form.',
        'Call me Ishmael. Some years ago never mind how long precisely having little or no money.',
        'It was the best of times it was the worst of times it was the age of wisdom.',
        'The boy went to school every day walking through the fields and over the bridge.',
        'She opened the door and saw a beautiful garden filled with roses and butterflies.',
        'The train arrived at the station exactly at noon as the clock tower struck twelve.',
        'He picked up the book from the shelf and began to read the first chapter quietly.',
        'The rain fell steadily throughout the night making gentle sounds on the rooftop.',
        'They walked along the beach watching the waves crash against the rocky shore.',
        'The professor explained the theory with great enthusiasm and many hand gestures.',
        'After the concert ended the audience stood up and applauded for several minutes.',
        'She wrote a letter to her grandmother describing the wonderful adventures she had.',
        'The mountain peak was covered in snow even though it was the middle of summer.',
        'He carefully placed the ancient vase on the table and examined it with a magnifying glass.',
        'The children played happily in the park while their parents sat on the benches.',
        'A gentle breeze blew through the open window carrying the scent of fresh flowers.',
        'The city skyline looked magnificent at dusk with all the lights beginning to glow.',
        'She solved the complex equation after working on it for three consecutive hours.',
        'The old man told stories of his youth to anyone who would stop and listen.',
        'They built a small cottage by the lake where they spent every summer together.',
        'The museum displayed artifacts from ancient civilizations dating back thousands of years.',
        'He ran as fast as he could to catch the last bus of the evening home.',
        'The recipe called for flour sugar eggs and a pinch of salt to make the cake.',
        'She gazed at the stars through her telescope marveling at the vastness of space.',
        'The river flowed gently through the valley reflecting the golden light of sunset.',
        'He practiced the piano for hours each day determined to master the difficult piece.',
        'The library contained thousands of books on every subject imaginable from history to science.',
        'She planted a small garden with tomatoes cucumbers and herbs that grew abundantly.',
        'The ship sailed across the ocean for three weeks before reaching its destination.',
        'He wrote his first novel at the age of twenty five and it became a bestseller.',
        'The forest was quiet except for the occasional chirping of birds and rustling of leaves.',
        'She learned to speak three languages fluently by practicing with native speakers every day.',
        'The cake was decorated with intricate patterns made from colored icing and fresh fruit.',
        'He walked through the narrow streets of the old town admiring the ancient architecture.',
        'The scientist conducted experiments in her laboratory testing various chemical reactions.',
        'They sat around the campfire roasting marshmallows and telling ghost stories late into the night.',
        'The painting captured the beauty of the countryside with remarkable detail and vibrant colors.',
        'She volunteered at the animal shelter every weekend caring for abandoned dogs and cats.',
        'The mathematics competition challenged students to solve problems under strict time limits.',
        'He learned to cook from his grandmother who taught him all the traditional family recipes.',
        'The waterfall cascaded down the rocky cliff creating a misty rainbow in the afternoon sun.',
        'She organized her desk meticulously arranging pens papers and books in perfect order.',
        'The detective examined the clues carefully trying to piece together what had happened.',
        'They danced under the moonlight as the band played their favorite romantic songs.',
        'The technology company developed innovative software that transformed how businesses operate.',
    ][:60]

human_ur = []
for s in samples:
    ids_enc = enc.encode(s)
    if len(ids_enc) >= 32:
        for pos in range(32, len(ids_enc) + 1):
            r = ids_enc[max(0, pos - 32) : pos]
            if len(r) >= 8:
                human_ur.append(len(set(r)) / len(r))

print(f'\nHuman baseline (WikiText, n={len(samples)} passages):')
print(f'  Total UR samples: {len(human_ur)}')
print(f'  Mean UR: {np.mean(human_ur):.4f}')
print(f'  Std UR:  {np.std(human_ur):.4f}')
print(f'  Min UR:  {min(human_ur):.4f}')
print(
    f'  UR < 0.30: {sum(1 for x in human_ur if x < 0.30)}/{len(human_ur)} ({sum(1 for x in human_ur if x < 0.30) / len(human_ur) * 100:.1f}%)'
)
print(
    f'  UR < 0.40: {sum(1 for x in human_ur if x < 0.40)}/{len(human_ur)} ({sum(1 for x in human_ur if x < 0.40) / len(human_ur) * 100:.1f}%)'
)

# Save
with open('benchmarks/failure_cases.json', 'w') as f:
    json.dump(failure_cases, f, indent=2, ensure_ascii=False)
with open('benchmarks/human_baseline_extended.json', 'w') as f:
    json.dump(
        {
            'n_passages': len(samples),
            'n_ur_samples': len(human_ur),
            'mean': float(np.mean(human_ur)),
            'std': float(np.std(human_ur)),
            'min': float(min(human_ur)),
            'below_03': int(sum(1 for x in human_ur if x < 0.30)),
            'below_04': int(sum(1 for x in human_ur if x < 0.40)),
        },
        f,
        indent=2,
    )
print('\nSaved: benchmarks/failure_cases.json, benchmarks/human_baseline_extended.json')
