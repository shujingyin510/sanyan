"""多Agent共享上下文 — 共享符号表 + 共享记忆 + Agent协作
P34: SharedContext — 多Agent共享上下文空间
P35: AgentCoordinator — Agent协调器（任务分发+结果聚合）
P36: SharedSymbolTable — 共享符号表（子Agent可读父Agent索引）
"""

import threading
import time
from typing import Any, Callable, Dict, List, Tuple, Optional


class SharedContext:
    """共享上下文空间：多Agent可读写"""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._watchers: Dict[str, List[Callable]] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """读取共享数据"""
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any, source: str = ''):
        """写入共享数据"""
        with self._lock:
            old_value = self._data.get(key)
            self._data[key] = {
                'value': value,
                'source': source,
                'time': time.time(),
            }
            # 触发监视器
            if old_value != value and key in self._watchers:
                for watcher in self._watchers[key]:
                    try:
                        watcher(key, value, source)
                    except Exception:
                        pass

    def watch(self, key: str, callback: Callable):
        """监视数据变化"""
        with self._lock:
            if key not in self._watchers:
                self._watchers[key] = []
            self._watchers[key].append(callback)

    def unwatch(self, key: str, callback: Callable = None):
        """取消监视"""
        with self._lock:
            if callback:
                if key in self._watchers:
                    self._watchers[key] = [w for w in self._watchers[key] if w != callback]
            else:
                self._watchers.pop(key, None)

    def get_all(self) -> Dict[str, Any]:
        """获取所有共享数据"""
        with self._lock:
            return {k: v['value'] for k, v in self._data.items()}

    def keys(self) -> List[str]:
        """获取所有键"""
        with self._lock:
            return list(self._data.keys())

    def summary(self) -> str:
        """共享上下文摘要"""
        with self._lock:
            entries = []
            for k, v in self._data.items():
                source = v.get('source', '?')
                val_str = str(v['value'])[:50]
                entries.append(f'  {k} = {val_str} (from {source})')
            return '共享上下文:\n' + '\n'.join(entries) if entries else '(空)'


class SharedSymbolTable:
    """共享符号表：子Agent可读父Agent的符号索引"""

    def __init__(self):
        self._symbols: Dict[str, Dict] = {}
        self._lock = threading.RLock()

    def import_from(self, parent_table: 'SharedSymbolTable'):
        """从父符号表导入"""
        with self._lock:
            parent_symbols = parent_table.get_all()
            for sym, info in parent_symbols.items():
                if sym not in self._symbols:
                    self._symbols[sym] = {**info, 'imported': True}

    def register(self, name: str, file_path: str, line: int, symbol_type: str = 'def', source: str = ''):
        """注册符号"""
        with self._lock:
            if name not in self._symbols:
                self._symbols[name] = {
                    'defs': [],
                    'refs': [],
                    'type': symbol_type,
                }
            entry = self._symbols[name]
            entry['defs'].append(
                {
                    'file': file_path,
                    'line': line,
                    'source': source,
                }
            )

    def add_ref(self, name: str, file_path: str, line: int):
        """添加引用"""
        with self._lock:
            if name not in self._symbols:
                self._symbols[name] = {'defs': [], 'refs': [], 'type': 'ref'}
            self._symbols[name]['refs'].append(
                {
                    'file': file_path,
                    'line': line,
                }
            )

    def lookup(self, name: str) -> Dict:
        """查找符号"""
        with self._lock:
            return self._symbols.get(name, {'defs': [], 'refs': [], 'type': 'unknown'})

    def search(self, keyword: str) -> List[Tuple[str, Dict]]:
        """搜索符号"""
        with self._lock:
            results = []
            for name, info in self._symbols.items():
                if keyword.lower() in name.lower():
                    results.append((name, info))
            return results

    def get_all(self) -> Dict[str, Dict]:
        """获取所有符号"""
        with self._lock:
            return dict(self._symbols)

    def stats(self) -> Dict[str, int]:
        """统计信息"""
        with self._lock:
            total = len(self._symbols)
            imported = sum(1 for s in self._symbols.values() if s.get('imported'))
            return {'total': total, 'imported': imported, 'local': total - imported}


class AgentCoordinator:
    """Agent协调器：任务分发 + 结果聚合 + 冲突解决"""

    def __init__(self):
        self._agents: Dict[str, Dict] = {}
        self._shared = SharedContext()
        self._symbol_table = SharedSymbolTable()
        self._task_queue: List[Dict] = []
        self._results: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def register_agent(self, name: str, agent_fn: Callable, capabilities: List[str] = None):
        """注册Agent"""
        with self._lock:
            self._agents[name] = {
                'fn': agent_fn,
                'capabilities': capabilities or [],
                'status': 'idle',
                'tasks_completed': 0,
            }

    def submit_task(self, task: str, required_capabilities: List[str] = None, agent_name: Optional[str] = None) -> str:
        """提交任务"""
        task_id = f'task_{int(time.time() * 1000)}'

        with self._lock:
            # 选择Agent
            if agent_name and agent_name in self._agents:
                chosen = agent_name
            else:
                chosen = self._select_agent(required_capabilities or [])

            self._task_queue.append(
                {
                    'id': task_id,
                    'task': task,
                    'agent': chosen,
                    'status': 'pending',
                    'created_at': time.time(),
                }
            )

        return task_id

    def execute_task(self, task_id: str, context: Dict = None) -> Any:
        """执行任务"""
        with self._lock:
            task = None
            for t in self._task_queue:
                if t['id'] == task_id:
                    task = t
                    break

            if not task:
                return f'未知任务: {task_id}'

            agent_name = task['agent']
            if agent_name not in self._agents:
                return f'未知Agent: {agent_name}'

            agent = self._agents[agent_name]
            agent['status'] = 'busy'

        # 执行
        try:
            result = agent['fn'](task['task'], context or {})
            with self._lock:
                task['status'] = 'completed'
                task['result'] = result
                agent['status'] = 'idle'
                agent['tasks_completed'] += 1
                self._results[task_id] = result
            return result
        except Exception as e:
            with self._lock:
                task['status'] = 'failed'
                task['error'] = str(e)
                agent['status'] = 'idle'
            return f'执行失败: {e}'

    def execute_parallel(self, tasks: List[Dict[str, Any]]) -> List[Dict]:
        """并行执行多个任务"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = []
        with ThreadPoolExecutor(max_workers=min(4, len(tasks))) as pool:
            futures = {}
            for task_info in tasks:
                task_id = self.submit_task(
                    task_info['task'],
                    task_info.get('capabilities'),
                    task_info.get('agent'),
                )
                future = pool.submit(self.execute_task, task_id, task_info.get('context'))
                futures[future] = task_id

            for future in as_completed(futures):
                task_id = futures[future]
                try:
                    result = future.result(timeout=60)
                    results.append({'id': task_id, 'result': result, 'success': True})
                except Exception as e:
                    results.append({'id': task_id, 'result': str(e), 'success': False})

        return results

    def aggregate_results(self, results: List[Dict], method: str = 'majority') -> Any:
        """聚合多个结果"""
        if not results:
            return None

        if method == 'majority':
            # 多数投票
            from collections import Counter

            values = [r.get('result') for r in results if r.get('success')]
            if not values:
                return results[0].get('result') if results else None
            counter = Counter(str(v) for v in values)
            return counter.most_common(1)[0][0]

        elif method == 'first':
            # 第一个成功的结果
            for r in results:
                if r.get('success'):
                    return r.get('result')
            return None

        elif method == 'all':
            # 所有结果
            return [r.get('result') for r in results if r.get('success')]

        return results

    def _select_agent(self, capabilities: List[str]) -> str:
        """选择最合适的Agent"""
        best_agent = None
        best_score = -1

        for name, info in self._agents.items():
            if info['status'] != 'idle':
                continue

            # 能力匹配分数
            agent_caps = set(info['capabilities'])
            needed_caps = set(capabilities)
            if needed_caps:
                score = len(agent_caps & needed_caps) / len(needed_caps)
            else:
                score = 0.5  # 无特定需求

            # 负载均衡：完成任务少的优先
            score -= info['tasks_completed'] * 0.01

            if score > best_score:
                best_score = score
                best_agent = name

        return best_agent or list(self._agents.keys())[0] if self._agents else 'default'

    def get_shared_context(self) -> SharedContext:
        """获取共享上下文"""
        return self._shared

    def get_symbol_table(self) -> SharedSymbolTable:
        """获取共享符号表"""
        return self._symbol_table

    def status(self) -> str:
        """协调器状态"""
        agents = []
        for name, info in self._agents.items():
            agents.append(f'  {name}: {info["status"]} ({info["tasks_completed"]}完成)')
        pending = sum(1 for t in self._task_queue if t['status'] == 'pending')
        return 'Agent协调器:\n' + '\n'.join(agents) + f'\n待处理: {pending}个任务'
