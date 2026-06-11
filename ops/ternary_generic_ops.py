"""三态泛型容器：三态集、三态图、三态队列、三态栈"""

from typing import Any
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError
from ops.registry import register


class TernarySet:
    """三态集：每个元素带独立置信度的集合。

    支持：
    - 添加/删除元素（带置信度）
    - 交集/并集/差集（置信度融合）
    - 成员查询（返回置信度）
    """

    def __init__(self):
        self._elements: dict[str, TritValue] = {}

    def add(self, elem, confidence=1.0):
        """添加元素，置信度取较高值"""
        key = str(elem) if not isinstance(elem, str) else elem
        if key in self._elements:
            existing = self._elements[key]
            new_conf = max(existing.confidence, confidence)
            self._elements[key] = TritValue(existing.value, confidence=new_conf)
        else:
            self._elements[key] = TritValue(1, confidence=confidence)

    def remove(self, elem):
        """删除元素"""
        key = str(elem) if not isinstance(elem, str) else elem
        if key in self._elements:
            del self._elements[key]

    def contains(self, elem):
        """查询元素，返回置信度"""
        key = str(elem) if not isinstance(elem, str) else elem
        if key in self._elements:
            return self._elements[key].confidence
        return 0.0

    def size(self):
        """返回元素数量"""
        return len(self._elements)

    def to_list(self):
        """转为列表"""
        return list(self._elements.keys())

    def union(self, other: 'TernarySet'):
        """并集：置信度取较高值"""
        result = TernarySet()
        for k, v in self._elements.items():
            result._elements[k] = v
        for k, v in other._elements.items():
            if k in result._elements:
                existing = result._elements[k]
                new_conf = max(existing.confidence, v.confidence)
                result._elements[k] = TritValue(v.value, confidence=new_conf)
            else:
                result._elements[k] = v
        return result

    def intersection(self, other: 'TernarySet'):
        """交集：置信度取较低值"""
        result = TernarySet()
        for k, v in self._elements.items():
            if k in other._elements:
                other_v = other._elements[k]
                new_conf = min(v.confidence, other_v.confidence)
                result._elements[k] = TritValue(v.value, confidence=new_conf)
        return result

    def difference(self, other: 'TernarySet'):
        """差集：只保留在 self 中但不在 other 中的元素"""
        result = TernarySet()
        for k, v in self._elements.items():
            if k not in other._elements:
                result._elements[k] = v
        return result

    def confidence_sum(self):
        """返回置信度总和"""
        return sum(v.confidence for v in self._elements.values())

    def __repr__(self):
        items = ', '.join(f'{k}({v.confidence:.2f})' for k, v in self._elements.items())
        return f'三态集({items})'


class TernaryGraph:
    """三态图：节点和边都带置信度的图结构。

    支持：
    - 添加节点/边（带置信度）
    - 最短路径（置信度加权）
    - 连通分量
    - 节点查询
    """

    def __init__(self):
        self._nodes: dict[str, TritValue] = {}
        self._edges: dict[str, list[tuple[str, float]]] = {}

    def add_node(self, node, confidence=1.0):
        """添加节点"""
        key = str(node)
        if key in self._nodes:
            existing = self._nodes[key]
            new_conf = max(existing.confidence, confidence)
            self._nodes[key] = TritValue(existing.value, confidence=new_conf)
        else:
            self._nodes[key] = TritValue(1, confidence=confidence)

    def add_edge(self, from_node, to_node, confidence=1.0, bidirectional=False):
        """添加边"""
        from_key = str(from_node)
        to_key = str(to_node)

        # 确保节点存在
        if from_key not in self._nodes:
            self.add_node(from_key)
        if to_key not in self._nodes:
            self.add_node(to_key)

        # 添加边
        if from_key not in self._edges:
            self._edges[from_key] = []
        self._edges[from_key].append((to_key, confidence))

        if bidirectional:
            if to_key not in self._edges:
                self._edges[to_key] = []
            self._edges[to_key].append((from_key, confidence))

    def get_neighbors(self, node):
        """获取邻居节点"""
        key = str(node)
        return self._edges.get(key, [])

    def node_confidence(self, node):
        """获取节点置信度"""
        key = str(node)
        if key in self._nodes:
            return self._nodes[key].confidence
        return 0.0

    def edge_confidence(self, from_node, to_node):
        """获取边置信度"""
        from_key = str(from_node)
        to_key = str(to_node)
        if from_key in self._edges:
            for to, conf in self._edges[from_key]:
                if to == to_key:
                    return conf
        return 0.0

    def shortest_path(self, start, end):
        """最短路径（置信度加权）：返回路径和最低置信度"""
        import heapq

        start_key = str(start)
        end_key = str(end)

        if start_key not in self._nodes or end_key not in self._nodes:
            return None, 0.0

        # Dijkstra 算法，权重为 1/置信度
        distances = {start_key: 0.0}
        paths = {start_key: [start_key]}
        min_conf = {start_key: 1.0}
        heap = [(0.0, start_key)]

        while heap:
            dist, current = heapq.heappop(heap)

            if current == end_key:
                return paths[current], min_conf[current]

            if dist > distances.get(current, float('inf')):
                continue

            for neighbor, conf in self._edges.get(current, []):
                # 权重为 1/置信度（置信度越高，权重越低）
                weight = 1.0 / max(conf, 0.01)
                new_dist = dist + weight
                new_conf = min(min_conf[current], conf)

                if new_dist < distances.get(neighbor, float('inf')):
                    distances[neighbor] = new_dist
                    paths[neighbor] = paths[current] + [neighbor]
                    min_conf[neighbor] = new_conf
                    heapq.heappush(heap, (new_dist, neighbor))

        return None, 0.0

    def connected_components(self):
        """获取连通分量"""
        visited = set()
        components = []

        for node in self._nodes:
            if node not in visited:
                component = []
                stack = [node]
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.append(current)
                        for neighbor, _ in self._edges.get(current, []):
                            if neighbor not in visited:
                                stack.append(neighbor)
                components.append(component)

        return components

    def to_dict(self):
        """转为字典表示"""
        return {
            'nodes': {k: v.confidence for k, v in self._nodes.items()},
            'edges': {k: [(to, conf) for to, conf in v] for k, v in self._edges.items()},
        }

    def __repr__(self):
        return f'三态图(节点={len(self._nodes)}, 边={sum(len(v) for v in self._edges.values())})'


class TernaryQueue:
    """三态队列：先进先出，元素带置信度"""

    def __init__(self):
        self._items: list[tuple[Any, float]] = []

    def enqueue(self, item, confidence=1.0):
        """入队"""
        self._items.append((item, confidence))

    def dequeue(self):
        """出队，返回 (元素, 置信度)"""
        if not self._items:
            return None, 0.0
        return self._items.pop(0)

    def peek(self):
        """查看队首"""
        if not self._items:
            return None, 0.0
        return self._items[0]

    def size(self):
        return len(self._items)

    def is_empty(self):
        return len(self._items) == 0

    def to_list(self):
        return [(item, conf) for item, conf in self._items]

    def __repr__(self):
        return f'三态队列(长度={len(self._items)})'


class TernaryStack:
    """三态栈：后进先出，元素带置信度"""

    def __init__(self):
        self._items: list[tuple[Any, float]] = []

    def push(self, item, confidence=1.0):
        """压栈"""
        self._items.append((item, confidence))

    def pop(self):
        """弹栈，返回 (元素, 置信度)"""
        if not self._items:
            return None, 0.0
        return self._items.pop()

    def peek(self):
        """查看栈顶"""
        if not self._items:
            return None, 0.0
        return self._items[-1]

    def size(self):
        return len(self._items)

    def is_empty(self):
        return len(self._items) == 0

    def to_list(self):
        return [(item, conf) for item, conf in reversed(self._items)]

    def __repr__(self):
        return f'三态栈(长度={len(self._items)})'


# ── 三态集操作 ──


def _ternary_set_new(evaluator, args):
    """三态集(元素1, 元素2, ...) — 创建三态集"""
    s = TernarySet()
    for a in args:
        val = evaluator.eval(a)
        if isinstance(val, TritValue):
            s.add(val.to_payload() if val.is_string() else val.to_int(), val.confidence)
        else:
            s.add(val)
    return s


def _ternary_set_add(evaluator, args):
    """三态集加(set, 元素 [, 置信度]) — 添加元素"""
    if len(args) < 2:
        raise SanyanSyntaxError('三态集加 需要集合和元素')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('第一个参数必须是三态集')
    elem = evaluator.eval(args[1])
    conf = 1.0
    if len(args) >= 3:
        conf_val = evaluator.eval(args[2])
        conf = conf_val.to_float() if isinstance(conf_val, TritValue) else float(conf_val)
    s.add(elem, conf)
    return s


def _ternary_set_remove(evaluator, args):
    """三态集删(set, 元素) — 删除元素"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态集删 需要集合和元素')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('第一个参数必须是三态集')
    elem = evaluator.eval(args[1])
    s.remove(elem)
    return s


def _ternary_set_contains(evaluator, args):
    """三态集含(set, 元素) → 置信度"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态集含 需要集合和元素')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('第一个参数必须是三态集')
    elem = evaluator.eval(args[1])
    conf = s.contains(elem)
    return TritValue(1 if conf > 0 else -1, confidence=conf)


def _ternary_set_size(evaluator, args):
    """三态集长(set) → 元素数量"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态集长 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return TritValue(s.size())


def _ternary_set_union(evaluator, args):
    """三态集并(set1, set2) → 并集"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态集并 需要两个集合')
    s1 = evaluator.eval(args[0])
    s2 = evaluator.eval(args[1])
    if not isinstance(s1, TernarySet) or not isinstance(s2, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return s1.union(s2)


def _ternary_set_intersection(evaluator, args):
    """三态集交(set1, set2) → 交集"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态集交 需要两个集合')
    s1 = evaluator.eval(args[0])
    s2 = evaluator.eval(args[1])
    if not isinstance(s1, TernarySet) or not isinstance(s2, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return s1.intersection(s2)


def _ternary_set_difference(evaluator, args):
    """三态集差(set1, set2) → 差集"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态集差 需要两个集合')
    s1 = evaluator.eval(args[0])
    s2 = evaluator.eval(args[1])
    if not isinstance(s1, TernarySet) or not isinstance(s2, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return s1.difference(s2)


def _ternary_set_to_list(evaluator, args):
    """三态集列(set) → 列表"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态集列 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return s.to_list()


def _ternary_set_conf_sum(evaluator, args):
    """三态集信度和(set) → 置信度总和"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态集信度和 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return TritValue(s.confidence_sum(), confidence=1.0)


# ── 三态图操作 ──


def _ternary_graph_new(evaluator, args):
    """三态图() — 创建空图"""
    return TernaryGraph()


def _ternary_graph_add_node(evaluator, args):
    """三态图加节点(graph, 节点 [, 置信度])"""
    if len(args) < 2:
        raise SanyanSyntaxError('三态图加节点 需要图和节点')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('第一个参数必须是三态图')
    node = evaluator.eval(args[1])
    conf = 1.0
    if len(args) >= 3:
        conf_val = evaluator.eval(args[2])
        conf = conf_val.to_float() if isinstance(conf_val, TritValue) else float(conf_val)
    g.add_node(node, conf)
    return g


def _ternary_graph_add_edge(evaluator, args):
    """三态图加边(graph, 起点, 终点 [, 置信度 [, 双向]])"""
    if len(args) < 3:
        raise SanyanSyntaxError('三态图加边 需要图、起点和终点')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('第一个参数必须是三态图')
    from_node = evaluator.eval(args[1])
    to_node = evaluator.eval(args[2])
    conf = 1.0
    bidirectional = False
    if len(args) >= 4:
        conf_val = evaluator.eval(args[3])
        conf = conf_val.to_float() if isinstance(conf_val, TritValue) else float(conf_val)
    if len(args) >= 5:
        bidir_val = evaluator.eval(args[4])
        bidirectional = bidir_val.to_int() == 1 if isinstance(bidir_val, TritValue) else bool(bidir_val)
    g.add_edge(from_node, to_node, conf, bidirectional)
    return g


def _ternary_graph_neighbors(evaluator, args):
    """三态图邻居(graph, 节点) → 邻居列表"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态图邻居 需要图和节点')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('第一个参数必须是三态图')
    node = evaluator.eval(args[1])
    return g.get_neighbors(node)


def _ternary_graph_shortest_path(evaluator, args):
    """三态图最短路(graph, 起点, 终点) → [路径, 最低置信度]"""
    if len(args) != 3:
        raise SanyanSyntaxError('三态图最短路 需要图、起点和终点')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('第一个参数必须是三态图')
    start = evaluator.eval(args[1])
    end = evaluator.eval(args[2])
    path, conf = g.shortest_path(start, end)
    if path is None:
        return [TritValue(-1), TritValue(0)]
    return [path, TritValue(conf, confidence=1.0)]


def _ternary_graph_components(evaluator, args):
    """三态图连通(graph) → 连通分量列表"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态图连通 需要一个参数')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('参数必须是三态图')
    return g.connected_components()


def _ternary_graph_to_dict(evaluator, args):
    """三态图字典(graph) → 字典表示"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态图字典 需要一个参数')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('参数必须是三态图')
    return g.to_dict()


# ── 三态队列操作 ──


def _ternary_queue_new(evaluator, args):
    """三态队列() — 创建空队列"""
    return TernaryQueue()


def _ternary_queue_enqueue(evaluator, args):
    """三态入队(queue, 元素 [, 置信度])"""
    if len(args) < 2:
        raise SanyanSyntaxError('三态入队 需要队列和元素')
    q = evaluator.eval(args[0])
    if not isinstance(q, TernaryQueue):
        raise SanyanTypeError('第一个参数必须是三态队列')
    item = evaluator.eval(args[1])
    conf = 1.0
    if len(args) >= 3:
        conf_val = evaluator.eval(args[2])
        conf = conf_val.to_float() if isinstance(conf_val, TritValue) else float(conf_val)
    q.enqueue(item, conf)
    return q


def _ternary_queue_dequeue(evaluator, args):
    """三态出队(queue) → 元素"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态出队 需要一个参数')
    q = evaluator.eval(args[0])
    if not isinstance(q, TernaryQueue):
        raise SanyanTypeError('参数必须是三态队列')
    item, conf = q.dequeue()
    if item is None:
        return TritValue(-1, confidence=0.0)
    return item


def _ternary_queue_peek(evaluator, args):
    """三态查看队(queue) → 元素"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态查看队 需要一个参数')
    q = evaluator.eval(args[0])
    if not isinstance(q, TernaryQueue):
        raise SanyanTypeError('参数必须是三态队列')
    item, conf = q.peek()
    if item is None:
        return TritValue(-1, confidence=0.0)
    return item


def _ternary_queue_size(evaluator, args):
    """三态队长(queue) → 长度"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态队长 需要一个参数')
    q = evaluator.eval(args[0])
    if not isinstance(q, TernaryQueue):
        raise SanyanTypeError('参数必须是三态队列')
    return TritValue(q.size())


# ── 三态栈操作 ──


def _ternary_stack_new(evaluator, args):
    """三态栈() — 创建空栈"""
    return TernaryStack()


def _ternary_stack_push(evaluator, args):
    """三态压栈(stack, 元素 [, 置信度])"""
    if len(args) < 2:
        raise SanyanSyntaxError('三态压栈 需要栈和元素')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernaryStack):
        raise SanyanTypeError('第一个参数必须是三态栈')
    item = evaluator.eval(args[1])
    conf = 1.0
    if len(args) >= 3:
        conf_val = evaluator.eval(args[2])
        conf = conf_val.to_float() if isinstance(conf_val, TritValue) else float(conf_val)
    s.push(item, conf)
    return s


def _ternary_stack_pop(evaluator, args):
    """三态弹栈(stack) → 元素"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态弹栈 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernaryStack):
        raise SanyanTypeError('参数必须是三态栈')
    item, conf = s.pop()
    if item is None:
        return TritValue(-1, confidence=0.0)
    return item


def _ternary_stack_peek(evaluator, args):
    """三态查看栈(stack) → 元素"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态查看栈 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernaryStack):
        raise SanyanTypeError('参数必须是三态栈')
    item, conf = s.peek()
    if item is None:
        return TritValue(-1, confidence=0.0)
    return item


def _ternary_stack_size(evaluator, args):
    """三态栈长(stack) → 长度"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态栈长 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernaryStack):
        raise SanyanTypeError('参数必须是三态栈')
    return TritValue(s.size())


# ── 注册操作 ──

# 三态集
register('三态集', _ternary_set_new)
register('三态集加', _ternary_set_add)
register('三态集删', _ternary_set_remove)
register('三态集含', _ternary_set_contains)
register('三态集长', _ternary_set_size)
register('三态集并', _ternary_set_union)
register('三态集交', _ternary_set_intersection)
register('三态集差', _ternary_set_difference)
register('三态集列', _ternary_set_to_list)
register('三态集信度和', _ternary_set_conf_sum)

# 三态图
register('三态图', _ternary_graph_new)
register('三态图加节点', _ternary_graph_add_node)
register('三态图加边', _ternary_graph_add_edge)
register('三态图邻居', _ternary_graph_neighbors)
register('三态图最短路', _ternary_graph_shortest_path)
register('三态图连通', _ternary_graph_components)
register('三态图字典', _ternary_graph_to_dict)

# 三态队列
register('三态队列', _ternary_queue_new)
register('三态入队', _ternary_queue_enqueue)
register('三态出队', _ternary_queue_dequeue)
register('三态查看队', _ternary_queue_peek)
register('三态队长', _ternary_queue_size)

# 三态栈
register('三态栈', _ternary_stack_new)
register('三态压栈', _ternary_stack_push)
register('三态弹栈', _ternary_stack_pop)
register('三态查看栈', _ternary_stack_peek)
register('三态栈长', _ternary_stack_size)

# 英文别名
register('ternary_set', _ternary_set_new)
register('ternary_set_add', _ternary_set_add)
register('ternary_set_remove', _ternary_set_remove)
register('ternary_set_contains', _ternary_set_contains)
register('ternary_set_size', _ternary_set_size)
register('ternary_set_union', _ternary_set_union)
register('ternary_set_intersection', _ternary_set_intersection)
register('ternary_set_difference', _ternary_set_difference)

register('ternary_graph', _ternary_graph_new)
register('ternary_graph_add_node', _ternary_graph_add_node)
register('ternary_graph_add_edge', _ternary_graph_add_edge)
register('ternary_graph_neighbors', _ternary_graph_neighbors)
register('ternary_graph_shortest_path', _ternary_graph_shortest_path)
register('ternary_graph_components', _ternary_graph_components)

register('ternary_queue', _ternary_queue_new)
register('ternary_queue_enqueue', _ternary_queue_enqueue)
register('ternary_queue_dequeue', _ternary_queue_dequeue)
register('ternary_queue_peek', _ternary_queue_peek)
register('ternary_queue_size', _ternary_queue_size)

register('ternary_stack', _ternary_stack_new)
register('ternary_stack_push', _ternary_stack_push)
register('ternary_stack_pop', _ternary_stack_pop)
register('ternary_stack_peek', _ternary_stack_peek)
register('ternary_stack_size', _ternary_stack_size)
