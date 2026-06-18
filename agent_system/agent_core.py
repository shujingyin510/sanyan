"""Agent Core — 基础工具类

包含：
  - SymbolTable: 符号表缓存
  - MemoryStore: 分层记忆
  - ProjectGraph: 项目依赖图
"""

import glob as _glob
import re as _re
import time as _time


class SymbolTable:
    """符号表缓存：启动时扫全盘建索引，后续O(1)查"""

    def __init__(self):
        self._cache = {}
        self._indexed = False

    def build_all(self):
        """一次性扫描全项目，建立所有符号索引"""
        if self._indexed:
            return

        for ext in ['*.py', '*.san']:
            for fp in _glob.glob('**/' + ext, recursive=True):
                if '__pycache__' in fp or len(fp) > 80:
                    continue
                try:
                    with open(fp, encoding='utf-8', errors='ignore') as fh:
                        for lineno, line in enumerate(fh, 1):
                            # 函数/类定义
                            m = _re.search(r'\b(?:def|class|定义)\s+([a-zA-Z_]\w*)', line)
                            if m:
                                sym = m.group(1)
                                entry = self._cache.setdefault(sym, {'def': [], 'ref': []})
                                if len(entry['def']) < 5:
                                    entry['def'].append((fp, lineno))
                            else:
                                # 引用（非导入行）
                                for m2 in _re.finditer(r'\b([a-zA-Z_]\w{2,})\b', line):
                                    if 'import' in line.lower():
                                        continue
                                    sym = m2.group(1)
                                    entry = self._cache.setdefault(sym, {'def': [], 'ref': []})
                                    if len(entry['ref']) < 10:
                                        entry['ref'].append((fp, lineno))
                except Exception:
                    pass
        self._indexed = True

    def lookup(self, symbol):
        if not self._indexed:
            self.build_all()
        return self._cache.get(symbol, {'def': [], 'ref': []})


class MemoryStore:
    """分层记忆：语义摘要(S) + 事件存储(E) + 时间衰减 + 跨任务回忆

    S-Memory: LLM 一句话摘要，用于语义检索
    E-Memory: 原始事件存储，按时间衰减
    """

    def __init__(self):
        self.entries = []  # E-Memory: [{tool, result, kw, time, summary}]
        self.semantic = []  # S-Memory: [(summary, keywords)]
        self._summarizer = None  # lazy LLM ref

    def _extract_kw(self, text):
        kw = set(_re.findall(r'[a-zA-Z_]\w{2,}', str(text)))
        s = str(text)
        for i in range(len(s) - 1):
            if '\u4e00' <= s[i] <= '\u9fff' and '\u4e00' <= s[i + 1] <= '\u9fff':
                kw.add(s[i : i + 2])
        return kw

    def set_llm(self, llm_fn):
        """注入 LLM 摘要函数"""
        self._summarizer = llm_fn

    def add(self, tool, params, result):
        kw = self._extract_kw(str(params)) | self._extract_kw(str(result))
        entry = {
            'tool': tool,
            'result': str(result)[:200],
            'kw': kw,
            'time': _time.time(),
            'summary': '',
        }
        # LLM 摘要：异步尝试
        if self._summarizer:
            try:
                raw = str(params)[:100] + ' → ' + str(result)[:200]
                entry['summary'] = self._summarizer(f'用5字以内概括: {raw}') or ''
                if entry['summary']:
                    self.semantic.append((entry['summary'], kw))
            except Exception:
                pass
        self.entries.append(entry)

    def context(self, query='', limit=3):
        if not self.entries:
            return ''
        qk = self._extract_kw(query) if query else set()
        scored = []
        for i, e in enumerate(reversed(self.entries[-30:])):
            # 关键词匹配分
            ks = len(qk & e.get('kw', set())) if qk else 1
            # 语义匹配分
            ss = 0
            if e.get('summary') and qk:
                ss = len(qk & self._extract_kw(e['summary']))
            # 时间衰减：每 60 秒权重减半
            age = _time.time() - e.get('time', _time.time())
            decay = max(0.1, 0.5 ** (age / 60))
            score = (ks + ss * 2) * decay
            if score > 0.05:
                scored.append((score, e))
        scored.sort(key=lambda x: -x[0])
        entries = [e for _, e in scored[:limit]] or self.entries[-limit:]
        parts = [f'{e["tool"]}:{str(e["result"])[:60]}' for e in entries]
        if entries and entries[0].get('summary'):
            parts.insert(0, f'[摘要] {entries[0]["summary"]}')
        return '[记忆] ' + ' | '.join(parts)

    def recall(self, task, limit=3):
        """跨任务回忆：找到与当前任务相关的历史"""
        if not self.semantic:
            return ''
        tkw = self._extract_kw(task)
        scored = []
        for summary, kw in self.semantic[-50:]:
            s = len(tkw & kw) if tkw else 0
            if s > 0:
                scored.append((s, summary))
        scored.sort(key=lambda x: -x[0])
        if scored:
            return '[经验] ' + '; '.join(s for _, s in scored[:limit])
        return ''


class ProjectGraph:
    """项目图：文件依赖关系"""

    def __init__(self, root='.'):
        self.deps = {}  # file → [imported_files]
        self._built = False

    def build(self, files=None):
        if self._built:
            return

        files = files or _glob.glob('**/*.py', recursive=True)[:100]
        for fp in files:
            if '__pycache__' in fp:
                continue
            try:
                with open(fp, encoding='utf-8', errors='ignore') as fh:
                    deps = []
                    for line in fh:
                        if line.startswith('from ') or line.startswith('import '):
                            deps.append(line.strip()[:60])
                        if len(deps) > 10:
                            break
                    if deps:
                        self.deps[fp] = deps
            except Exception:
                pass
        self._built = True

    def depends_on(self, file):
        return self.deps.get(file, [])
