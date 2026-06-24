"""Print per-word token decomposition for report."""

import tiktoken
from transformers import AutoTokenizer

gpt2 = tiktoken.get_encoding('gpt2')
qwen = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B', local_files_only=True)

words = [
    '循环',
    '如果',
    '否则',
    '打印',
    '函数',
    '返回',
    '类',
    '导入',
    '当',
    '对于',
    '在',
    '捕获',
    '尝试',
    '打开',
    '映射',
    '过滤',
]

for w in words:
    g_parts = [gpt2.decode([t]) for t in gpt2.encode(w)]
    q_parts = [qwen.decode([t]) for t in qwen.encode(w)]
    g_str = ' + '.join(f'[{p!r}]' for p in g_parts)
    q_str = ' + '.join(f'[{p!r}]' for p in q_parts)
    print(f'| {w} | {len(gpt2.encode(w))} | {g_str} | {len(qwen.encode(w))} | {q_str} |')

# Byte-level analysis
print()
for ch in '循环':
    b = ch.encode('utf-8')
    g = [gpt2.decode([t]) for t in gpt2.encode(ch)]
    q = [qwen.decode([t]) for t in qwen.encode(ch)]
    print(
        f'{ch} -> UTF-8 {b.hex()} ({len(b)}B) -> GPT2: {len(gpt2.encode(ch))}t {g}  Qwen: {len(qwen.encode(ch))}t {q}'
    )
