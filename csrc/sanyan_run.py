#!/usr/bin/env python -X utf8
"""三言推理引擎 — .san 脚本运行器
用法: python -X utf8 csrc/sanyan_run.py csrc/infer_demo.san
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 1. 注册推理算子
import csrc.sanyan_ops  # noqa: F401

# 2. 解析并执行 .san 文件
from evaluator import SanyanEvaluator
from lexer import tokenize
from parser import parse

if len(sys.argv) < 2:
    print('用法: python -X utf8 csrc/sanyan_run.py <file.san>')
    sys.exit(1)

san_path = sys.argv[1]
source = open(san_path, encoding='utf-8').read()

evaluator = SanyanEvaluator(max_loop_steps=10000)
for line in source.strip().split('\n'):
    line = line.strip()
    if not line or line.startswith('//'):
        continue
    try:
        t = tokenize(line)
        if t:
            a = parse(t)
            if a:
                evaluator.eval(a)
    except Exception as e:
        print(f'  [!] {line[:60]}... -> {e}')
