"""模板库管理器 — 预置模板 + LLM 生成缓存

结构：
  agent_system/templates/
  ├── math/           — 数学函数模板
  ├── data_structures/ — 数据结构模板
  ├── algorithms/     — 算法模板
  ├── utils/          — 工具函数模板
  └── cache/          — LLM 生成的缓存（自动生成）

用法：
  mgr = TemplateManager()
  code = mgr.get_code("水仙花数判断", "math_utils.py")  # 预置模板
  code = mgr.get_code("快速排序", "sort.py")  # 缓存或 LLM 生成
"""

import hashlib
import os
import re
import sqlite3
import time
from typing import Callable, Dict, List, Optional


TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
CACHE_DIR = os.path.join(TEMPLATES_DIR, 'cache')
CACHE_DB = os.path.join(CACHE_DIR, 'code_cache.db')


class TemplateManager:
    """模板库管理器"""

    def __init__(self, llm_fn: Optional[Callable] = None):
        self.llm_fn = llm_fn
        self._templates: Dict[str, Dict] = {}
        self._ensure_dirs()
        self._init_cache_db()
        self._load_templates()

    def _ensure_dirs(self):
        """确保目录存在"""
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _init_cache_db(self):
        """初始化缓存数据库"""
        conn = sqlite3.connect(CACHE_DB)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS code_cache (
                task_hash TEXT PRIMARY KEY,
                task TEXT,
                filename TEXT,
                code TEXT,
                source TEXT,
                created_at REAL,
                hit_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def _load_templates(self):
        """从 .py 文件加载模板"""
        for category in ['math', 'data_structures', 'algorithms', 'utils']:
            category_dir = os.path.join(TEMPLATES_DIR, category)
            if not os.path.exists(category_dir):
                continue
            for fname in os.listdir(category_dir):
                if fname.endswith('.py') and not fname.startswith('_'):
                    filepath = os.path.join(category_dir, fname)
                    self._load_template_file(filepath, category)

    def _load_template_file(self, filepath: str, category: str):
        """加载单个模板文件"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析元数据（文件头部的注释）
        meta = self._parse_meta(content)
        name = meta.get('name', os.path.basename(filepath).replace('.py', ''))
        keywords = meta.get('keywords', [name])

        self._templates[name] = {
            'name': name,
            'category': category,
            'keywords': keywords,
            'code': content,
            'filepath': filepath,
        }

    def _parse_meta(self, content: str) -> Dict:
        """解析模板元数据"""
        meta = {}
        lines = content.split('\n')

        for line in lines[:20]:
            line = line.strip()
            if line.startswith('# name:'):
                meta['name'] = line.split(':', 1)[1].strip()
            elif line.startswith('# keywords:'):
                keywords_str = line.split(':', 1)[1].strip()
                meta['keywords'] = [k.strip() for k in keywords_str.split(',')]
            elif line.startswith('#') or line.startswith('"""') or line.startswith("'''"):
                continue
            else:
                break

        return meta

    def _task_hash(self, task: str, filename: str) -> str:
        """生成任务哈希"""
        key = f'{task}|{filename}'
        return hashlib.md5(key.encode('utf-8')).hexdigest()

    def get_code(self, task: str, filename: str) -> Optional[str]:
        """获取代码：预置模板 → 缓存 → LLM 生成"""
        # 1. 查预置模板
        template = self._match_template(task)
        if template:
            return template['code']

        # 2. 查缓存
        cached = self._cache_get(task, filename)
        if cached:
            return cached

        # 3. LLM 生成
        if self.llm_fn:
            code = self._generate_with_llm(task, filename)
            if code:
                self._cache_set(task, filename, code, 'llm')
                return code

        return None

    def _match_template(self, task: str) -> Optional[Dict]:
        """匹配预置模板"""
        task_lower = task.lower()

        for name, template in self._templates.items():
            for keyword in template['keywords']:
                if keyword.lower() in task_lower:
                    return template

        return None

    def _cache_get(self, task: str, filename: str) -> Optional[str]:
        """从缓存获取"""
        task_hash = self._task_hash(task, filename)
        conn = sqlite3.connect(CACHE_DB)
        row = conn.execute('SELECT code, hit_count FROM code_cache WHERE task_hash=?', (task_hash,)).fetchone()
        if row:
            conn.execute('UPDATE code_cache SET hit_count=hit_count+1 WHERE task_hash=?', (task_hash,))
            conn.commit()
            conn.close()
            return row[0]
        conn.close()
        return None

    def _cache_set(self, task: str, filename: str, code: str, source: str):
        """写入缓存"""
        task_hash = self._task_hash(task, filename)
        conn = sqlite3.connect(CACHE_DB)
        conn.execute(
            """INSERT OR REPLACE INTO code_cache
               (task_hash, task, filename, code, source, created_at, hit_count)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (task_hash, task, filename, code, source, time.time()),
        )
        conn.commit()
        conn.close()

    def _generate_with_llm(self, task: str, filename: str) -> Optional[str]:
        """用 LLM 生成代码"""
        prompt = f"""为以下任务生成 Python 代码。

任务: {task[:300]}
文件名: {filename}

要求:
1. 只输出代码，不要其他文字
2. 代码要完整可运行
3. 包含必要的 docstring
4. 遵循 PEP 8 规范"""

        try:
            result = self.llm_fn(prompt)
            # 提取代码块
            code = self._extract_code(result)
            return code
        except Exception:
            return None

    def _extract_code(self, text: str) -> str:
        """从 LLM 输出中提取代码"""
        # 尝试提取 ```python ... ``` 代码块
        match = re.search(r'```python\s*\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 尝试提取 ``` ... ``` 代码块
        match = re.search(r'```\s*\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 如果没有代码块，直接返回（去掉首尾非代码行）
        lines = text.strip().split('\n')
        code_lines = []
        in_code = False
        for line in lines:
            if line.startswith('def ') or line.startswith('class ') or line.startswith('import '):
                in_code = True
            if in_code:
                code_lines.append(line)

        return '\n'.join(code_lines) if code_lines else text.strip()

    def list_templates(self) -> List[Dict]:
        """列出所有模板"""
        return [
            {
                'name': t['name'],
                'category': t['category'],
                'keywords': t['keywords'],
            }
            for t in self._templates.values()
        ]

    def cache_stats(self) -> Dict:
        """缓存统计"""
        conn = sqlite3.connect(CACHE_DB)
        total = conn.execute('SELECT COUNT(*) FROM code_cache').fetchone()[0]
        by_source = conn.execute('SELECT source, COUNT(*) FROM code_cache GROUP BY source').fetchall()
        conn.close()
        return {
            'total': total,
            'by_source': {s: c for s, c in by_source},
        }
