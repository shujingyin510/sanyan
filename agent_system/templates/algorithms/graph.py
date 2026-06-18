# name: 图算法
# keywords: 图, 最短路径, 最小生成树, 拓扑排序, graph, shortest path, MST, topological sort, Dijkstra, BFS, DFS, Kruskal, Prim

from typing import Dict, List, Optional, Set, Tuple
import heapq


def dijkstra(graph: Dict[str, List[Tuple[str, float]]], start: str) -> Dict[str, float]:
    """Dijkstra 最短路径算法

    时间复杂度: O((V + E) log V)
    空间复杂度: O(V)

    Args:
        graph: 邻接表 {vertex: [(neighbor, weight), ...]}
        start: 起点

    Returns:
        {vertex: shortest_distance}
    """
    distances = {v: float('inf') for v in graph}
    distances[start] = 0
    pq = [(0, start)]

    while pq:
        dist, v = heapq.heappop(pq)
        if dist > distances[v]:
            continue
        for w, weight in graph.get(v, []):
            new_dist = dist + weight
            if new_dist < distances[w]:
                distances[w] = new_dist
                heapq.heappush(pq, (new_dist, w))

    return distances


def dijkstra_path(graph: Dict[str, List[Tuple[str, float]]], start: str, end: str) -> Optional[Tuple[float, List[str]]]:
    """Dijkstra 最短路径（带路径）

    Returns:
        (distance, path) or None
    """
    distances = {v: float('inf') for v in graph}
    distances[start] = 0
    prev = {v: None for v in graph}
    pq = [(0, start)]

    while pq:
        dist, v = heapq.heappop(pq)
        if v == end:
            break
        if dist > distances[v]:
            continue
        for w, weight in graph.get(v, []):
            new_dist = dist + weight
            if new_dist < distances[w]:
                distances[w] = new_dist
                prev[w] = v
                heapq.heappush(pq, (new_dist, w))

    if distances[end] == float('inf'):
        return None

    # 重建路径
    path = []
    current = end
    while current is not None:
        path.append(current)
        current = prev[current]
    path.reverse()

    return distances[end], path


def bellman_ford(graph: Dict[str, List[Tuple[str, float]]], start: str) -> Optional[Dict[str, float]]:
    """Bellman-Ford 最短路径算法（支持负权边）

    时间复杂度: O(VE)
    空间复杂度: O(V)

    Returns:
        {vertex: shortest_distance} or None (检测到负环)
    """
    # 收集所有边
    edges = []
    for u in graph:
        for v, w in graph[u]:
            edges.append((u, v, w))

    vertices = set(graph.keys())
    distances = {v: float('inf') for v in vertices}
    distances[start] = 0

    # 松弛 V-1 次
    for _ in range(len(vertices) - 1):
        for u, v, w in edges:
            if distances[u] != float('inf') and distances[u] + w < distances[v]:
                distances[v] = distances[u] + w

    # 检测负环
    for u, v, w in edges:
        if distances[u] != float('inf') and distances[u] + w < distances[v]:
            return None

    return distances


def floyd_warshall(graph: Dict[str, List[Tuple[str, float]]]) -> Dict[str, Dict[str, float]]:
    """Floyd-Warshall 全源最短路径

    时间复杂度: O(V³)
    空间复杂度: O(V²)
    """
    vertices = list(graph.keys())
    n = len(vertices)
    idx = {v: i for i, v in enumerate(vertices)}

    # 初始化距离矩阵
    dist = [[float('inf')] * n for _ in range(n)]
    for i in range(n):
        dist[i][i] = 0

    for u in graph:
        for v, w in graph[u]:
            dist[idx[u]][idx[v]] = w

    # Floyd-Warshall
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if dist[i][k] + dist[k][j] < dist[i][j]:
                    dist[i][k] + dist[k][j]

    return {vertices[i]: {vertices[j]: dist[i][j] for j in range(n)} for i in range(n)}


def kruskal_mst(n: int, edges: List[Tuple[int, int, float]]) -> List[Tuple[int, int, float]]:
    """Kruskal 最小生成树

    时间复杂度: O(E log E)
    空间复杂度: O(V)

    Args:
        n: 顶点数
        edges: [(u, v, weight), ...]

    Returns:
        MST 边列表
    """
    # 并查集
    parent = list(range(n))
    rank = [0] * n

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px == py:
            return False
        if rank[px] < rank[py]:
            px, py = py, px
        parent[py] = px
        if rank[px] == rank[py]:
            rank[px] += 1
        return True

    # 按权重排序
    edges.sort(key=lambda e: e[2])

    mst = []
    for u, v, w in edges:
        if union(u, v):
            mst.append((u, v, w))
            if len(mst) == n - 1:
                break

    return mst


def prim_mst(graph: Dict[str, List[Tuple[str, float]]], start: str) -> List[Tuple[str, str, float]]:
    """Prim 最小生成树

    时间复杂度: O((V + E) log V)
    空间复杂度: O(V)
    """
    mst = []
    visited = set()
    pq = [(0, start, None)]  # (weight, vertex, from)

    while pq and len(visited) < len(graph):
        weight, v, from_v = heapq.heappop(pq)
        if v in visited:
            continue
        visited.add(v)
        if from_v is not None:
            mst.append((from_v, v, weight))

        for w, edge_weight in graph.get(v, []):
            if w not in visited:
                heapq.heappush(pq, (edge_weight, w, v))

    return mst


def topological_sort(graph: Dict[str, List[str]]) -> Optional[List[str]]:
    """拓扑排序

    时间复杂度: O(V + E)
    空间复杂度: O(V)

    Returns:
        拓扑排序结果 or None (有环)
    """
    in_degree = {v: 0 for v in graph}
    for u in graph:
        for v in graph[u]:
            in_degree[v] = in_degree.get(v, 0) + 1

    queue = [v for v in graph if in_degree[v] == 0]
    result = []

    while queue:
        v = queue.pop(0)
        result.append(v)
        for w in graph[v]:
            in_degree[w] -= 1
            if in_degree[w] == 0:
                queue.append(w)

    if len(result) != len(graph):
        return None  # 有环

    return result


def has_cycle(graph: Dict[str, List[str]]) -> bool:
    """检测有向图是否有环"""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {v: WHITE for v in graph}

    def dfs(v: str) -> bool:
        color[v] = GRAY
        for w in graph[v]:
            if color[w] == GRAY:
                return True
            if color[w] == WHITE and dfs(w):
                return True
        color[v] = BLACK
        return False

    for v in graph:
        if color[v] == WHITE:
            if dfs(v):
                return True
    return False


def connected_components(graph: Dict[str, List[str]]) -> List[Set[str]]:
    """求连通分量（无向图）"""
    visited = set()
    components = []

    def dfs(v: str, component: Set[str]):
        visited.add(v)
        component.add(v)
        for w in graph[v]:
            if w not in visited:
                dfs(w, component)

    for v in graph:
        if v not in visited:
            component = set()
            dfs(v, component)
            components.append(component)

    return components


def strongly_connected_components(graph: Dict[str, List[str]]) -> List[Set[str]]:
    """求强连通分量（Tarjan 算法）"""
    index_counter = 0
    stack = []
    lowlink = {}
    index = {}
    on_stack = set()
    result = []

    def strongconnect(v: str):
        nonlocal index_counter
        index[v] = index_counter
        lowlink[v] = index_counter
        index_counter += 1
        stack.append(v)
        on_stack.add(v)

        for w in graph[v]:
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            component = set()
            while True:
                w = stack.pop()
                on_stack.remove(w)
                component.add(w)
                if w == v:
                    break
            result.append(component)

    for v in graph:
        if v not in index:
            strongconnect(v)

    return result
