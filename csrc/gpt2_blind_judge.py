"""GPT-2 124M 盲评引擎"""

import json


def has_garbled(text):
    words = text.split()
    for w in words:
        if len(w) > 8:
            return True
        for i in range(len(w) - 2):
            if w[i] == w[i + 1] == w[i + 2]:
                return True
    return False


def evaluate(a_text, b_text):
    a_g = has_garbled(a_text)
    b_g = has_garbled(b_text)
    a_len = len(a_text.split())
    b_len = len(b_text.split())
    lr = min(a_len, b_len) / max(a_len, b_len) if max(a_len, b_len) > 0 else 1

    completeness = 'tie'
    naturalness = 'tie'
    stop_timing = 'tie'

    # 停止时机：更短更好（退化场景）
    if lr < 0.70:
        if a_len < b_len and not a_g:
            stop_timing = 'A'
        elif b_len < a_len and not b_g:
            stop_timing = 'B'
        elif a_len < b_len:
            stop_timing = 'A'
        else:
            stop_timing = 'B'

    # 完整性
    if lr < 0.55:
        if a_len < b_len:
            completeness = 'A'
        else:
            completeness = 'B'
    elif lr < 0.75:
        a_bigr = len(set(zip(a_text.split(), a_text.split()[1:]))) if len(a_text.split()) > 1 else 0
        b_bigr = len(set(zip(b_text.split(), b_text.split()[1:]))) if len(b_text.split()) > 1 else 0
        if a_bigr > b_bigr * 1.3:
            completeness = 'A'
        elif b_bigr > a_bigr * 1.3:
            completeness = 'B'

    # 自然度：主要看乱码
    if a_g and not b_g:
        naturalness = 'B'
    elif b_g and not a_g:
        naturalness = 'A'
    else:
        a_uniq = len(set(a_text.split())) / max(len(a_text.split()), 1)
        b_uniq = len(set(b_text.split())) / max(len(b_text.split()), 1)
        if a_uniq > b_uniq * 1.5:
            naturalness = 'A'
        elif b_uniq > a_uniq * 1.5:
            naturalness = 'B'

    return completeness, naturalness, stop_timing


d = json.load(open('benchmarks/blind_eval_gpt2.json', encoding='utf-8'))
ternary_wins = {'completeness': 0, 'naturalness': 0, 'stop_timing': 0}
eos_wins = {'completeness': 0, 'naturalness': 0, 'stop_timing': 0}
tie = {'completeness': 0, 'naturalness': 0, 'stop_timing': 0}

for p in d:
    c, n, s = evaluate(p['A'], p['B'])
    for dim_name, choice in [('completeness', c), ('naturalness', n), ('stop_timing', s)]:
        winner = p['A_label'] if choice == 'A' else (p['B_label'] if choice == 'B' else 'tie')
        if winner == 'ternary':
            ternary_wins[dim_name] += 1
        elif winner == 'eos':
            eos_wins[dim_name] += 1
        else:
            tie[dim_name] += 1

print('GPT-2 124M — 100 题盲评结果')
print('=' * 45)
print(f'{"维度":<12} {"三元胜":>6} {"EOS胜":>6} {"平局":>6}')
print('-' * 42)
for dim in ['completeness', 'naturalness', 'stop_timing']:
    tw = ternary_wins[dim]
    ew = eos_wins[dim]
    te = tie[dim]
    print(f'{dim:<12} {tw:>6} {ew:>6} {te:>6}')

with open('benchmarks/blind_eval_gpt2_results.json', 'w', encoding='utf-8') as f:
    json.dump({'ternary_wins': ternary_wins, 'eos_wins': eos_wins, 'tie': tie}, f, indent=2)
print('\nSaved: benchmarks/blind_eval_gpt2_results.json')
