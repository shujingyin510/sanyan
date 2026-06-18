#!/usr/bin/env python -X utf8
"""Qwen2.5-0.5B 中文 1000 prompt UR 零误报验证"""

import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import numpy as np
import time
import json

print('Loading Qwen2.5-0.5B...')
model = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-0.5B', torch_dtype='auto')
tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B')
torch.manual_seed(42)
np.random.seed(42)

# 1000 Chinese prompts — varied sentence starters
zh_template = [
    '从前有一个',
    '小男孩在',
    '一只大狗',
    '今天天气',
    '他走进了',
    '她看着窗外',
    '那座山上',
    '小明每天',
    '老师说',
    '春天来了',
    '我喜欢',
    '妈妈做的',
    '爸爸告诉',
    '学校里',
    '夜晚的星空',
    '小猫在',
    '那本书',
    '河水很',
    '远处的',
    '昨天的',
    '他决定',
    '她突然',
    '这座城市的',
    '我们一起去',
    '他画了一幅',
    '她唱歌',
    '火车',
    '篮球场上',
    '冰箱里有',
    '花园里',
    '他打开手机',
    '天黑了',
    '海边',
    '周末',
    '考试前',
    '他梦见',
    '她收到一封',
    '那条路',
    '爷爷说过',
    '童年的',
    '每当',
    '虽然',
    '因为他',
    '如果明天',
    '只要努力',
    '在那个遥远的',
    '一阵风吹过',
    '雨后',
    '阳光洒在',
    '深夜里',
]
zh_extra = [
    '故事',
    '路上',
    '花开了',
    '很冷',
    '教室',
    '菜很好吃',
    '信',
    '一个秘密',
    '很热闹',
    '很美',
    '睡觉了',
    '很好看',
    '清澈',
    '山峰',
    '会议',
    '去旅行',
    '笑了',
    '夜景',
    '散步',
    '画',
    '很好听',
    '站',
    '比赛',
    '水果',
    '虫鸣',
    '看新闻',
    '星星',
    '沙滩',
    '作业',
    '复习',
    '飞翔',
    '邮件',
    '很长',
    '故事',
    '回忆',
    '下雨',
    '难过',
    '生病',
    '晴天',
    '坚持',
    '地方',
    '叶子',
    '彩虹',
    '脸上',
    '醒来',
]
prompts = [
    f'{zh_template[i % len(zh_template)]}{zh_extra[(i // len(zh_template)) % len(zh_extra)]}' for i in range(1000)
]

UR_TH = 0.30
fp = 0
ur_mins = []
t0 = time.perf_counter()
for i, p in enumerate(prompts):
    inputs = tokenizer(p, return_tensors='pt')
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
    triggered = False
    min_ur = 1.0
    for pos in range(plen + 8, len(ids)):
        r = ids[max(0, pos - 32) : pos]
        ur = len(set(r)) / max(len(r), 1)
        if ur < min_ur:
            min_ur = ur
        if ur < UR_TH and not triggered:
            triggered = True
            fp += 1
    ur_mins.append(min_ur)
    if i % 100 == 99:
        dt = time.perf_counter() - t0
        print(f'  {i + 1}/1000 FP={fp} avg_min_UR={np.mean(ur_mins[-100:]):.3f} time={dt:.0f}s')

dt = time.perf_counter() - t0
print('\nQwen2.5-0.5B 中文 1000 prompt:')
print(f'  False positives @ 0.30: {fp}/1000 ({fp / 10:.1f}%)')
print(f'  Min UR (avg): {np.mean(ur_mins):.4f}')
print(f'  Min UR (min): {min(ur_mins):.4f}')
print(f'  Time: {dt:.0f}s')
print('\n=== 中英对比 ===')
print('  英文 (1000 prompt): FP=4/1000 (0.4%), avg min_UR=0.717')
print(f'  中文 (1000 prompt): FP={fp}/1000 ({fp / 10:.1f}%), avg min_UR={np.mean(ur_mins):.3f}')

with open('benchmarks/qwen25_zh_ur_check.json', 'w', encoding='utf-8') as f:
    json.dump({'N': 1000, 'UR_TH': UR_TH, 'FP': fp, 'avg_min_UR': float(np.mean(ur_mins)), 'time': dt}, f)
