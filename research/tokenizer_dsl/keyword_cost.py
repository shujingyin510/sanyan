"""Keyword token cost: 60 Chinese keywords across 4 tokenizers + ASCII distribution chart."""

import tiktoken
from transformers import AutoTokenizer

encoders = {
    'GPT-2': tiktoken.get_encoding('gpt2'),
    'Qwen': AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B', local_files_only=True),
    'OPT': AutoTokenizer.from_pretrained('facebook/opt-125m', local_files_only=True),
    'Pythia': AutoTokenizer.from_pretrained('EleutherAI/pythia-160m', local_files_only=True),
}

keywords = {
    '控制流': ['循环', '如果', '否则', '当', '对于', '在', '直到', '跳出', '继续', '遍历', '步长', '终止'],
    '函数': ['函数', '返回', '调用', '参数', '传入', '输出', '结果', '无', '递归'],
    '类型/数据': ['列表', '字典', '集合', '元组', '字符串', '数字', '整数', '布尔', '空', '真', '假'],
    'OOP': ['类', '对象', '继承', '方法', '属性', '实例', '接口', '抽象'],
    'I/O': ['打印', '读取', '写入', '打开', '关闭', '输入', '文件', '路径'],
    '异常': ['尝试', '捕获', '抛出', '错误', '异常', '最终'],
    '模块': ['导入', '模块', '包', '从', '作为', '使用'],
    '操作': ['映射', '过滤', '排序', '反转', '合并', '拆分', '替换', '查找', '连接', '添加', '删除'],
}

# ── 1. Per-keyword table ──
print('### 中文关键词 Token 开销（4 tokenizer 对比）\n')
print(f'{"类别":<10} {"关键词":<8} {"GPT2":>5} {"Qwen":>5} {"OPT":>5} {"Pyth":>5}')
print('-' * 45)
all_data = []
for cat, words in keywords.items():
    for w in words:
        cost_map = {n: len(enc.encode(w)) for n, enc in encoders.items()}
        all_data.append((cat, w, cost_map))
        g, q, o, p = cost_map['GPT-2'], cost_map['Qwen'], cost_map['OPT'], cost_map['Pythia']
        print(f'{cat:<10} {w:<8} {g:>5} {q:>5} {o:>5} {p:>5}')
    print()

# ── 2. Summary table ──
print('### 汇总\n')
print(f'{"Tokenizer":<12} {"总计 tk":>8} {"平均 tk":>8} {"最多 tk":>8} {"最少 tk":>8} {"词表":>10}')
print('-' * 52)
for n, enc in encoders.items():
    costs = [d[2][n] for d in all_data]
    vocab = getattr(enc, 'vocab_size', getattr(enc, 'n_vocab', '?'))
    print(f'{n:<12} {sum(costs):>8} {sum(costs) / len(costs):>7.1f} {max(costs):>8} {min(costs):>8} {str(vocab):>10}')

# ── 3. ASCII distribution chart ──
print('\n\n### Token Cost Distribution（每个关键词的 token 数分布）\n')
for name in ['GPT-2', 'Qwen', 'OPT', 'Pythia']:
    costs = sorted([d[2][name] for d in all_data])
    dist: dict[int, int] = {}
    for c in costs:
        dist[c] = dist.get(c, 0) + 1
    max_count = max(dist.values())

    print(f'--- {name} (n={len(costs)}) ---')
    print(f'{"tk":>3} {"count":>5}  {"bar"}')
    for c in sorted(dist):
        bar = '█' * (dist[c] * 40 // max_count)
        print(f'{c:>3} {dist[c]:>5}  {bar}')

    # stats
    avg = sum(costs) / len(costs)
    print(f'    avg={avg:.1f}  median={costs[len(costs) // 2]}  max={max(costs)}  min={min(costs)}\n')

# ── 4. Percentage of keywords with single-token encoding ──
print('### 单 Token 关键词占比\n')
for name in ['GPT-2', 'Qwen', 'OPT', 'Pythia']:
    costs = [d[2][name] for d in all_data]
    single = sum(1 for c in costs if c == 1)
    print(f'{name:<12} {single}/{len(costs)} ({single / len(costs):.0%})')
