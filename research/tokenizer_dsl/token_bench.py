"""Token efficiency: Chinese DSL vs Python — GPT-2 tokenizer vs Qwen2.5 tokenizer"""

import tiktoken
from transformers import AutoTokenizer

enc_gpt2 = tiktoken.get_encoding('gpt2')
enc_qwen = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B', local_files_only=True)

tests = [
    ('Loop 10x', '循环 10 次：\n    打印 i', 'for i in range(10):\n    print(i)'),
    (
        'If/else',
        '如果 x > 0：\n    打印 正数\n否则：\n    打印 负数',
        'if x > 0:\n    print("positive")\nelse:\n    print("negative")',
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
    ('While loop', '当 x < 10：\n    x = x + 1', 'while x < 10:\n    x = x + 1'),
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

print(f'{"Pattern":<14} {"GPT2-CN":>8} {"GPT2-PY":>8} {"GPT2-Δ":>7} | {"QWEN-CN":>8} {"QWEN-PY":>8} {"QWEN-Δ":>7}')
print('-' * 70)
total_g2cn, total_g2py = 0, 0
total_qwcn, total_qwpy = 0, 0
for name, cn, py in tests:
    g2cn = len(enc_gpt2.encode(cn))
    g2py = len(enc_gpt2.encode(py))
    qwcn = len(enc_qwen.encode(cn))
    qwpy = len(enc_qwen.encode(py))
    total_g2cn += g2cn
    total_g2py += g2py
    total_qwcn += qwcn
    total_qwpy += qwpy
    g2d = (1 - g2cn / g2py) * 100
    qwd = (1 - qwcn / qwpy) * 100
    print(f'{name:<14} {g2cn:>8} {g2py:>8} {g2d:>+6.0f}% | {qwcn:>8} {qwpy:>8} {qwd:>+6.0f}%')

print('-' * 70)
g2d = (1 - total_g2cn / total_g2py) * 100
qwd = (1 - total_qwcn / total_qwpy) * 100
print(f'{"TOTAL":<14} {total_g2cn:>8} {total_g2py:>8} {g2d:>+6.0f}% | {total_qwcn:>8} {total_qwpy:>8} {qwd:>+6.0f}%')
print(
    f'\nGPT-2: Chinese {total_g2cn / len(tests):.1f} tk/snip  Python {total_g2py / len(tests):.1f} tk/snip  → {"+" if g2d < 0 else ""}{-g2d:.0f}% {"worse" if g2d < 0 else "better"} for Chinese'
)
print(
    f'Qwen:  Chinese {total_qwcn / len(tests):.1f} tk/snip  Python {total_qwpy / len(tests):.1f} tk/snip  → {"+" if qwd < 0 else ""}{-qwd:.0f}% {"worse" if qwd < 0 else "better"} for Chinese'
)
