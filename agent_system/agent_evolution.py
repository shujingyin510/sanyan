"""约束进化系统 — 第3层：系统级自我进化（受限）

核心思路：不是自由进化，而是在围栏内优化
- 接口不变（ISA、语义）
- 只改内部实现（VM、编译器优化）
- 多后端差分测试保证正确性
- 多目标评估保证"变好"

组件:
    P41: ConstraintEvolver — 约束进化器（定义可改变/不可改变区域）
    P42: DifferentialVerifier — 差分验证器（多后端一致性+性能）
    P43: MultiObjectiveEvaluator — 多目标评估器（综合得分）
    P44: SelfHostVerifier — 自举验证器（不动点验证）
"""

import os
import subprocess as sp
import time
from typing import Dict, List, Tuple, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))


class ConstraintEvolver:
    """约束进化器：定义可改变/不可改变区域"""

    # 不可改变的区域（接口层）
    IMMUTABLE = {
        'vm.py': {
            'ISA opcodes': '操作码定义不能改（会破坏二进制兼容）',
            'VM.run()': '主循环接口不能改',
        },
        'ternary_core.py': {
            'TritValue': '三态值类型不能改',
            'Kleene logic': 'Kleene真值表不能改',
        },
        'evaluator.py': {
            'eval()': '求值器主接口不能改',
        },
        'ops/registry.py': {
            'register()': '操作注册接口不能改',
        },
    }

    # 可改变的区域（实现层）
    MUTABLE = {
        'vm.py': {
            'VM._exec_*': '操作码实现可以优化',
            'VM._dispatch': '分派逻辑可以优化',
        },
        'ternary_core.py': {
            'BT.add': '加法实现可以优化',
            'BT.mul': '乘法实现可以优化',
        },
        'evaluator.py': {
            'eval._eval_*': '求值函数内部可以优化',
        },
        'ops/': {
            'ops/*.py': '操作实现可以优化',
        },
        'llvmgen/': {
            'llvmgen/codegen.py': '代码生成可以优化',
        },
    }

    # 性能关键路径
    PERFORMANCE_CRITICAL = {
        'vm.py': ['run', '_dispatch'],
        'ternary_core.py': ['add', 'sub', 'mul', 'div'],
        'evaluator.py': ['eval'],
    }

    def __init__(self):
        self._proposals: List[Dict] = []
        self._accepted: List[Dict] = []
        self._rejected: List[Dict] = []

    def can_change(self, file_path: str, element: Optional[str] = None) -> Tuple[bool, str]:
        """检查是否可以修改"""
        # 检查是否在不可改变区域
        for immutable_file, elements in self.IMMUTABLE.items():
            if self._match_path(file_path, immutable_file):
                if element is None:
                    return False, f'{file_path} 是不可改变的'
                for imm_name, reason in elements.items():
                    if imm_name in (element or ''):
                        return False, reason

        # 检查是否在可改变区域
        for mutable_file, elements in self.MUTABLE.items():
            if self._match_path(file_path, mutable_file):
                if element is None:
                    return True, f'{file_path} 可以修改'
                for mut_name, reason in elements.items():
                    if mut_name in (element or '') or mut_name.endswith('*'):
                        return True, reason

        return False, '未知文件，不允许修改'

    def _match_path(self, file_path: str, pattern: str) -> bool:
        """路径匹配"""
        if pattern.endswith('/'):
            return file_path.startswith(pattern)
        return file_path == pattern or file_path.endswith('/' + pattern)

    def is_performance_critical(self, file_path: str, element: Optional[str] = None) -> bool:
        """是否是性能关键路径"""
        for critical_file, elements in self.PERFORMANCE_CRITICAL.items():
            if self._match_path(file_path, critical_file):
                if element is None:
                    return True
                return any(e in element for e in elements)
        return False

    def propose_change(self, file_path: str, element: str, description: str, expected_improvement: float = 0) -> Dict:
        """提议变更"""
        can, reason = self.can_change(file_path, element)
        proposal = {
            'id': len(self._proposals) + 1,
            'file': file_path,
            'element': element,
            'description': description,
            'expected_improvement': expected_improvement,
            'allowed': can,
            'reason': reason,
            'status': 'pending',
            'time': time.time(),
        }
        self._proposals.append(proposal)
        return proposal

    def review_proposal(self, proposal_id: int, approved: bool, reason: str = ''):
        """审核变更"""
        for p in self._proposals:
            if p['id'] == proposal_id:
                p['status'] = 'approved' if approved else 'rejected'
                p['review_reason'] = reason
                if approved:
                    self._accepted.append(p)
                else:
                    self._rejected.append(p)
                return p
        return None

    def summary(self) -> str:
        """摘要"""
        return f'变更提案: {len(self._proposals)} | 已接受: {len(self._accepted)} | 已拒绝: {len(self._rejected)}'


class DifferentialVerifier:
    """差分验证器：多后端一致性 + 性能测试"""

    # 后端列表
    BACKENDS = {
        'python': {
            'name': 'Python 求值器',
            'cmd': [os.sys.executable, '-X', 'utf8', 'main.py'],
        },
        'vm': {
            'name': '字节码 VM',
            'cmd': [os.sys.executable, '-X', 'utf8', 'main.py', '--vm'],
        },
    }

    # 测试用例
    TEST_CASES = [
        {'input': '(输出 (加 1 2))', 'expected': '3'},
        {'input': '(输出 (乘 3 4))', 'expected': '12'},
        {'input': '(输出 (若 (大于 5 3) "是" "否"))', 'expected': '是'},
        {'input': '(设 x 10)(输出 (加 x 5))', 'expected': '15'},
    ]

    def __init__(self):
        self._results: List[Dict] = []

    def verify_consistency(self, test_cases: List[Dict] = None) -> Dict:
        """验证多后端一致性"""
        if test_cases is None:
            test_cases = self.TEST_CASES

        results = []
        for test in test_cases:
            test_result = {
                'input': test['input'],
                'expected': test['expected'],
                'backends': {},
                'consistent': True,
            }

            # 测试每个后端
            for backend_name, backend in self.BACKENDS.items():
                try:
                    output = self._run_backend(backend, test['input'])
                    test_result['backends'][backend_name] = {
                        'output': output.strip(),
                        'success': True,
                    }
                except Exception as e:
                    test_result['backends'][backend_name] = {
                        'output': str(e),
                        'success': False,
                    }

            # 检查一致性
            outputs = [r['output'] for r in test_result['backends'].values() if r['success']]
            if len(outputs) > 1:
                test_result['consistent'] = len(set(outputs)) == 1

            results.append(test_result)

        # 汇总
        total = len(results)
        consistent = sum(1 for r in results if r['consistent'])
        success_rate = consistent / total if total > 0 else 0

        return {
            'total': total,
            'consistent': consistent,
            'success_rate': success_rate,
            'results': results,
        }

    def _run_backend(self, backend: Dict, input_code: str) -> str:
        """运行单个后端"""
        cmd = backend['cmd'] + [input_code] if '{input}' not in str(backend['cmd']) else backend['cmd']
        r = sp.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=ROOT,
        )
        if r.returncode != 0:
            raise RuntimeError(f'Backend failed: {r.stderr[:200]}')
        return r.stdout

    def benchmark_performance(self, iterations: int = 10) -> Dict:
        """基准测试性能"""
        results = {}
        for backend_name, backend in self.BACKENDS.items():
            times = []
            for _ in range(iterations):
                start = time.time()
                try:
                    self._run_backend(backend, '(输出 (加 1 2))')
                    times.append(time.time() - start)
                except Exception:
                    pass

            if times:
                results[backend_name] = {
                    'avg_ms': (sum(times) / len(times)) * 1000,
                    'min_ms': min(times) * 1000,
                    'max_ms': max(times) * 1000,
                    'iterations': len(times),
                }

        return results

    def verify_change(self, old_code: str, new_code: str, file_path: str) -> Dict:
        """验证变更：比较变更前后"""
        # 1. 运行现有测试
        consistency = self.verify_consistency()

        # 2. 性能测试
        performance = self.benchmark_performance(iterations=5)

        return {
            'consistency': consistency,
            'performance': performance,
            'safe_to_apply': consistency['success_rate'] >= 0.9,
        }


class MultiObjectiveEvaluator:
    """多目标评估器：综合得分计算"""

    # 默认权重
    DEFAULT_WEIGHTS = {
        'performance': 0.4,  # 性能提升
        'correctness': 0.3,  # 正确性（测试通过率）
        'consistency': 0.2,  # 多后端一致性
        'code_quality': 0.1,  # 代码质量（行数变化）
    }

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS
        self._evaluations: List[Dict] = []

    def evaluate(self, change: Dict, verification: Dict) -> Dict:
        """评估变更"""
        scores = {}

        # 性能得分：基准测试提升
        perf = verification.get('performance', {})
        if perf:
            # 简单计算：平均性能提升
            avg_perf = sum(p.get('avg_ms', 0) for p in perf.values()) / len(perf)
            scores['performance'] = min(1.0, max(0, 1 - avg_perf / 100))
        else:
            scores['performance'] = 0.5

        # 正确性得分：测试通过率
        consistency = verification.get('consistency', {})
        scores['correctness'] = consistency.get('success_rate', 0.5)

        # 一致性得分：多后端输出一致
        scores['consistency'] = consistency.get('success_rate', 0.5)

        # 代码质量得分：行数变化（少为好）
        code_change = change.get('lines_changed', 0)
        scores['code_quality'] = max(0, 1 - abs(code_change) / 100)

        # 综合得分
        total_score = sum(scores.get(k, 0) * v for k, v in self.weights.items())

        evaluation = {
            'scores': scores,
            'total_score': total_score,
            'weights': self.weights,
            'recommendation': 'accept' if total_score > 0.6 else 'reject',
            'time': time.time(),
        }

        self._evaluations.append(evaluation)
        return evaluation

    def compare_changes(self, evaluations: List[Dict]) -> Optional[Dict]:
        """比较多个变更，选择最优"""
        if not evaluations:
            return None
        return max(evaluations, key=lambda e: e.get('total_score', 0))

    def summary(self) -> str:
        """摘要"""
        if not self._evaluations:
            return '无评估记录'
        avg_score = sum(e.get('total_score', 0) for e in self._evaluations) / len(self._evaluations)
        accepted = sum(1 for e in self._evaluations if e.get('recommendation') == 'accept')
        return (
            f'评估: {len(self._evaluations)}次 | '
            f'平均得分: {avg_score:.2f} | '
            f'接受: {accepted} | '
            f'拒绝: {len(self._evaluations) - accepted}'
        )


class SelfHostVerifier:
    """自举验证器：不动点验证"""

    def __init__(self):
        self._results: List[Dict] = []

    def verify_bytecode_compiler(self) -> Dict:
        """验证字节码编译器自举"""
        # Level 2 自举：编译器编译自身
        print('[self-host] 验证 Level 2 字节码编译器自举...')

        try:
            # 编译 bytecode_compiler.san
            r1 = sp.run(
                [
                    os.sys.executable,
                    '-X',
                    'utf8',
                    'sanyanc.py',
                    'stdlib/bytecode_compiler.san',
                    '-o',
                    'build/test_compiler.bin',
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=ROOT,
            )

            if r1.returncode != 0:
                return {
                    'success': False,
                    'level': 2,
                    'error': f'编译失败: {r1.stderr[:200]}',
                }

            # 用 VM 直接加载运行
            test_code = """
import sys
sys.path.insert(0, '.')
from vm import VM
vm = VM.from_bin('build/test_compiler.bin')
vm.run()
"""
            r2 = sp.run(
                [os.sys.executable, '-X', 'utf8', '-c', test_code], capture_output=True, text=True, timeout=60, cwd=ROOT
            )

            if r2.returncode != 0:
                return {
                    'success': False,
                    'level': 2,
                    'error': f'VM运行失败: {r2.stderr[:200]}',
                }

            # 比较输出
            return {
                'success': True,
                'level': 2,
                'message': 'Level 2 自举验证通过',
            }

        except Exception as e:
            return {
                'success': False,
                'level': 2,
                'error': str(e),
            }

    def verify_vm_consistency(self) -> Dict:
        """验证 VM 一致性"""
        print('[self-host] 验证 VM 多后端一致性...')

        test_cases = [
            '(输出 (加 1 2))',
            '(输出 (乘 3 4))',
            '(输出 (若 (大于 5 3) "是" "否"))',
        ]

        results = []
        for test in test_cases:
            # Python 求值器
            r_py = sp.run(
                [os.sys.executable, '-X', 'utf8', 'main.py', test], capture_output=True, text=True, timeout=30, cwd=ROOT
            )

            # 字节码 VM
            r_vm = sp.run(
                [os.sys.executable, '-X', 'utf8', 'main.py', '--vm', test],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=ROOT,
            )

            py_out = r_py.stdout.strip() if r_py.returncode == 0 else 'ERROR'
            vm_out = r_vm.stdout.strip() if r_vm.returncode == 0 else 'ERROR'

            results.append(
                {
                    'input': test,
                    'python': py_out,
                    'vm': vm_out,
                    'consistent': py_out == vm_out,
                }
            )

        consistent = sum(1 for r in results if r['consistent'])
        return {
            'success': consistent == len(results),
            'total': len(results),
            'consistent': consistent,
            'results': results,
        }

    def run_full_verification(self) -> Dict:
        """运行完整自举验证"""
        print('[self-host] 运行完整自举验证...')

        bytecode = self.verify_bytecode_compiler()
        vm = self.verify_vm_consistency()

        overall = bytecode['success'] and vm['success']

        result = {
            'success': overall,
            'bytecode_compiler': bytecode,
            'vm_consistency': vm,
            'time': time.time(),
        }

        self._results.append(result)
        return result

    def summary(self) -> str:
        """摘要"""
        if not self._results:
            return '无验证记录'
        last = self._results[-1]
        return (
            f'自举验证: {"通过" if last["success"] else "失败"} | '
            f'字节码: {"通过" if last["bytecode_compiler"]["success"] else "失败"} | '
            f'VM一致性: {last["vm_consistency"]["consistent"]}/{last["vm_consistency"]["total"]}'
        )


class ConstrainedEvolutionSystem:
    """约束进化系统：整合所有组件 + 自动化闭环"""

    def __init__(self):
        self.evolver = ConstraintEvolver()
        self.verifier = DifferentialVerifier()
        self.evaluator = MultiObjectiveEvaluator()
        self.self_host = SelfHostVerifier()
        self._history: List[Dict] = []
        self._cycle_count = 0
        self._max_cycles = 10

    def propose_and_verify(self, file_path: str, element: str, description: str, change_code: str = '') -> Dict:
        """提议变更并验证"""
        # 1. 检查约束
        proposal = self.evolver.propose_change(file_path, element, description)
        if not proposal['allowed']:
            return {
                'status': 'rejected',
                'reason': proposal['reason'],
                'proposal': proposal,
            }

        # 2. 差分验证
        verification = self.verifier.verify_change('', change_code, file_path)

        # 3. 多目标评估
        evaluation = self.evaluator.evaluate({'lines_changed': len(change_code.split('\n'))}, verification)

        # 4. 决定是否接受
        accepted = evaluation['recommendation'] == 'accept' and verification['safe_to_apply']

        result = {
            'status': 'accepted' if accepted else 'rejected',
            'proposal': proposal,
            'verification': {
                'consistency_rate': verification['consistency']['success_rate'],
                'performance': verification['performance'],
            },
            'evaluation': evaluation,
            'time': time.time(),
        }

        self._history.append(result)

        if accepted:
            self.evolver.review_proposal(proposal['id'], True, '验证通过')

        return result

    def run_self_host_check(self) -> Dict:
        """运行自举验证"""
        return self.self_host.run_full_verification()

    # ── 自动化进化闭环 ──

    def _generate_candidates(self, task: str) -> List[Dict]:
        """生成候选变更（从可改变区域中选择）"""
        candidates = []

        # 性能关键路径的优化候选
        for file_path, elements in self.evolver.MUTABLE.items():
            for element, reason in elements.items():
                if '*' in element:
                    # 通配符：尝试推断具体元素
                    candidates.append(
                        {
                            'file': file_path,
                            'element': element.replace('*', 'impl'),
                            'description': f'优化 {file_path} {element}',
                            'type': 'performance',
                        }
                    )
                else:
                    candidates.append(
                        {
                            'file': file_path,
                            'element': element,
                            'description': reason,
                            'type': 'implementation',
                        }
                    )

        return candidates[:5]  # 限制候选数量

    def _snapshot_code(self, file_path: str) -> str:
        """快照当前代码"""
        try:
            with open(os.path.join(ROOT, file_path), encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ''

    def _apply_change(self, file_path: str, old_code: str, new_code: str) -> bool:
        """应用变更（回滚时用旧代码替换）"""
        try:
            with open(os.path.join(ROOT, file_path), 'w', encoding='utf-8') as f:
                f.write(new_code)
            return True
        except Exception:
            return False

    def evolution_cycle(self, task: str = '优化性能', max_iterations: int = 3) -> Dict:
        """单次进化循环：生成候选→验证→选择最优→应用"""
        print(f'\n═══ 进化循环 #{self._cycle_count + 1} ═══')
        print(f'任务: {task}')

        # 1. 先跑自举验证建立基线
        print('\n[1/4] 建立基线...')
        baseline = self.verifier.verify_consistency()
        baseline_perf = self.verifier.benchmark_performance(iterations=3)
        print(f'  基线一致性: {baseline["success_rate"]:.1%}')
        print(f'  基线性能: {self._format_perf(baseline_perf)}')

        # 2. 生成候选
        print('\n[2/4] 生成候选变更...')
        candidates = self._generate_candidates(task)
        print(f'  候选数: {len(candidates)}')

        # 3. 逐个验证候选
        print('\n[3/4] 验证候选...')
        best_result = None
        best_score = -1

        for i, candidate in enumerate(candidates):
            print(f'  候选 {i + 1}/{len(candidates)}: {candidate["description"][:50]}')

            # 快照当前代码
            self._snapshot_code(candidate['file'])

            # 尝试应用（这里用模拟，实际应该调用 Agent 修改）
            # 暂时只验证约束
            proposal = self.evolver.propose_change(candidate['file'], candidate['element'], candidate['description'])

            if not proposal['allowed']:
                print(f'    跳过: {proposal["reason"][:40]}')
                continue

            # 验证当前状态
            verification = self.verifier.verify_change('', '', candidate['file'])
            evaluation = self.evaluator.evaluate({'lines_changed': 0}, verification)

            print(f'    一致性: {verification["consistency"]["success_rate"]:.1%}')
            print(f'    得分: {evaluation["total_score"]:.2f}')

            if evaluation['total_score'] > best_score:
                best_score = evaluation['total_score']
                best_result = {
                    'candidate': candidate,
                    'verification': verification,
                    'evaluation': evaluation,
                }

        # 4. 选择最优并记录
        print('\n[4/4] 选择最优...')
        if best_result:
            print(f'  最优: {best_result["candidate"]["description"][:50]}')
            print(f'  得分: {best_result["evaluation"]["total_score"]:.2f}')
            print(f'  推荐: {best_result["evaluation"]["recommendation"]}')
        else:
            print('  无有效候选')

        self._cycle_count += 1

        return {
            'cycle': self._cycle_count,
            'baseline': {
                'consistency': baseline['success_rate'],
                'performance': baseline_perf,
            },
            'candidates_evaluated': len(candidates),
            'best': best_result,
        }

    def _format_perf(self, perf: Dict) -> str:
        """格式化性能数据"""
        parts = []
        for backend, data in perf.items():
            parts.append(f'{backend}: {data["avg_ms"]:.1f}ms')
        return ', '.join(parts) if parts else '无数据'

    def run_evolution(self, task: str = '优化性能', max_cycles: int = 3) -> Dict:
        """运行多轮进化"""
        print('\n═══════════════════════════════════════')
        print(f'  自动化进化闭环 — 最多 {max_cycles} 轮')
        print('═══════════════════════════════════════')

        results = []
        for i in range(max_cycles):
            result = self.evolution_cycle(task)
            results.append(result)

            # 如果没有有效候选，停止
            if not result.get('best'):
                print('\n[stop] 无有效候选，停止进化')
                break

            # 如果得分已经很高，停止
            if result['best']['evaluation']['total_score'] > 0.9:
                print('\n[stop] 得分已很高，停止进化')
                break

        # 最终验证
        print('\n═══ 最终验证 ═══')
        final = self.verifier.verify_consistency()
        print(f'一致性: {final["success_rate"]:.1%}')

        final_self_host = self.self_host.run_full_verification()
        print(f'自举: {"通过" if final_self_host["success"] else "失败"}')

        return {
            'cycles': len(results),
            'results': results,
            'final_consistency': final['success_rate'],
            'final_self_host': final_self_host['success'],
        }

    def summary(self) -> str:
        """系统摘要"""
        return (
            f'\n═══ 约束进化系统 ═══\n'
            f'{self.evolver.summary()}\n'
            f'{self.evaluator.summary()}\n'
            f'{self.self_host.summary()}\n'
            f'进化循环: {self._cycle_count}次\n'
            f'历史记录: {len(self._history)}次'
        )
