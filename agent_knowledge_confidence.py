"""Knowledge Confidence + Task Type 细化

核心目标：
1. Knowledge Confidence — 防止把偶然当规律
2. Task Type 细化 — 发现子聚类

组件：
  P73: KnowledgeConfidence — 知识置信度计算
  P74: SubClusterDiscovery — 子聚类发现
  P75: ConfidenceAwareKnowledge — 带置信度的知识库
"""

import json
import math
import os
import sqlite3
import statistics
import time
from typing import Dict, List

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Knowledge Confidence ──


class KnowledgeConfidence:
    """知识置信度计算"""

    def __init__(self):
        pass

    def calculate(self, n_samples: int, success_rate: float, consistency: float = 1.0) -> float:
        """计算知识置信度

        Args:
            n_samples: 样本数
            success_rate: 成功率
            consistency: 一致性（成功率的标准差越小，一致性越高）

        Returns:
            置信度 0-1
        """
        # 样本数因子：样本越多，置信度越高（对数增长）
        sample_factor = min(1.0, math.log(n_samples + 1) / math.log(100))

        # 成功率因子：成功率越接近0.5，置信度越低（二选一随机也能50%）
        # 成功率越极端（接近0或1），置信度越高
        sr_factor = 2 * abs(success_rate - 0.5)

        # 一致性因子：标准差越小，一致性越高
        consistency_factor = max(0, 1.0 - consistency * 2)

        # 综合置信度
        confidence = sample_factor * 0.4 + sr_factor * 0.3 + consistency_factor * 0.3

        return max(0.0, min(1.0, confidence))

    def interpret(self, confidence: float) -> str:
        """解释置信度"""
        if confidence >= 0.9:
            return '高置信度（可信赖）'
        elif confidence >= 0.7:
            return '中等置信度（基本可信）'
        elif confidence >= 0.5:
            return '低置信度（需要更多数据）'
        else:
            return '极低置信度（不可信赖）'


# ── Sub-Cluster Discovery ──


class SubClusterDiscovery:
    """子聚类发现：发现任务类型内的子模式"""

    def __init__(self):
        self.embedder = self._create_embedder()

    def _create_embedder(self):
        """创建嵌入器"""
        try:
            from agent_knowledge import TaskEmbedding

            return TaskEmbedding()
        except Exception:
            return None

    def discover_subclusters(self, tasks: List[Dict], n_subclusters: int = 3) -> Dict:
        """发现子聚类"""
        if not tasks:
            return {'subclusters': [], 'centers': []}

        # 提取特征
        features = []
        for task in tasks:
            if self.embedder:
                emb = self.embedder.embed(task.get('text', ''))
            else:
                # 简单特征：长度 + 关键词
                text = task.get('text', '')
                emb = [len(text) / 100, text.count('优化') / 10, text.count('修复') / 10]
            features.append(emb)

        # 简单聚类：K-means变体
        if len(features) < n_subclusters:
            n_subclusters = max(1, len(features))

        # 初始化聚类中心
        centers = [features[i * len(features) // n_subclusters] for i in range(n_subclusters)]

        # 迭代分配
        assignments = [0] * len(features)
        for _ in range(10):  # 10次迭代
            # 分配到最近中心
            for i, feat in enumerate(features):
                min_dist = float('inf')
                min_cluster = 0
                for j, center in enumerate(centers):
                    dist = sum((a - b) ** 2 for a, b in zip(feat, center)) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        min_cluster = j
                assignments[i] = min_cluster

            # 更新中心
            for j in range(n_subclusters):
                cluster_features = [features[i] for i in range(len(features)) if assignments[i] == j]
                if cluster_features:
                    dim = len(cluster_features[0])
                    centers[j] = [sum(f[d] for f in cluster_features) / len(cluster_features) for d in range(dim)]

        # 分析子聚类
        subclusters = []
        for j in range(n_subclusters):
            cluster_tasks = [tasks[i] for i in range(len(tasks)) if assignments[i] == j]
            if cluster_tasks:
                # 找中心任务（最接近聚类中心的）
                center_task = min(
                    cluster_tasks,
                    key=lambda t: self._distance(
                        self.embedder.embed(t.get('text', '')) if self.embedder else [0], centers[j]
                    ),
                )
                subclusters.append(
                    {
                        'id': j,
                        'size': len(cluster_tasks),
                        'center_task': center_task.get('text', '')[:50],
                        'tasks': [t.get('text', '')[:30] for t in cluster_tasks[:5]],
                    }
                )

        return {
            'subclusters': subclusters,
            'n_clusters': n_subclusters,
        }

    def _distance(self, a: List[float], b: List[float]) -> float:
        """计算距离"""
        if not a or not b or len(a) != len(b):
            return float('inf')
        return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


# ── Confidence-Aware Knowledge ──


class ConfidenceAwareKnowledge:
    """带置信度的知识库"""

    DB_PATH = os.path.join(ROOT, 'agent_knowledge_confidence.db')

    def __init__(self):
        self.confidence_calc = KnowledgeConfidence()
        self.subcluster = SubClusterDiscovery()
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT,
                sub_type TEXT,
                config_snapshot TEXT,
                n_samples INTEGER,
                success_rate REAL,
                consistency REAL,
                confidence REAL,
                created_at REAL,
                last_updated REAL
            );
        """)
        conn.commit()
        conn.close()

    def record_knowledge(
        self, task_type: str, sub_type: str, config: Dict, n_samples: int, success_rate: float, consistency: float = 0.1
    ):
        """记录知识"""
        confidence = self.confidence_calc.calculate(n_samples, success_rate, consistency)
        config_key = json.dumps(config, sort_keys=True)

        conn = sqlite3.connect(self.DB_PATH)
        existing = conn.execute(
            'SELECT id FROM knowledge_entries WHERE task_type=? AND sub_type=? AND config_snapshot=?',
            (task_type, sub_type, config_key),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE knowledge_entries
                SET n_samples=?, success_rate=?, consistency=?, confidence=?, last_updated=?
                WHERE id=?
            """,
                (n_samples, success_rate, consistency, confidence, time.time(), existing[0]),
            )
        else:
            conn.execute(
                """
                INSERT INTO knowledge_entries
                (task_type, sub_type, config_snapshot, n_samples, success_rate, consistency, confidence, created_at, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task_type,
                    sub_type,
                    config_key,
                    n_samples,
                    success_rate,
                    consistency,
                    confidence,
                    time.time(),
                    time.time(),
                ),
            )

        conn.commit()
        conn.close()

    def get_knowledge(self, task_type: str, min_confidence: float = 0.5) -> List[Dict]:
        """获取置信度足够的知识"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute(
            """
            SELECT sub_type, config_snapshot, n_samples, success_rate, confidence
            FROM knowledge_entries
            WHERE task_type=? AND confidence>=?
            ORDER BY confidence DESC
        """,
            (task_type, min_confidence),
        ).fetchall()
        conn.close()

        return [
            {
                'sub_type': r[0],
                'config': json.loads(r[1]),
                'n_samples': r[2],
                'success_rate': r[3],
                'confidence': r[4],
            }
            for r in rows
        ]

    def get_all_stats(self) -> Dict:
        """获取所有统计"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute("""
            SELECT task_type, COUNT(*), AVG(confidence), SUM(n_samples)
            FROM knowledge_entries
            GROUP BY task_type
        """).fetchall()
        conn.close()

        return {
            r[0]: {
                'entries': r[1],
                'avg_confidence': r[2] or 0,
                'total_samples': r[3] or 0,
            }
            for r in rows
        }

    def summary(self) -> str:
        stats = self.get_all_stats()
        lines = ['Knowledge Confidence:']
        for task_type, s in stats.items():
            interp = self.confidence_calc.interpret(s['avg_confidence'])
            lines.append(f'  {task_type}: {s["entries"]}条, 置信度={s["avg_confidence"]:.2f} ({interp})')
        return '\n'.join(lines) if lines else '  (无数据)'


# ── 整合 ──


class KnowledgeConfidenceSystem:
    """Knowledge Confidence 系统"""

    def __init__(self):
        self.confidence_calc = KnowledgeConfidence()
        self.subcluster = SubClusterDiscovery()
        self.knowledge = ConfidenceAwareKnowledge()

    def build_knowledge_base(self, tasks: List[Dict], configs: List[Dict], results: List[Dict]) -> Dict:
        """构建带置信度的知识库"""
        print(f'\n═══ 构建知识库 ({len(tasks)}任务) ═══')

        # 按任务类型分组
        by_type: Dict[str, List[Dict]] = {}
        for task, config, result in zip(tasks, configs, results):
            task_type = task.get('type', 'unknown')
            if task_type not in by_type:
                by_type[task_type] = []
            by_type[task_type].append(
                {
                    'task': task,
                    'config': config,
                    'result': result,
                }
            )

        # 为每种任务类型计算置信度
        knowledge_stats = {}
        for task_type, entries in by_type.items():
            success_rates = [e['result'].get('success_rate', 0) for e in entries]
            n_samples = len(entries)

            if success_rates:
                avg_sr = statistics.mean(success_rates)
                consistency = statistics.stdev(success_rates) if len(success_rates) > 1 else 0.1
                confidence = self.confidence_calc.calculate(n_samples, avg_sr, consistency)
            else:
                avg_sr = 0
                consistency = 1
                confidence = 0

            # 记录知识
            self.knowledge.record_knowledge(task_type, 'default', {}, n_samples, avg_sr, consistency)

            knowledge_stats[task_type] = {
                'n_samples': n_samples,
                'avg_success_rate': avg_sr,
                'consistency': consistency,
                'confidence': confidence,
                'interpretation': self.confidence_calc.interpret(confidence),
            }

            print(f'  {task_type}: {n_samples}样本, SR={avg_sr:.1%}, 置信度={confidence:.2f}')

        return knowledge_stats

    def discover_subclusters(self, tasks: List[Dict]) -> Dict:
        """发现子聚类"""
        print('\n═══ 发现子聚类 ═══')

        # 按任务类型分组
        by_type: Dict[str, List[Dict]] = {}
        for task in tasks:
            task_type = task.get('type', 'unknown')
            if task_type not in by_type:
                by_type[task_type] = []
            by_type[task_type].append(task)

        results = {}
        for task_type, type_tasks in by_type.items():
            if len(type_tasks) < 10:
                print(f'  {task_type}: 样本不足({len(type_tasks)}), 跳过')
                continue

            subclusters = self.subcluster.discover_subclusters(type_tasks, n_subclusters=3)
            results[task_type] = subclusters

            print(f'  {task_type}: {subclusters["n_clusters"]}个子聚类')
            for sc in subclusters['subclusters']:
                print(f'    Cluster {sc["id"]}: {sc["size"]}个任务, 中心="{sc["center_task"]}"')

        return results

    def print_report(self, knowledge_stats: Dict, subclusters: Dict):
        """打印报告"""
        print('\n' + '=' * 60)
        print('  Knowledge Confidence 报告')
        print('=' * 60)

        print('\n知识置信度:')
        for task_type, stats in knowledge_stats.items():
            print(f'  {task_type}:')
            print(f'    样本数: {stats["n_samples"]}')
            print(f'    成功率: {stats["avg_success_rate"]:.1%}')
            print(f'    一致性: {stats["consistency"]:.2f}')
            print(f'    置信度: {stats["confidence"]:.2f} ({stats["interpretation"]})')

        print('\n子聚类发现:')
        for task_type, sc in subclusters.items():
            print(f'  {task_type}: {sc["n_clusters"]}个子聚类')
            for cluster in sc['subclusters']:
                print(f'    Cluster {cluster["id"]}: {cluster["size"]}个任务')

        # 结论
        print('\n结论:')
        high_conf = sum(1 for s in knowledge_stats.values() if s['confidence'] >= 0.7)
        low_conf = sum(1 for s in knowledge_stats.values() if s['confidence'] < 0.5)
        print(f'  高置信度知识: {high_conf}/{len(knowledge_stats)}')
        print(f'  低置信度知识: {low_conf}/{len(knowledge_stats)}')
        if low_conf > 0:
            print('  ⚠ 需要更多样本来提升低置信度知识')
