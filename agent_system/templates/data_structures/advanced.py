# name: 高级数据结构
# keywords: 图, 字典树, 并查集, 跳表, 图算法, graph, trie, union find, skip list

from typing import Dict, List, Optional, Tuple


class Graph:
    """图（邻接表表示）"""

    def __init__(self, directed: bool = False):
        self.directed = directed
        self.adj: Dict[str, List[Tuple[str, float]]] = {}

    def add_vertex(self, v: str):
        """添加顶点"""
        if v not in self.adj:
            self.adj[v] = []

    def add_edge(self, u: str, v: str, weight: float = 1.0):
        """添加边"""
        self.add_vertex(u)
        self.add_vertex(v)
        self.adj[u].append((v, weight))
        if not self.directed:
            self.adj[v].append((u, weight))

    def remove_edge(self, u: str, v: str):
        """删除边"""
        if u in self.adj:
            self.adj[u] = [(w, wt) for w, wt in self.adj[u] if w != v]
        if not self.directed and v in self.adj:
            self.adj[v] = [(w, wt) for w, wt in self.adj[v] if w != u]

    def neighbors(self, v: str) -> List[str]:
        """获取邻居"""
        return [w for w, _ in self.adj.get(v, [])]

    def has_edge(self, u: str, v: str) -> bool:
        """检查是否有边"""
        return any(w == v for w, _ in self.adj.get(u, []))

    def bfs(self, start: str) -> List[str]:
        """广度优先搜索"""
        visited = set()
        queue = [start]
        result = []
        while queue:
            v = queue.pop(0)
            if v in visited:
                continue
            visited.add(v)
            result.append(v)
            for w in self.neighbors(v):
                if w not in visited:
                    queue.append(w)
        return result

    def dfs(self, start: str) -> List[str]:
        """深度优先搜索"""
        visited = set()
        result = []

        def _dfs(v: str):
            visited.add(v)
            result.append(v)
            for w in self.neighbors(v):
                if w not in visited:
                    _dfs(w)

        _dfs(start)
        return result

    def shortest_path(self, start: str, end: str) -> Optional[List[str]]:
        """最短路径（BFS）"""
        if start == end:
            return [start]
        visited = set()
        queue = [(start, [start])]
        while queue:
            v, path = queue.pop(0)
            if v in visited:
                continue
            visited.add(v)
            for w in self.neighbors(v):
                if w == end:
                    return path + [w]
                if w not in visited:
                    queue.append((w, path + [w]))
        return None

    def dijkstra(self, start: str) -> Dict[str, float]:
        """Dijkstra 最短路径算法"""
        import heapq

        distances = {v: float('inf') for v in self.adj}
        distances[start] = 0
        pq = [(0, start)]

        while pq:
            dist, v = heapq.heappop(pq)
            if dist > distances[v]:
                continue
            for w, weight in self.adj[v]:
                new_dist = dist + weight
                if new_dist < distances[w]:
                    distances[w] = new_dist
                    heapq.heappush(pq, (new_dist, w))

        return distances

    def has_cycle(self) -> bool:
        """检测是否有环"""
        visited = set()
        rec_stack = set()

        def _dfs(v: str) -> bool:
            visited.add(v)
            rec_stack.add(v)
            for w in self.neighbors(v):
                if w not in visited:
                    if _dfs(w):
                        return True
                elif w in rec_stack:
                    return True
            rec_stack.remove(v)
            return False

        for v in self.adj:
            if v not in visited:
                if _dfs(v):
                    return True
        return False


class Trie:
    """字典树（前缀树）"""

    def __init__(self):
        self.root = {}

    def insert(self, word: str):
        """插入单词"""
        node = self.root
        for char in word:
            if char not in node:
                node[char] = {}
            node = node[char]
        node['#'] = True  # 标记单词结束

    def search(self, word: str) -> bool:
        """搜索单词"""
        node = self.root
        for char in word:
            if char not in node:
                return False
            node = node[char]
        return '#' in node

    def starts_with(self, prefix: str) -> bool:
        """检查是否有前缀"""
        node = self.root
        for char in prefix:
            if char not in node:
                return False
            node = node[char]
        return True

    def get_words_with_prefix(self, prefix: str) -> List[str]:
        """获取所有以指定前缀开头的单词"""
        node = self.root
        for char in prefix:
            if char not in node:
                return []
            node = node[char]

        result = []
        self._collect_words(node, prefix, result)
        return result

    def _collect_words(self, node: dict, prefix: str, result: List[str]):
        if '#' in node:
            result.append(prefix)
        for char, child in node.items():
            if char != '#':
                self._collect_words(child, prefix + char, result)

    def delete(self, word: str):
        """删除单词"""
        self._delete_helper(self.root, word, 0)

    def _delete_helper(self, node: dict, word: str, depth: int) -> bool:
        if depth == len(word):
            if '#' in node:
                del node['#']
                return len(node) == 0
            return False

        char = word[depth]
        if char not in node:
            return False

        should_delete = self._delete_helper(node[char], word, depth + 1)
        if should_delete:
            del node[char]
            return len(node) == 0

        return False


class UnionFind:
    """并查集"""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.count = n  # 连通分量数

    def find(self, x: int) -> int:
        """查找根节点（路径压缩）"""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        """合并两个集合"""
        root_x = self.find(x)
        root_y = self.find(y)

        if root_x == root_y:
            return False

        # 按秩合并
        if self.rank[root_x] < self.rank[root_y]:
            root_x, root_y = root_y, root_x
        self.parent[root_y] = root_x
        if self.rank[root_x] == self.rank[root_y]:
            self.rank[root_x] += 1

        self.count -= 1
        return True

    def connected(self, x: int, y: int) -> bool:
        """检查是否连通"""
        return self.find(x) == self.find(y)


class SkipList:
    """跳表"""

    def __init__(self, max_level: int = 16, p: float = 0.5):
        self.max_level = max_level
        self.p = p
        self.header = self._create_node(-1, max_level)
        self.level = 0
        self.size = 0

    def _create_node(self, value: int, level: int) -> dict:
        return {'value': value, 'forward': [None] * (level + 1)}

    def _random_level(self) -> int:
        import random

        level = 0
        while random.random() < self.p and level < self.max_level:
            level += 1
        return level

    def insert(self, value: int):
        """插入元素"""
        update = [None] * (self.max_level + 1)
        current = self.header

        for i in range(self.level, -1, -1):
            while current['forward'][i] and current['forward'][i]['value'] < value:
                current = current['forward'][i]
            update[i] = current

        new_level = self._random_level()
        if new_level > self.level:
            for i in range(self.level + 1, new_level + 1):
                update[i] = self.header
            self.level = new_level

        new_node = self._create_node(value, new_level)
        for i in range(new_level + 1):
            new_node['forward'][i] = update[i]['forward'][i]
            update[i]['forward'][i] = new_node

        self.size += 1

    def search(self, value: int) -> bool:
        """搜索元素"""
        current = self.header
        for i in range(self.level, -1, -1):
            while current['forward'][i] and current['forward'][i]['value'] < value:
                current = current['forward'][i]
        current = current['forward'][0]
        return current is not None and current['value'] == value

    def delete(self, value: int) -> bool:
        """删除元素"""
        update = [None] * (self.max_level + 1)
        current = self.header

        for i in range(self.level, -1, -1):
            while current['forward'][i] and current['forward'][i]['value'] < value:
                current = current['forward'][i]
            update[i] = current

        target = current['forward'][0]
        if target is None or target['value'] != value:
            return False

        for i in range(self.level + 1):
            if update[i]['forward'][i] != target:
                break
            update[i]['forward'][i] = target['forward'][i]

        while self.level > 0 and self.header['forward'][self.level] is None:
            self.level -= 1

        self.size -= 1
        return True

    def to_list(self) -> List[int]:
        """转为有序列表"""
        result = []
        current = self.header['forward'][0]
        while current:
            result.append(current['value'])
            current = current['forward'][0]
        return result
