"""从 git log 提取任务记录，构建知识层数据

功能：
  1. 解析 git log 的 commit message
  2. 按前缀分类任务类型（实验/修复/CI/文档/功能/重构）
  3. TF-IDF 向量化
  4. K-Means 聚类
  5. 存入 SQLite（兼容 agent_learning.py 的 task_history schema）

用法：
  python -X utf8 agent_system/extract_git_tasks.py
  python -X utf8 agent_system/extract_git_tasks.py --clusters 8
"""

import math
import os
import re
import sqlite3
import subprocess
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'git_task_knowledge.db')


# ── 1. 解析 git log ──


def parse_git_log(repo_root: str) -> List[Dict]:
    """从 git log 提取 commit 信息"""
    result = subprocess.run(
        ['git', 'log', '--format=%H|%s|%ai|%an'],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding='utf-8',
    )
    commits = []
    for line in result.stdout.strip().split('\n'):
        if not line or '|' not in line:
            continue
        parts = line.split('|', 3)
        if len(parts) < 4:
            continue
        sha, message, date, author = parts
        commits.append(
            {
                'sha': sha.strip(),
                'message': message.strip(),
                'date': date.strip(),
                'author': author.strip(),
            }
        )
    return commits


# ── 2. 任务分类 ──

TASK_PATTERNS = {
    'experiment': [
        r'实验',
        r'experiment',
        r'bench',
        r'评测',
        r'验证',
        r'ROC',
        r'消融',
        r'基线',
        r'FP=',
        r'TPR',
        r'prompt',
        r'UR',
        r'退化',
        r'盲评',
    ],
    'bug_fix': [
        r'修复',
        r'fix',
        r'bug',
        r'错误',
        r'报错',
        r'崩溃',
        r'死循环',
        r'清零',
        r'误提交',
        r'拼写',
        r'路径修复',
        r'全修',
        r'修正',
    ],
    'ci': [
        r'CI',
        r'ruff',
        r'mypy',
        r'coverage',
        r'pytest',
        r'preflight',
        r'格式化',
        r'format',
        r'lint',
        r'check',
    ],
    'docs': [
        r'文档',
        r'docs?',
        r'README',
        r'CHANGELOG',
        r'报告',
        r'手册',
        r'叙述',
        r'标题',
        r'版本号',
        r'目录树',
        r'归档',
    ],
    'feature': [
        r'新增',
        r'feature',
        r'功能',
        r'Phase',
        r'SIMD',
        r'AVX',
        r'GEMM',
        r'Transformer',
        r'LayerNorm',
        r'GELU',
        r'Softmax',
        r'Agent',
        r'第\d层',
        r'Layer',
        r'闭环',
        r'自举',
        r'汇编',
        r'VM',
        r'LLM',
        r'进化',
        r'知识',
        r'策略',
        r'sanyanc',
        r'Level\s*\d',
        r'解析',
        r'实现',
        r'支持',
        r'直连',
        r'优化',
        r'CLI',
        r'提示词',
        r'经验库',
        r'反馈回路',
        r'hypothesis',
        r'生成器',
        r'JSON',
        r'pipe',
        r'opcode',
        r'hash',
        r'哈希',
        r'字典',
    ],
    'refactor': [
        r'refactor',
        r'重构',
        r'整合',
        r'移动',
        r'清理',
        r'重写',
        r'下放',
        r'同步',
        r'统一',
        r'精简',
    ],
}


def classify_commit(message: str) -> str:
    """根据 commit message 前缀和关键词分类任务类型"""
    # 优先检查前缀
    prefix_map = {
        '实验:': 'experiment',
        'bench': 'experiment',
        '修复:': 'bug_fix',
        'fix:': 'bug_fix',
        'CI': 'ci',
        'ruff': 'ci',
        'mypy': 'ci',
        '文档:': 'docs',
        'docs:': 'docs',
        '报告:': 'docs',
        'CHANGELOG': 'docs',
        # '本地保存:' 不用前缀匹配，交给关键词分类
        'chore:': 'refactor',
        'refactor:': 'refactor',
    }
    for prefix, task_type in prefix_map.items():
        if message.startswith(prefix):
            return task_type

    # 关键词匹配，计分取最高
    scores: Dict[str, int] = defaultdict(int)
    for task_type, patterns in TASK_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, message, re.IGNORECASE):
                scores[task_type] += 1

    if scores:
        return max(scores, key=scores.get)  # type: ignore[arg-type]
    return 'other'


# ── 3. TF-IDF 向量化 ──

# 中文停用词
STOP_WORDS = set('的了是在不有也我他她它这那个们就都而且但是如果因为所以可以已经'.split())


def tokenize(text: str) -> List[str]:
    """简单分词：中文按字/词切分，英文按空格"""
    # 英文单词
    en_words = re.findall(r'[a-zA-Z_]\w+', text.lower())
    # 中文：按 2-gram + 3-gram 切分
    cn_chars = re.findall(r'[\u4e00-\u9fff]', text)
    cn_bigrams = [cn_chars[i] + cn_chars[i + 1] for i in range(len(cn_chars) - 1)]
    cn_trigrams = [cn_chars[i] + cn_chars[i + 1] + cn_chars[i + 2] for i in range(len(cn_chars) - 2)]
    # 单字也保留（覆盖短词）
    cn_unigrams = list(cn_chars)
    all_tokens = en_words + cn_trigrams + cn_bigrams + cn_unigrams
    return [t for t in all_tokens if t not in STOP_WORDS and len(t) > 1]


def build_tfidf(docs: List[List[str]]) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
    """构建 TF-IDF 向量"""
    # 文档频率
    df: Dict[str, int] = Counter()
    for doc in docs:
        unique = set(doc)
        for token in unique:
            df[token] += 1

    n = len(docs)
    idf = {token: math.log(n / (count + 1)) + 1 for token, count in df.items()}

    tfidf_vectors = []
    for doc in docs:
        tf = Counter(doc)
        total = len(doc) if doc else 1
        vector = {}
        for token, count in tf.items():
            vector[token] = (count / total) * idf.get(token, 1.0)
        tfidf_vectors.append(vector)

    return tfidf_vectors, idf


def cosine_sim(a: Dict[str, float], b: Dict[str, float]) -> float:
    """余弦相似度"""
    keys = set(a.keys()) & set(b.keys())
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── 4. K-Means 聚类 ──


def kmeans(vectors: List[Dict[str, float]], k: int, max_iter: int = 50) -> List[int]:
    """简易 K-Means（基于余弦相似度）"""
    import random

    n = len(vectors)
    if n <= k:
        return list(range(n))

    # 随机初始化质心
    indices = random.sample(range(n), k)
    centroids = [vectors[i].copy() for i in indices]
    labels = [0] * n

    for _ in range(max_iter):
        # 分配
        changed = False
        for i, vec in enumerate(vectors):
            best_cluster = 0
            best_sim = -1.0
            for c_idx, centroid in enumerate(centroids):
                sim = cosine_sim(vec, centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_cluster = c_idx
            if labels[i] != best_cluster:
                labels[i] = best_cluster
                changed = True

        if not changed:
            break

        # 更新质心（取簇内平均）
        for c_idx in range(k):
            members = [vectors[i] for i in range(n) if labels[i] == c_idx]
            if not members:
                continue
            new_centroid: Dict[str, float] = Counter()
            for vec in members:
                for token, val in vec.items():
                    new_centroid[token] += val
            count = len(members)
            centroids[c_idx] = {k: v / count for k, v in new_centroid.items()}

    return labels


# ── 5. 存入 SQLite ──


def init_db(db_path: str) -> sqlite3.Connection:
    """初始化数据库，兼容 agent_learning.py schema"""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS task_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT,
            task_type TEXT,
            tool_chain TEXT,
            success INTEGER DEFAULT 1,
            duration REAL DEFAULT 0,
            created_at REAL,
            cluster_id INTEGER,
            sha TEXT,
            date TEXT,
            author TEXT
        );
        CREATE TABLE IF NOT EXISTS task_clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER,
            label TEXT,
            size INTEGER,
            top_keywords TEXT,
            task_types TEXT,
            created_at REAL
        );
        CREATE TABLE IF NOT EXISTS task_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            token TEXT,
            tfidf_score REAL,
            FOREIGN KEY (task_id) REFERENCES task_history(id)
        );
    """)
    conn.commit()
    return conn


def store_tasks(
    conn: sqlite3.Connection,
    commits: List[Dict],
    labels: List[int],
    tfidf_vectors: List[Dict[str, float]],
    task_types: List[str],
):
    """存入数据库"""
    import time

    now = time.time()

    # 清空旧数据
    conn.execute('DELETE FROM task_history')
    conn.execute('DELETE FROM task_clusters')
    conn.execute('DELETE FROM task_embeddings')

    # 存任务记录
    for i, commit in enumerate(commits):
        cursor = conn.execute(
            """INSERT INTO task_history
               (task, task_type, tool_chain, success, duration, created_at, cluster_id, sha, date, author)
               VALUES (?, ?, ?, 1, 0, ?, ?, ?, ?, ?)""",
            (
                commit['message'],
                task_types[i],
                '',  # tool_chain 从 commit 无法提取
                now,
                labels[i],
                commit['sha'][:8],
                commit['date'],
                commit['author'],
            ),
        )
        task_id = cursor.lastrowid

        # 存 embedding（取 top-10 关键词）
        top_tokens = sorted(tfidf_vectors[i].items(), key=lambda x: x[1], reverse=True)[:10]
        for token, score in top_tokens:
            conn.execute(
                'INSERT INTO task_embeddings (task_id, token, tfidf_score) VALUES (?, ?, ?)',
                (task_id, token, score),
            )

    # 存聚类摘要
    n_clusters = max(labels) + 1
    for c in range(n_clusters):
        members = [i for i, lbl in enumerate(labels) if lbl == c]
        if not members:
            continue
        # 聚类关键词：合并簇内所有 token，按总 TF-IDF 排序
        cluster_tokens: Counter = Counter()
        for idx in members:
            for token, score in tfidf_vectors[idx].items():
                cluster_tokens[token] += score
        top_keywords = [t for t, _ in cluster_tokens.most_common(10)]

        # 任务类型分布
        type_dist = Counter(task_types[i] for i in members)
        type_str = ', '.join(f'{t}:{n}' for t, n in type_dist.most_common())

        conn.execute(
            """INSERT INTO task_clusters
               (cluster_id, label, size, top_keywords, task_types, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (c, f'cluster_{c}', len(members), '|'.join(top_keywords), type_str, now),
        )

    conn.commit()


# ── 6. 主流程 ──


def main():
    import argparse

    parser = argparse.ArgumentParser(description='从 git log 提取任务记录')
    parser.add_argument('--clusters', type=int, default=6, help='聚类数量（默认6）')
    parser.add_argument('--db', type=str, default=DB_PATH, help='输出数据库路径')
    args = parser.parse_args()

    print('=== 从 git log 提取任务记录 ===\n')

    # 1. 解析
    commits = parse_git_log(ROOT)
    print(f'解析到 {len(commits)} 条 commit')

    # 2. 分类
    task_types = [classify_commit(c['message']) for c in commits]
    type_dist = Counter(task_types)
    print('\n任务类型分布：')
    for t, count in type_dist.most_common():
        print(f'  {t}: {count} ({count * 100 / len(commits):.1f}%)')

    # 3. 向量化
    tokens_list = [tokenize(c['message']) for c in commits]
    tfidf_vectors, idf = build_tfidf(tokens_list)
    print(f'\nTF-IDF 词汇量: {len(idf)}')

    # 4. 聚类
    labels = kmeans(tfidf_vectors, args.clusters)
    print(f'\n聚类结果（{args.clusters} 簇）：')
    for c in range(args.clusters):
        members = [i for i, lbl in enumerate(labels) if lbl == c]
        type_in_cluster = Counter(task_types[i] for i in members)
        top_types = ', '.join(f'{t}({n})' for t, n in type_in_cluster.most_common(3))
        # 取代表 commit
        representative = commits[members[0]]['message'][:40] if members else ''
        print(f'  簇 {c}: {len(members)} 条 | {top_types} | 例: {representative}')

    # 5. 存入数据库
    conn = init_db(args.db)
    store_tasks(conn, commits, labels, tfidf_vectors, task_types)
    conn.close()
    print(f'\n已存入: {args.db}')
    print(f'  task_history: {len(commits)} 条')
    print(f'  task_clusters: {args.clusters} 簇')
    print('  task_embeddings: top-10 关键词/条')


if __name__ == '__main__':
    main()
