"""3-part experiment: keyword scaling + cross-language + random text."""

import tiktoken
import random
from transformers import AutoTokenizer

encoders = {
    'GPT-2': tiktoken.get_encoding('gpt2'),
    'Qwen': AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B', local_files_only=True),
    'OPT': AutoTokenizer.from_pretrained('facebook/opt-125m', local_files_only=True),
    'Pythia': AutoTokenizer.from_pretrained('EleutherAI/pythia-160m', local_files_only=True),
}

random.seed(42)

# ══════════════════════════════════════════
# A) Keyword Scaling: 71 → 200 → 500
# ══════════════════════════════════════════

CN_PROG = {
    'control': [
        '循环',
        '如果',
        '否则',
        '当',
        '对于',
        '在',
        '直到',
        '跳出',
        '继续',
        '遍历',
        '步长',
        '终止',
        '条件',
        '判断',
        '分支',
        '选择',
        '执行',
    ],
    'function': [
        '函数',
        '返回',
        '调用',
        '参数',
        '传入',
        '输出',
        '结果',
        '无',
        '递归',
        '闭包',
        '匿名',
        '定义',
        '声明',
        '运行',
    ],
    'data': [
        '列表',
        '字典',
        '集合',
        '元组',
        '字符串',
        '数字',
        '整数',
        '布尔',
        '空',
        '真',
        '假',
        '数组',
        '队列',
        '栈',
        '堆',
        '树',
        '图',
    ],
    'oop': [
        '类',
        '对象',
        '继承',
        '方法',
        '属性',
        '实例',
        '接口',
        '抽象',
        '封装',
        '多态',
        '构造',
        '析构',
        '重载',
        '覆盖',
    ],
    'io': ['打印', '读取', '写入', '打开', '关闭', '输入', '文件', '路径', '流', '缓冲', '编码', '解码', '序列化'],
    'error': ['尝试', '捕获', '抛出', '错误', '异常', '最终', '断言', '日志', '调试', '追踪', '回滚'],
    'module': ['导入', '模块', '包', '从', '作为', '使用', '导出', '依赖', '版本'],
    'operation': [
        '映射',
        '过滤',
        '排序',
        '反转',
        '合并',
        '拆分',
        '替换',
        '查找',
        '连接',
        '添加',
        '删除',
        '新建',
        '创建',
        '修改',
        '查询',
        '计算',
        '长度',
        '索引',
        '范围',
    ],
}

CN_TECH = {
    'ai_ml': [
        '模型',
        '训练',
        '推理',
        '梯度',
        '优化',
        '损失',
        '准确',
        '网络',
        '层',
        '激活',
        '正则',
        '批量',
        '学习',
        '卷积',
        '注意',
        '嵌入',
        '解码',
        '编码',
        '生成',
        '预测',
    ],
    'db': [
        '数据库',
        '查询',
        '索引',
        '事务',
        '锁',
        '表',
        '列',
        '行',
        '主键',
        '外键',
        '视图',
        '存储',
        '缓存',
        '持久',
        '迁移',
    ],
    'web': ['请求', '响应', '路由', '会话', '令牌', '认证', '授权', '中间件', '跨域', '负载', '代理', '端口', '域名'],
    'system': ['线程', '进程', '内存', '磁盘', '网络', '套接字', '信号', '管道', '调度', '上下文', '寄存器', '中断'],
}

CN_DAILY = {
    'general': [
        '今天',
        '明天',
        '昨天',
        '工作',
        '学习',
        '吃饭',
        '睡觉',
        '天气',
        '时间',
        '地点',
        '原因',
        '结果',
        '问题',
        '答案',
        '方法',
        '过程',
        '开始',
        '结束',
        '中间',
        '前后',
        '大小',
        '高低',
        '快慢',
        '好坏',
        '多少',
        '远近',
        '新旧',
        '冷热',
        '轻重',
        '长短',
        '粗细',
        '厚薄',
        '宽窄',
    ],
    'action': [
        '说',
        '看',
        '听',
        '写',
        '读',
        '走',
        '跑',
        '跳',
        '坐',
        '站',
        '买',
        '卖',
        '给',
        '拿',
        '放',
        '推',
        '拉',
        '开',
        '关',
        '用',
    ],
    'object': [
        '电脑',
        '手机',
        '桌子',
        '椅子',
        '窗户',
        '门',
        '灯',
        '书',
        '笔',
        '纸',
        '杯子',
        '碗',
        '鞋子',
        '衣服',
        '帽子',
        '眼镜',
        '钥匙',
        '钱包',
        '钟',
        '表',
    ],
}

# Flatten all
all_cn = []
for group in [CN_PROG, CN_TECH, CN_DAILY]:
    for cat, words in group.items():
        all_cn.extend(words)
all_cn = list(dict.fromkeys(all_cn))  # deduplicate

print('=' * 70)
print('A) 关键词规模扩展实验')
print('=' * 70)

for size in [71, 200, 500]:
    sample = random.sample(all_cn, min(size, len(all_cn)))
    # balance categories
    print(f'\n--- 规模: {size} 个中文关键词 ---')
    print(f'{"":<16} {"GPT-2":>8} {"Qwen":>8} {"OPT":>8} {"Pythia":>8}')
    print('-' * 52)
    totals = {n: 0 for n in encoders}
    single = {n: 0 for n in encoders}
    for w in sample:
        costs = {n: len(enc.encode(w)) for n, enc in encoders.items()}
        for n in encoders:
            totals[n] += costs[n]
            if costs[n] == 1:
                single[n] += 1
    for n in encoders:
        avg = totals[n] / len(sample)
        rate = single[n] / len(sample) * 100
        print(f'{n + "> ":>16} {totals[n]:>8} {avg:>7.1f}avg {rate:>5.0f}% 1tk')

# ══════════════════════════════════════════
# B) Cross-language keywords
# ══════════════════════════════════════════

PY_KW = [
    'def',
    'class',
    'return',
    'if',
    'else',
    'elif',
    'for',
    'while',
    'try',
    'except',
    'finally',
    'import',
    'from',
    'as',
    'with',
    'lambda',
    'yield',
    'raise',
    'assert',
    'pass',
    'break',
    'continue',
    'and',
    'or',
    'not',
    'in',
    'is',
    'None',
    'True',
    'False',
]
JAVA_KW = [
    'public',
    'private',
    'protected',
    'static',
    'void',
    'class',
    'extends',
    'implements',
    'interface',
    'abstract',
    'final',
    'new',
    'return',
    'if',
    'else',
    'for',
    'while',
    'try',
    'catch',
    'finally',
    'throw',
    'throws',
    'import',
    'package',
    'this',
    'super',
    'synchronized',
    'volatile',
    'transient',
    'native',
]

print('\n\n' + '=' * 70)
print('B) 跨语言对照：Python / Java 关键词')
print('=' * 70)

for label, kws in [('Python', PY_KW), ('Java', JAVA_KW)]:
    print(f'\n--- {label} ({len(kws)} keywords) ---')
    print(f'{"Keyword":<16} {"GPT-2":>6} {"Qwen":>6} {"OPT":>6} {"Pythia":>6}')
    print('-' * 42)
    totals = {n: 0 for n in encoders}
    for kw in kws:
        costs = {n: len(enc.encode(' ' + kw)) - 1 for n, enc in encoders.items()}  # subtract leading space
        for n in encoders:
            totals[n] += costs[n]
        print(f'{kw:<16} {costs["GPT-2"]:>6} {costs["Qwen"]:>6} {costs["OPT"]:>6} {costs["Pythia"]:>6}')
    print('-' * 42)
    print(
        f'{"AVERAGE":<16} {totals["GPT-2"] / len(kws):>5.1f}  {totals["Qwen"] / len(kws):>5.1f}  {totals["OPT"] / len(kws):>5.1f}  {totals["Pythia"] / len(kws):>5.1f}'
    )

# ══════════════════════════════════════════
# C) Random Chinese text — rule out bias
# ══════════════════════════════════════════

print('\n\n' + '=' * 70)
print('C) 随机中文文本（排除编程偏差）')
print('=' * 70)

domains = {
    '编程': random.sample(sum(CN_PROG.values(), []), 20),
    'AI/技术': random.sample(sum(CN_TECH.values(), []), 20),
    '日常词汇': random.sample(sum(CN_DAILY.values(), []), 20),
}

for domain, words in domains.items():
    print(f'\n--- {domain} ---')
    totals = {n: 0 for n in encoders}
    single = {n: 0 for n in encoders}
    for w in words:
        costs = {n: len(enc.encode(w)) for n, enc in encoders.items()}
        for n in encoders:
            totals[n] += costs[n]
            if costs[n] == 1:
                single[n] += 1
    for n in encoders:
        avg = totals[n] / len(words)
        print(f'  {n:<8} avg={avg:.1f} tk  {single[n]}/{len(words)} 1tk ({single[n] / len(words):.0%})')

# Overall
print(f'\n{"领域":<12} {"GPT2 avg":>9} {"Qwen avg":>9} {"OPT avg":>9} {"Pythia avg":>9}')
print('-' * 52)
for domain, words in [
    ('编程DSL', all_cn[:71]),
    ('AI/技术', sum(CN_TECH.values(), [])),
    ('日常', sum(CN_DAILY.values(), [])),
]:
    avgs = {}
    for n, enc in encoders.items():
        avgs[n] = sum(len(enc.encode(w)) for w in words) / len(words)
    print(f'{domain:<12} {avgs["GPT-2"]:>8.1f}  {avgs["Qwen"]:>8.1f}  {avgs["OPT"]:>8.1f}  {avgs["Pythia"]:>8.1f}')
