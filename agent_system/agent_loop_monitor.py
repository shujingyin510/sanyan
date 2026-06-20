"""Agent 循环日志 — 持久化 + 统计 + 健康监控

功能:
    - 每次循环记录到 .agent_loop.log
    - 统计修复成功率
    - 健康监控（卡住检测）
    - 回滚验证
"""

import json
import os
import time
from typing import Any, Dict, List
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(ROOT, '.agent_loop.log')
STATS_FILE = os.path.join(ROOT, '.agent_loop_stats.json')
HEALTH_FILE = os.path.join(ROOT, '.agent_loop_health.json')


class LoopLogger:
    """循环日志：记录每次验证循环的详细信息"""

    def __init__(self, log_file: str = LOG_FILE):
        self.log_file = log_file

    def log(self, event: str, details: Dict[str, Any] = None):
        """记录日志事件"""
        entry = {
            'time': datetime.now().isoformat(),
            'event': event,
            'details': details or {},
        }
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception:
            pass

    def log_cycle_start(self, cycle_num: int, changed_files: List[str]):
        """记录循环开始"""
        self.log(
            'cycle_start',
            {
                'cycle': cycle_num,
                'files': changed_files[:10],
            },
        )

    def log_preflight_result(self, success: bool, output: str):
        """记录 preflight 结果"""
        self.log(
            'preflight',
            {
                'success': success,
                'output': output[-300:],
            },
        )

    def log_agent_fix(self, attempt: int, success: bool, output: str):
        """记录 Agent 修复"""
        self.log(
            'agent_fix',
            {
                'attempt': attempt,
                'success': success,
                'output': output[-200:],
            },
        )

    def log_commit(self, success: bool, message: str):
        """记录提交"""
        self.log(
            'commit',
            {
                'success': success,
                'message': message,
            },
        )

    def log_stash(self, reason: str):
        """记录 stash 回滚"""
        self.log(
            'stash',
            {
                'reason': reason,
            },
        )

    def log_cycle_end(self, cycle_num: int, success: bool, duration: float):
        """记录循环结束"""
        self.log(
            'cycle_end',
            {
                'cycle': cycle_num,
                'success': success,
                'duration': duration,
            },
        )

    def log_error(self, error: str):
        """记录错误"""
        self.log(
            'error',
            {
                'error': error,
            },
        )

    def read_recent(self, n: int = 50) -> List[Dict]:
        """读取最近 n 条日志"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            return [json.loads(line) for line in lines[-n:]]
        except Exception:
            return []


class LoopStats:
    """循环统计：成功率、修复率、平均耗时"""

    def __init__(self, stats_file: str = STATS_FILE):
        self.stats_file = stats_file
        self._load()

    def _load(self):
        """加载统计数据"""
        try:
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                self._stats = json.load(f)
        except Exception:
            self._stats = {
                'total_cycles': 0,
                'successful_cycles': 0,
                'failed_cycles': 0,
                'agent_fixes_attempted': 0,
                'agent_fixes_succeeded': 0,
                'total_duration': 0,
                'cycles': [],
            }

    def _save(self):
        """保存统计数据"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self._stats, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def record_cycle(self, success: bool, duration: float, agent_fixes: int = 0, agent_fixes_succeeded: int = 0):
        """记录一次循环"""
        self._stats['total_cycles'] += 1
        if success:
            self._stats['successful_cycles'] += 1
        else:
            self._stats['failed_cycles'] += 1
        self._stats['agent_fixes_attempted'] += agent_fixes
        self._stats['agent_fixes_succeeded'] += agent_fixes_succeeded
        self._stats['total_duration'] += duration

        self._stats['cycles'].append(
            {
                'time': datetime.now().isoformat(),
                'success': success,
                'duration': duration,
                'agent_fixes': agent_fixes,
            }
        )

        # 只保留最近 100 次循环
        if len(self._stats['cycles']) > 100:
            self._stats['cycles'] = self._stats['cycles'][-100:]

        self._save()

    def get_success_rate(self) -> float:
        """获取总成功率"""
        total = self._stats['total_cycles']
        if total == 0:
            return 0
        return self._stats['successful_cycles'] / total

    def get_fix_rate(self) -> float:
        """获取 Agent 修复成功率"""
        attempted = self._stats['agent_fixes_attempted']
        if attempted == 0:
            return 0
        return self._stats['agent_fixes_succeeded'] / attempted

    def get_avg_duration(self) -> float:
        """获取平均循环耗时"""
        total = self._stats['total_cycles']
        if total == 0:
            return 0
        return self._stats['total_duration'] / total

    def summary(self) -> str:
        """统计摘要"""
        return (
            f'循环: {self._stats["total_cycles"]}次 '
            f'(成功{self._stats["successful_cycles"]} 失败{self._stats["failed_cycles"]}) '
            f'成功率{self.get_success_rate():.1%} | '
            f'Agent修复: {self._stats["agent_fixes_attempted"]}次 '
            f'成功率{self.get_fix_rate():.1%} | '
            f'平均耗时: {self.get_avg_duration():.1f}s'
        )


class HealthMonitor:
    """健康监控：检测卡住、超时、异常"""

    STUCK_THRESHOLD = 300  # 5分钟无进展视为卡住
    MAX_CONSECUTIVE_FAILURES = 5  # 连续失败上限

    def __init__(self, health_file: str = HEALTH_FILE):
        self.health_file = health_file
        self._state = {
            'last_activity': time.time(),
            'consecutive_failures': 0,
            'last_cycle_num': 0,
            'status': 'healthy',
        }
        self._load()

    def _load(self):
        """加载健康状态"""
        try:
            with open(self.health_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                self._state.update(saved)
        except Exception:
            pass

    def _save(self):
        """保存健康状态"""
        try:
            with open(self.health_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def record_activity(self, cycle_num: int, success: bool):
        """记录活动"""
        self._state['last_activity'] = time.time()
        self._state['last_cycle_num'] = cycle_num

        if success:
            self._state['consecutive_failures'] = 0
            self._state['status'] = 'healthy'
        else:
            self._state['consecutive_failures'] += 1
            if self._state['consecutive_failures'] >= self.MAX_CONSECUTIVE_FAILURES:
                self._state['status'] = 'critical'
            elif self._state['consecutive_failures'] >= 3:
                self._state['status'] = 'warning'

        self._save()

    def is_stuck(self) -> bool:
        """是否卡住"""
        elapsed = time.time() - self._state['last_activity']
        return elapsed > self.STUCK_THRESHOLD

    def get_status(self) -> str:
        """获取健康状态"""
        if self.is_stuck():
            return 'stuck'
        return self._state['status']

    def summary(self) -> str:
        """健康摘要"""
        elapsed = time.time() - self._state['last_activity']
        status = self.get_status()
        return (
            f'状态: {status} | '
            f'最后活动: {elapsed:.0f}s前 | '
            f'连续失败: {self._state["consecutive_failures"]} | '
            f'当前循环: #{self._state["last_cycle_num"]}'
        )

    def reset(self):
        """重置健康状态"""
        self._state = {
            'last_activity': time.time(),
            'consecutive_failures': 0,
            'last_cycle_num': 0,
            'status': 'healthy',
        }
        self._save()


class RollbackVerifier:
    """回滚验证：stash 后验证代码状态"""

    def __init__(self):  # STUB: placeholder
        pass

    def verify_clean(self) -> bool:
        """验证工作区是否干净"""
        import subprocess as sp

        r = sp.run(['git', 'status', '--porcelain'], capture_output=True, text=True, cwd=ROOT)
        return r.stdout.strip() == ''

    def verify_no_stash(self) -> bool:
        """验证没有未处理的 stash"""
        import subprocess as sp

        r = sp.run(['git', 'stash', 'list'], capture_output=True, text=True, cwd=ROOT)
        # 检查是否有 agent 自动创建的 stash
        for line in r.stdout.strip().split('\n'):
            if 'agent自动' in line:
                return False
        return True

    def get_stash_list(self) -> List[str]:
        """获取 agent 相关的 stash"""
        import subprocess as sp

        r = sp.run(['git', 'stash', 'list'], capture_output=True, text=True, cwd=ROOT)
        stashes = []
        for line in r.stdout.strip().split('\n'):
            if 'agent自动' in line:
                stashes.append(line.strip())
        return stashes

    def verify_after_rollback(self) -> Dict[str, Any]:
        """回滚后验证"""
        return {
            'clean': self.verify_clean(),
            'agent_stashes': self.get_stash_list(),
            'ok': self.verify_clean() and self.verify_no_stash(),
        }
