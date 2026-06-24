"""Controlled tokenizer experiment v2 — cleaner causal proof.

Three scenarios for the SAME Chinese DSL code:
  A) GPT-2 native: each Chinese char → 2-3 byte-fragment tokens
  B) "Dream" tokenizer: each Chinese char = 1 token (like Qwen for known chars, GPT-2 for ASCII)
  C) Qwen native: upper bound
"""

import tiktoken
import re
from transformers import AutoTokenizer

gpt2 = tiktoken.get_encoding('gpt2')
qwen = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B', local_files_only=True)

dsl = """函数 计算(数字)：
    如果 数字 > 0：
        打印 正数
    否则：
        打印 负数"""

# ── A) GPT-2 native ──
g_tokens = gpt2.encode(dsl)
# Count Chinese chars vs ASCII in tokens
cn_chars = len(re.findall(r'[\u4e00-\u9fff]', dsl))
ascii_chars = len(dsl) - cn_chars


# ── B) "Dream" tokenizer: Chinese chars = 1 token, ASCII = GPT-2 token ──
# This is a plausible upper bound if every Chinese char were in vocab
def dream_tokenize(text):
    tk = 0
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            tk += 1  # Chinese/full-width = 1 token
        elif ch in (' ', '\n', '\t'):
            tk += 1  # whitespace groups would be better, but keep simple
        else:
            tk += len(gpt2.encode(ch))  # ASCII via GPT-2
    return tk


d_cost = dream_tokenize(dsl)
q_cost = len(qwen.encode(dsl))

# ── Print ──
print('=' * 60)
print('  因果证明：纯 Tokenizer 词表 → Token 开销')
print('=' * 60)
print(f'\n代码: {len(dsl)} chars ({cn_chars} 中文 + {len(dsl) - cn_chars} ASCII)')
print()

print(f'{"Tokenizer":<32} {"Token":>6} {"vs原生":>8} {"vs Qwen":>7}')
print('-' * 55)
print(f'{"A) GPT-2 原生（0% 中文覆盖）":<32} {len(g_tokens):>6}')
print(
    f'{"B) Dream（每个中文=1tk）":<32} {d_cost:>6}  {(1 - d_cost / len(g_tokens)) * 100:>+7.0f}%  {(d_cost / q_cost - 1) * 100:>+7.0f}%'
)
print(f'{"C) Qwen（151k 双语词表）":<32} {q_cost:>6}  {(1 - q_cost / len(g_tokens)) * 100:>+7.0f}%  {"—":>7}')
print()

print('关键数字：')
print(
    f'  GPT-2: {cn_chars} 个中文 × avg {sum(len(gpt2.encode(c)) for c in dsl if "\\u4e00" <= c <= "\\u9fff") / cn_chars:.1f} tk/字 = 中文部分占 {sum(len(gpt2.encode(c)) for c in dsl if "\\u4e00" <= c <= "\\u9fff")} tk'
)
print(f'  Dream: 每个中文 = 1 tk → 中文部分仅 {cn_chars} tk')
print(f'  Qwen: {q_cost} tk（含天然 1tk 中文 + ASCII 优化）')
print(f'\nGPT-2 vs Dream 的 {len(g_tokens) - d_cost} token 差距 = 纯 tokenizer 词表是否含中文')
print(f"Dream vs Qwen 的 {d_cost - q_cost} token 差距 = subword 合并优化（如'打印'→1tk 而非 2tk）")

# Token composition breakdown
print(f'\n{"中文字":<6} {"GPT2 tk":>8} {"UTF8bytes":>10}')
total_g = 0
for c in sorted(set(c for c in dsl if '\u4e00' <= c <= '\u9fff')):
    tk = len(gpt2.encode(c))
    b = c.encode('utf-8')
    total_g += tk * dsl.count(c)
    print(f'{c:<6} {tk:>8} {b.hex():>10}')
print(f'{"合计":<6} {total_g:>8}')
