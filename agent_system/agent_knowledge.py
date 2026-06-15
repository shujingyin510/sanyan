"""Knowledge Validation — 从规则分类到学习分类

组件：
  P69: TaskEmbedding — 任务向量化
  P70: TaskSimilarity — 任务相似度计算
  P71: ClusterLearning — 自动聚类学习任务距离
  P72: KnowledgeValidator — 知识验证器
"""

import json
import math
import os
import sqlite3
import time
from typing import Dict, List, Optional, Tuple, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Task Embedding ──


class TaskEmbedding:
    """任务向量化：将任务文本转换为数值向量"""

    # 特征词典（手动定义，未来可学习）
    FEATURE_WORDS = {
        # bug_fix
        'fix': 0,
        'bug': 0,
        'error': 0,
        '修复': 0,
        '错误': 0,
        '报错': 0,
        # refactor
        'refactor': 1,
        '重构': 1,
        '优化': 1,
        '整理': 1,
        '简化': 1,
        # performance
        'performance': 2,
        '性能': 2,
        '加速': 2,
        '瓶颈': 2,
        '慢': 2,
        # feature
        'feature': 3,
        '新增': 3,
        '添加': 3,
        '实现': 3,
        '功能': 3,
        # analysis
        'analysis': 4,
        '分析': 4,
        '查看': 4,
        '理解': 4,
        '搜索': 4,
        # test
        'test': 5,
        '测试': 5,
        '验证': 5,
        '检查': 5,
        'lint': 5,
        # documentation
        'doc': 6,
        '文档': 6,
        '注释': 6,
        '说明': 6,
        'README': 6,
        # complexity
        'simple': 7,
        '简单': 7,
        'quick': 7,
        'complex': 8,
        '复杂': 8,
        'difficult': 8,
        # scope
        'file': 9,
        '文件': 9,
        'module': 9,
        '模块': 9,
        'project': 10,
        '项目': 10,
        'system': 10,
    }

    def embed(self, task: str) -> List[float]:
        """将任务转换为向量"""
        task_lower = task.lower()
        vector = [0.0] * 12  # 12维特征

        for word, idx in self.FEATURE_WORDS.items():
            if word in task_lower:
                vector[idx] = 1.0

        # 额外特征：长度
        vector.append(min(1.0, len(task) / 100))

        return vector

    def batch_embed(self, tasks: List[str]) -> List[List[float]]:
        """批量向量化"""
        return [self.embed(t) for t in tasks]


# ── Task Similarity ──


class TaskSimilarity:
    """任务相似度计算"""

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """余弦相似度"""
        if not a or not b or len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    @staticmethod
    def euclidean_distance(a: List[float], b: List[float]) -> float:
        """欧氏距离"""
        if not a or not b or len(a) != len(b):
            return float('inf')

        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    @staticmethod
    def manhattan_distance(a: List[float], b: List[float]) -> float:
        """曼哈顿距离"""
        if not a or not b or len(a) != len(b):
            return float('inf')

        return sum(abs(x - y) for x, y in zip(a, b))

    def find_similar(
        self, query: List[float], candidates: List[Tuple[str, List[float]]], top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """查找最相似的任务"""
        scored = []
        for name, vec in candidates:
            sim = self.cosine_similarity(query, vec)
            scored.append((name, sim))

        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]


# ── Cluster Learning ──


class ClusterLearning:
    """自动聚类学习任务距离"""

    DB_PATH = os.path.join(ROOT, 'agent_task_clusters.db')

    def __init__(self, n_clusters: int = 7):
        self.n_clusters = n_clusters
        self.embedder = TaskEmbedding()
        self.similarity = TaskSimilarity()
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_id INTEGER,
                task_text TEXT,
                task_type TEXT,
                embedding TEXT,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS cluster_centers (
                cluster_id INTEGER PRIMARY KEY,
                center_embedding TEXT,
                task_type TEXT,
                sample_count INTEGER,
                last_updated REAL
            );
        """)
        conn.commit()
        conn.close()

    def add_task(self, task: str, task_type: str):
        """添加任务到聚类"""
        embedding = self.embedder.embed(task)

        conn = sqlite3.connect(self.DB_PATH)

        # 找最近的聚类中心
        cluster_id = self._find_nearest_cluster(embedding, conn)

        # 如果没有聚类中心，创建新的
        if cluster_id is None:
            cluster_id = self._create_cluster(task_type, embedding, conn)

        # 添加任务
        conn.execute(
            """
            INSERT INTO task_clusters (cluster_id, task_text, task_type, embedding, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (cluster_id, task[:500], task_type, json.dumps(embedding), time.time()),
        )

        # 更新聚类中心
        self._update_cluster_center(cluster_id, conn)

        conn.commit()
        conn.close()

    def _find_nearest_cluster(self, embedding: List[float], conn) -> Optional[int]:
        """找最近的聚类中心"""
        rows = conn.execute('SELECT cluster_id, center_embedding FROM cluster_centers').fetchall()

        if not rows:
            return None

        best_cluster = None
        best_distance = float('inf')

        for cluster_id, center_json in rows:
            center = json.loads(center_json)
            dist = self.similarity.euclidean_distance(embedding, center)
            if dist < best_distance:
                best_distance = dist
                best_cluster = cluster_id

        # 如果最近距离太远，创建新聚类
        if best_distance > 2.0:
            return None

        return best_cluster

    def _create_cluster(self, task_type: str, embedding: List[float], conn) -> int:
        """创建新聚类"""
        # 找最大的cluster_id
        row = conn.execute('SELECT MAX(cluster_id) FROM cluster_centers').fetchone()
        new_id = (row[0] or 0) + 1

        conn.execute(
            """
            INSERT INTO cluster_centers (cluster_id, center_embedding, task_type, sample_count, last_updated)
            VALUES (?, ?, ?, 1, ?)
        """,
            (new_id, json.dumps(embedding), task_type, time.time()),
        )

        return new_id

    def _update_cluster_center(self, cluster_id: int, conn):
        """更新聚类中心（均值）"""
        rows = conn.execute('SELECT embedding FROM task_clusters WHERE cluster_id=?', (cluster_id,)).fetchall()

        if not rows:
            return

        # 计算均值
        embeddings = [json.loads(r[0]) for r in rows]
        n = len(embeddings)
        dim = len(embeddings[0]) if embeddings else 12

        center = [0.0] * dim
        for emb in embeddings:
            for i in range(min(dim, len(emb))):
                center[i] += emb[i]
        center = [x / n for x in center]

        # 更新
        conn.execute(
            """
            UPDATE cluster_centers
            SET center_embedding=?, sample_count=?, last_updated=?
            WHERE cluster_id=?
        """,
            (json.dumps(center), n, time.time(), cluster_id),
        )

    def predict(self, task: str) -> Dict:
        """预测任务类型"""
        embedding = self.embedder.embed(task)

        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute('SELECT cluster_id, center_embedding, task_type FROM cluster_centers').fetchall()
        conn.close()

        if not rows:
            return {'type': 'unknown', 'confidence': 0.0}

        best_cluster = None
        best_distance = float('inf')
        best_type = 'unknown'

        for cluster_id, center_json, task_type in rows:
            center = json.loads(center_json)
            dist = self.similarity.euclidean_distance(embedding, center)
            if dist < best_distance:
                best_distance = dist
                best_cluster = cluster_id
                best_type = task_type

        # 置信度：距离越近越确定
        confidence = max(0.0, 1.0 - best_distance / 3.0)

        return {
            'type': best_type,
            'cluster_id': best_cluster,
            'confidence': confidence,
            'distance': best_distance,
        }

    def get_clusters(self) -> List[Dict]:
        """获取所有聚类"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute("""
            SELECT cluster_id, task_type, sample_count, last_updated
            FROM cluster_centers
            ORDER BY sample_count DESC
        """).fetchall()
        conn.close()

        return [
            {
                'cluster_id': r[0],
                'task_type': r[1],
                'sample_count': r[2],
                'last_updated': r[3],
            }
            for r in rows
        ]

    def summary(self) -> str:
        clusters = self.get_clusters()
        total_samples = sum(c['sample_count'] for c in clusters)
        lines = [
            f'Cluster Learning: {len(clusters)}个聚类, {total_samples}个样本',
        ]
        for c in clusters[:5]:
            lines.append(f'  Cluster {c["cluster_id"]}: {c["task_type"]} ({c["sample_count"]}个)')
        return '\n'.join(lines)


# ── Knowledge Validator ──


class KnowledgeValidator:
    """知识验证器：验证分类质量"""

    def __init__(self):
        self.embedder = TaskEmbedding()
        self.similarity = TaskSimilarity()

    def validate_classification(self, tasks: List[Dict], true_labels: List[str]) -> Dict:
        """验证分类质量"""
        # 用规则分类
        from agent_system.agent_task_taxonomy import TaskClassifier

        classifier = TaskClassifier()

        correct = 0
        total = len(tasks)
        confusion = {}

        for task_info, true_label in zip(tasks, true_labels):
            task = task_info.get('task', '')
            predicted = classifier.classify(task)['type']

            if predicted == true_label:
                correct += 1
            else:
                key = f'{true_label}→{predicted}'
                confusion[key] = confusion.get(key, 0) + 1

        accuracy = correct / max(total, 1)

        return {
            'total': total,
            'correct': correct,
            'accuracy': accuracy,
            'confusion': confusion,
        }

    def find_misclassifications(self, tasks: List[Dict], true_labels: List[str], threshold: float = 0.5) -> List[Dict]:
        """找到可能的误分类"""
        from agent_system.agent_task_taxonomy import TaskClassifier

        classifier = TaskClassifier()

        misclassifications = []

        for task_info, true_label in zip(tasks, true_labels):
            task = task_info.get('task', '')
            result = classifier.classify(task)

            if result['type'] != true_label and result['confidence'] < threshold:
                misclassifications.append(
                    {
                        'task': task[:50],
                        'predicted': result['type'],
                        'true': true_label,
                        'confidence': result['confidence'],
                    }
                )

        return misclassifications


# ── 整合 ──


class KnowledgeValidationSystem:
    """Knowledge Validation 系统"""

    def __init__(self):
        self.embedder = TaskEmbedding()
        self.similarity = TaskSimilarity()
        self.cluster = ClusterLearning()
        self.validator = KnowledgeValidator()

    def run_validation(self, n_tasks: int = 100) -> Dict:
        """运行知识验证"""
        print(f'\n═══ Knowledge Validation ({n_tasks}任务) ═══')

        # 生成测试数据
        import random

        random.seed(42)

        task_templates = [
            ('修复{file}中的bug', 'bug_fix'),
            ('重构{file}代码', 'refactor'),
            ('优化{file}性能', 'performance'),
            ('新增{feature}功能', 'feature'),
            ('分析{file}结构', 'analysis'),
            ('给{file}添加测试', 'test'),
            ('更新{file}文档', 'documentation'),
        ]

        files = ['vm.py', 'evaluator.py', 'parser.py', 'runtime.py']
        features = ['日志', '缓存', '并行', '流式']

        tasks = []
        true_labels = []

        for i in range(n_tasks):
            template, label = random.choice(task_templates)
            file = random.choice(files)
            feature = random.choice(features)
            task = template.format(file=file, feature=feature)
            tasks.append({'task': task})
            true_labels.append(label)

        # 1. 验证规则分类
        print('\n[1/2] 验证规则分类...')
        rule_result = self.validator.validate_classification(tasks, true_labels)
        print(f'  准确率: {rule_result["accuracy"]:.1%}')
        print(f'  误分类: {len(rule_result["confusion"])}种')

        # 2. 添加到聚类
        print('\n[2/2] 训练聚类...')
        for task_info, label in zip(tasks[:50], true_labels[:50]):
            self.cluster.add_task(task_info['task'], label)

        # 3. 用聚类预测
        print('\n聚类预测测试:')
        test_tasks = [
            '修复evaluator.py的bug',
            '重构vm.py代码',
            '优化parser.py性能',
        ]

        for task in test_tasks:
            result = self.cluster.predict(task)
            print(f'  {task[:30]:30s} → {result["type"]:15s} (置信度: {result["confidence"]:.2f})')

        return {
            'rule_accuracy': rule_result['accuracy'],
            'clusters': len(self.cluster.get_clusters()),
            'misclassifications': rule_result['confusion'],
        }

    def summary(self) -> str:
        return f'Knowledge Validation:\n{self.cluster.summary()}'
