"""Multi-tokenizer benchmark: Chinese DSL vs Python across 6 local models."""

import tiktoken
from transformers import AutoTokenizer
import os
from typing import Any

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

tokenizers = [
    ('Qwen2.5-0.5B', lambda: AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B', local_files_only=True)),
    ('GPT-2 124M', lambda: tiktoken.get_encoding('gpt2')),
    ('OPT-125M', lambda: AutoTokenizer.from_pretrained('facebook/opt-125m')),
    ('Pythia-160M', lambda: AutoTokenizer.from_pretrained('EleutherAI/pythia-160m')),
    ('SmolLM2-135M', lambda: AutoTokenizer.from_pretrained('HuggingFaceTB/SmolLM2-135M')),
    ('ByT5-300M', lambda: AutoTokenizer.from_pretrained('google/byt5-small')),
]

tests = [
    ('Loop 10x', '循环 10 次：\n    打印 i', 'for i in range(10):\n    print(i)'),
    (
        'If/else',
        '如果 x > 0：\n    打印 正数\n否则：\n    打印 负数',
        'if x > 0:\n    print("pos")\nelse:\n    print("neg")',
    ),
    ('Function', '函数 加(a, b)：\n    返回 a + b', 'def add(a, b):\n    return a + b'),
    ('List comp', '列表 = [x * 2 对于 x 在 范围(10)]', 'lst = [x * 2 for x in range(10)]'),
    ('File read', '打开 文件.txt 作为 f：\n    内容 = f.读取()', 'with open("file.txt") as f:\n    content = f.read()'),
    (
        'Try/catch',
        '尝试：\n    做某事()\n捕获 错误：\n    打印 出错了',
        'try:\n    do_something()\nexcept Exception:\n    print("error")',
    ),
    (
        'Class',
        '类 狗(动物)：\n    函数 叫()：\n        打印 汪汪',
        'class Dog(Animal):\n    def bark(self):\n        print("woof")',
    ),
    ('Dict comp', '字典 = {键: 值 对于 键, 值 在 项目}', 'd = {k: v for k, v in items}'),
    ('Lambda', '函数(x)：x + 1', 'lambda x: x + 1'),
    ('Import', '导入 数学', 'import math'),
    ('While', '当 x < 10：\n    x = x + 1', 'while x < 10:\n    x = x + 1'),
    ('Return', '返回 a + b * 2', 'return a + b * 2'),
    ('Assign', '名字 = 张三\n年龄 = 25', 'name = "Zhang San"\nage = 25'),
    (
        'Nested fn',
        '函数 外()：\n    函数 内()：\n        返回 42\n    返回 内()',
        'def outer():\n    def inner():\n        return 42\n    return inner()',
    ),
    (
        'Map/filter',
        '映射(函数(x)：x*2, 列表) 过滤(函数(x)：x>0, 列表)',
        'map(lambda x: x*2, lst) filter(lambda x: x>0, lst)',
    ),
]

# Load all tokenizers
encoders: dict[str, Any] = {}
for name, fn in tokenizers:
    try:
        encoders[name] = fn()
    except Exception as e:
        print(f'SKIP {name}: {e}')

# Header
header = f'{"Pattern":<14}'
for n in encoders:
    header += f' {n[:8]:>10}'
print(header)
header2 = f'{"":<14}'
for n in encoders:
    header2 += f' {"Δ%":>10}'
print(header2)
print('-' * (14 + 11 * len(encoders)))

totals_cn = {n: 0 for n in encoders}
totals_py = {n: 0 for n in encoders}

for pname, cn, py in tests:
    row = f'{pname:<14}'
    for n, enc in encoders.items():
        cn_tk = len(enc.encode(cn))
        py_tk = len(enc.encode(py))
        totals_cn[n] += cn_tk
        totals_py[n] += py_tk
        gap = (1 - cn_tk / py_tk) * 100
        row += f' {gap:>+9.0f}%'
    print(row)

# Totals
print('-' * (14 + 11 * len(encoders)))
row = f'{"TOTAL":<14}'
for n in encoders:
    tc, tp = totals_cn[n], totals_py[n]
    gap = (1 - tc / tp) * 100
    row += f' {gap:>+9.0f}%'
print(row)

# Summary
print(f'\n{"Model":<20} {"Vocab":>8} {"CN avg":>7} {"PY avg":>7} {"Gap":>6}')
print('-' * 52)
for n in encoders:
    tc, tp = totals_cn[n], totals_py[n]
    vocab = getattr(encoders[n], 'vocab_size', getattr(encoders[n], 'n_vocab', '?'))
    cn_avg = tc / len(tests)
    py_avg = tp / len(tests)
    gap = (1 - tc / tp) * 100
    print(f'{n:<20} {str(vocab):>8} {cn_avg:>6.1f} {py_avg:>6.1f} {gap:>+5.0f}%')
