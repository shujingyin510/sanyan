"""三态图：带置信度的图结构"""

from typing import Dict, List, Tuple
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError
from ops.registry import register


class TernaryGraph:
    """三态图：节点和边都带置信度的图结构"""

    def __init__(self):
        self._nodes: Dict[str, TritValue] = {}
        self._edges: Dict[str, List[Tuple[str, float]]] = {}

    def add_node(self, node, confidence=1.0):
        key = str(node)
        if key in self._nodes:
            new_conf = max(self._nodes[key].confidence, confidence)
            self._nodes[key] = TritValue(self._nodes[key].value, confidence=new_conf)
        else:
            self._nodes[key] = TritValue(1, confidence=confidence)

    def add_edge(self, from_node, to_node, confidence=1.0, bidirectional=False):
        from_key, to_key = str(from_node), str(to_node)
        if from_key not in self._nodes:
            self.add_node(from_key)
        if to_key not in self._nodes:
            self.add_node(to_key)
        self._edges.setdefault(from_key, []).append((to_key, confidence))
        if bidirectional:
            self._edges.setdefault(to_key, []).append((from_key, confidence))

    def get_neighbors(self, node):
        return self._edges.get(str(node), [])

    def node_confidence(self, node):
        return self._nodes[str(node)].confidence if str(node) in self._nodes else 0.0

    def edge_confidence(self, from_node, to_node):
        for to, conf in self._edges.get(str(from_node), []):
            if to == str(to_node):
                return conf
        return 0.0

    def shortest_path(self, start, end):
        import heapq

        start_key, end_key = str(start), str(end)
        if start_key not in self._nodes or end_key not in self._nodes:
            return None, 0.0
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
        visited, components = set(), []
        for node in self._nodes:
            if node not in visited:
                component, stack = [], [node]
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
        return {
            'nodes': {k: v.confidence for k, v in self._nodes.items()},
            'edges': {k: [(to, conf) for to, conf in v] for k, v in self._edges.items()},
        }

    def __repr__(self):
        return f'三态图(节点={len(self._nodes)}, 边={sum(len(v) for v in self._edges.values())})'


# ── 操作函数 ──


def _ternary_graph_new(evaluator, args):
    return TernaryGraph()


def _ternary_graph_add_node(evaluator, args):
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
    if len(args) < 3:
        raise SanyanSyntaxError('三态图加边 需要图、起点和终点')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('第一个参数必须是三态图')
    from_node, to_node = evaluator.eval(args[1]), evaluator.eval(args[2])
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
    if len(args) != 2:
        raise SanyanSyntaxError('三态图邻居 需要图和节点')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('第一个参数必须是三态图')
    return g.get_neighbors(evaluator.eval(args[1]))


def _ternary_graph_shortest_path(evaluator, args):
    if len(args) != 3:
        raise SanyanSyntaxError('三态图最短路 需要图、起点和终点')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('第一个参数必须是三态图')
    path, conf = g.shortest_path(evaluator.eval(args[1]), evaluator.eval(args[2]))
    if path is None:
        return [TritValue(-1), TritValue(0)]
    return [path, TritValue(conf, confidence=1.0)]


def _ternary_graph_components(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态图连通 需要一个参数')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('参数必须是三态图')
    return g.connected_components()


def _ternary_graph_to_dict(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态图字典 需要一个参数')
    g = evaluator.eval(args[0])
    if not isinstance(g, TernaryGraph):
        raise SanyanTypeError('参数必须是三态图')
    return g.to_dict()


register('三态图', _ternary_graph_new)
register('三态图加节点', _ternary_graph_add_node)
register('三态图加边', _ternary_graph_add_edge)
register('三态图邻居', _ternary_graph_neighbors)
register('三态图最短路', _ternary_graph_shortest_path)
register('三态图连通', _ternary_graph_components)
register('三态图字典', _ternary_graph_to_dict)
register('ternary_graph', _ternary_graph_new)
register('ternary_graph_add_node', _ternary_graph_add_node)
register('ternary_graph_add_edge', _ternary_graph_add_edge)
register('ternary_graph_neighbors', _ternary_graph_neighbors)
register('ternary_graph_shortest_path', _ternary_graph_shortest_path)
register('ternary_graph_components', _ternary_graph_components)
register('ternary_graph_to_dict', _ternary_graph_to_dict)
