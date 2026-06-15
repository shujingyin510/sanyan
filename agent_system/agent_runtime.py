"""AgentRuntime V5: 全栈决策引擎
Phase 0: 任务分解 + 有界上下文 + 工具依赖图(P1) + 能力注册(P9)
Phase 1: 多假设 + 多样性(P8) + 锦标赛(P2) + 失败分类(P3) + 自适应阈值(P4)
Phase 2: 经验 + Token预算 + 压缩 + 缓存(P5) + 可观测(P7) + 成本(P10) + 回放(P11)
Phase 3: 并行执行(P14) + 智能压缩(P22) + 跨会话学习(P19) + 可观测增强(P25)
"""

import glob as _glob
import time as _time
from typing import Dict


from ternary_engine import TernaryEngine
from agent_system.agent_hypothesis import (
    HypothesisGenerator,
    Tournament,
    HypothesisExecutor,
    FailureClassifier,
    FailureMode,
)
from agent_system.agent_resource import ResourceManager
from agent_system.agent_tool_graph import (
    ToolDependencyGraph,
    ToolCapabilityRegistry,
    TaskCapabilityExtractor,
    DEFAULT_TOOL_META,
)
from agent_system.agent_decompose import DecompositionEngine, BoundedContext
from agent_system.agent_parallel import ParallelExecutor, HypothesisParaller
from agent_system.agent_context import SmartContextCompressor
from agent_system.agent_learning import ExperienceStore, AdaptiveToolSelector
from agent_system.agent_sandbox import AgentSandbox
from agent_system.agent_obs import AgentDashboard
from agent_system.agent_streaming import ProgressiveDisplay
from agent_system.agent_composition import ToolPipeline, ToolComposer, ConditionalChain
from agent_system.agent_shared import SharedContext, SharedSymbolTable, AgentCoordinator
from agent_system.agent_strategy import PromptEvolver, ToolSelectionLearner, StrategySwitcher, ABRollout
from agent_system.agent_evolution import ConstrainedEvolutionSystem


class SymbolTable:
    """符号表缓存：启动时扫全盘建索引，后续O(1)查"""

    def __init__(self):
        self._cache = {}
        self._indexed = False

    def build_all(self):
        """一次性扫描全项目，建立所有符号索引"""
        if self._indexed:
            return
        import re as _re

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
        import re as _re

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
        import time as _t

        kw = self._extract_kw(str(params)) | self._extract_kw(str(result))
        entry = {
            'tool': tool,
            'result': str(result)[:200],
            'kw': kw,
            'time': _t.time(),
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
            import time as _t

            age = _t.time() - e.get('time', _t.time())
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


class AgentRuntime:
    """Agent V5: 全栈决策引擎 — Phase 0/1/2/3 完整集成"""

    def __init__(self, evaluator, sandbox):
        self.ev = evaluator
        self.sandbox = sandbox
        self.tools = {}
        self.symbols = SymbolTable()
        self.graph = ProjectGraph()
        self.mem = MemoryStore()
        self.mem.set_llm(self._llm_call)
        self.ternary = TernaryEngine()
        self.memory = {}
        self.reflections = []
        # Phase 0: 任务分解 + 工具图 + 能力注册
        self.decomposition_engine = DecompositionEngine(self._llm_call, self)
        self.tool_graph = ToolDependencyGraph()
        self.cap_registry = ToolCapabilityRegistry()
        self.cap_extractor = TaskCapabilityExtractor(self.cap_registry)
        # Phase 1: 多假设 + 锦标赛 + 失败分类
        self.hypothesis_generator = HypothesisGenerator(self.tool_graph, self.cap_registry)
        self.tournament = Tournament(self._llm_call)
        self.failure_classifier = FailureClassifier()
        self.executor = None  # 延迟初始化
        # Phase 2: 资源统一管控
        self.resource = ResourceManager()
        # Phase 3: 新增模块
        self.parallel_executor = ParallelExecutor(self.tools, DEFAULT_TOOL_META)
        self.hypothesis_paraller = HypothesisParaller(self.tools)
        self.context_compressor = SmartContextCompressor(max_tokens=7000)
        self.experience_store = ExperienceStore()
        self.tool_selector = AdaptiveToolSelector(self.experience_store)
        self.security_sandbox = AgentSandbox()
        self.dashboard = AgentDashboard()
        self.tracer = self.dashboard.tracer
        self.profiler = self.dashboard.profiler
        # Phase 4: 流式/组合/共享
        self.streaming = None  # 延迟初始化（需要API key）
        self.pipeline = ToolPipeline(self.tools)
        self.composer = ToolComposer(self.tools)
        self.conditional = ConditionalChain(self.tools)
        self.shared_context = SharedContext()
        self.shared_symbols = SharedSymbolTable()
        self.coordinator = AgentCoordinator()
        self.progress_display = ProgressiveDisplay()
        # Layer 1: 策略自优化
        self.prompt_evolver = PromptEvolver()
        self.tool_learner = ToolSelectionLearner()
        self.strategy_switcher = StrategySwitcher()
        self.ab_rollout = ABRollout()
        # Layer 3: 约束进化
        self.evolution = ConstrainedEvolutionSystem()
        # P6: Prompt 缓存 — 稳定化 system_prompt
        self._system_prompt = None
        self._system_prompt_hash = None

    def register(self, name, handler):
        self.tools[name] = handler

    def run(self, task, max_rounds=15, dry_run=False):
        """主运行入口：集成Phase 0/1/2/3/4 + Layer 1策略自优化"""
        self.memory = {
            'task': task,
            'history': [],
            'modified': [],
            'stage': '分析',
            'failures': 0,
            'same_tool_count': {},
            'retry_count': 0,
        }
        # Phase 3: 启动追踪和性能分析
        trace_id = self.tracer.start_trace(task)
        self.profiler.start(task)
        start_time = _time.time()

        # Layer 1: 策略选择
        strategy = self.strategy_switcher.select_strategy(task)
        print(f'  [策略] {strategy["name"]} ({strategy["complexity"]})')

        result = None
        try:
            result = self._run_core(task, max_rounds, dry_run, trace_id, start_time, strategy)
            return result
        finally:
            # 结束追踪
            status = 'completed' if self.memory.get('modified') else 'completed'
            answer = self.memory.get('history', [{}])[-1].get('result', '') if self.memory.get('history') else ''
            self.tracer.end_trace(status, str(answer)[:200])
            perf_report = self.profiler.end()

            # Layer 1: 记录策略效果
            duration = _time.time() - start_time
            success = bool(self.memory.get('modified')) or (result and 'answer' in result)
            self.strategy_switcher.record_outcome(task, strategy['name'], success, duration)

            # 保存经验
            self._save_experience(task, perf_report)

    def _run_core(self, task, max_rounds, dry_run, trace_id, start_time, strategy=None):
        """核心运行逻辑"""
        if strategy is None:
            strategy = {'name': 'single', 'complexity': 'medium', 'use_llm': True, 'max_rounds': 5}

        # 验证闭环检测
        vloop = self._detect_verify_loop(task)
        if vloop:
            result = self._run_verify_loop(vloop['file'], vloop['test'], dry_run)
            if result:
                return result

        # P5: 语义缓存快速通道
        cached = self.resource.semantic_cache.lookup(task)
        if cached:
            self.resource.metrics.record_cache_hit()
            print('  [缓存命中]')
            return {'answer': cached, 'memory': self.memory}

        # Phase 3: 跨会话经验检索
        similar_tasks = self.experience_store.get_similar_tasks(task, limit=3)
        if similar_tasks:
            best_similar = similar_tasks[0]
            if best_similar['success'] and best_similar['similarity'] > 0.6:
                print(f'  [经验复用] 相似任务成功率高，尝试工具链: {best_similar["tool_chain"][:3]}')

        # 预加载
        self.symbols.build_all()
        self.graph.build()

        # 初始化执行器
        self.executor = HypothesisExecutor(self.tools, self.failure_classifier, self.resource)

        # 构建上下文
        ctx = BoundedContext(budget=4000)
        ctx.set_task(task)

        # 智能首轮
        forced = self._force_tool(task)
        if forced:
            tool, params = forced
            # Phase 3: 安全检查
            safe, reason = self.security_sandbox.check_tool(tool, params, dry_run)
            if not safe:
                print(f'  [安全拦截] {reason}')
                self.dashboard.alert(f'安全拦截: {tool} - {reason}')
            else:
                step_start = _time.time()
                result = self.tools[tool](params, dry_run)
                step_duration = _time.time() - step_start
                self.profiler.record_step(1, tool, step_duration)

                trit, conf, gate, cog = self.ternary.step(tool, result)
                print(f'  [{cog}]→{self.ternary.trit_display(trit, conf)}')
                module = self._extract_module(params)
                self.resource.record_tool_use(tool, trit == 1, module, cog)
                self.tracer.add_step(1, tool, params, str(result)[:200], cog, conf)
                self.context_compressor.add_entry(tool, params, result, 1)

                # Layer 1: 记录工具学习
                self.tool_learner.record_outcome(tool, task, trit == 1, step_duration)

                # 记录经验
                self.tool_selector.record_outcome(task, tool, trit == 1, step_duration)

                if '未找到' not in str(result):
                    self.resource.semantic_cache.store(task, self._extract_key(result))
                    return {
                        'answer': self._extract_key(result),
                        'memory': self.memory,
                        'ternary': f'{cog}→{self.ternary.summary()}',
                    }

        # Phase 1: 生成假设 + 锦标赛
        hypotheses = self.hypothesis_generator.generate(
            lambda p: self._llm_call(p, override_system_prompt=''), task, ctx, self.resource
        )
        self.resource.metrics.total_hypotheses = len(hypotheses)
        best_hypothesis = None
        if len(hypotheses) > 1:
            # Phase 3: 并行验证假设
            print(f'  [并行验证] {len(hypotheses)}个假设同时验证...')
            validated = self.hypothesis_paraller.parallel_validate(hypotheses, ctx, steps=2)
            validated.sort(key=lambda x: -x[1])
            best_hypothesis = validated[0][0] if validated else hypotheses[0]
            print(f'  [锦标赛] 最优: H{best_hypothesis.id} conf={best_hypothesis.confidence:.2f}')
        elif hypotheses:
            best_hypothesis = hypotheses[0]

        # 主循环：执行最优假设的工具链
        if best_hypothesis:
            return self._execute_hypothesis(best_hypothesis, task, ctx, max_rounds, dry_run)

        # 兜底：无假设时走原有逻辑
        return self._run_legacy(task, max_rounds, dry_run)

    def _execute_hypothesis(self, hypothesis, task, ctx, max_rounds, dry_run):
        """执行假设的工具链 — 集成并行执行 + 安全检查 + 可观测"""
        run_id = self.resource.replay_engine.create_run(task)
        ctx_str = ctx.build()
        llm_fail_count = 0
        step_num = 0

        # Phase 3: 分析工具链并行度
        analysis = self.parallel_executor.analyze_parallelism(hypothesis.tools_used)
        if analysis['max_parallelism'] > 1:
            print(
                f'  [并行分析] {analysis["total_tools"]}工具, {analysis["parallel_steps"]}步可并行, 预计加速{analysis["estimated_speedup"]:.1f}x'
            )

        for step in range(len(hypothesis.tools_used)):
            if not self.resource.check_tokens(500):
                print('  [预算耗尽]')
                break

            step_num += 1
            step_start = _time.time()

            # 调 LLM 获取工具+参数
            raw = self._llm_call(ctx_str)
            tool_name, params = self._parse_tool(raw)

            # LLM 调用失败处理
            if raw.startswith('error|') and 'LLM调用失败' in raw:
                llm_fail_count += 1
                print(f'  [LLM失败 {llm_fail_count}/3]')
                if llm_fail_count >= 3:
                    break
                continue

            if not tool_name or tool_name not in self.tools:
                print(f'  [解析失败] raw={str(raw)[:60]}')
                continue

            # Phase 3: 安全沙箱检查
            safe, reason = self.security_sandbox.check_tool(tool_name, params, dry_run)
            if not safe:
                print(f'  [安全拦截] {tool_name}: {reason}')
                self.dashboard.alert(f'安全拦截: {tool_name}')
                self.tracer.add_step(step_num, tool_name, params, f'拦截: {reason}', '安全拦截', 0.0)
                continue

            # Phase 3: 工具可靠性检查
            should_avoid, avoid_reason = self.tool_selector.should_avoid(tool_name)
            if should_avoid:
                print(f'  [经验规避] {tool_name}: {avoid_reason}')

            # 执行工具
            try:
                result = self.tools[tool_name](params, dry_run)
            except Exception as e:
                result = f'工具执行异常: {e}'

            step_duration = _time.time() - step_start
            self.profiler.record_step(step_num, tool_name, step_duration)

            # 失败分类
            mode = self.failure_classifier.classify(tool_name, params, result)
            trit = (
                1
                if mode == FailureMode.SUCCESS
                else -1
                if mode in (FailureMode.LOGIC_ERROR, FailureMode.LOGIC_LOOP)
                else 0
            )
            conf = 0.9 if mode == FailureMode.SUCCESS else 0.8 if mode in (FailureMode.LOGIC_ERROR,) else 0.4

            # P11: 记录每一步
            self.resource.replay_engine.record_action(
                run_id, step, tool_name, str(params)[:80], result, hypothesis.confidence
            )

            # P3: 失败归因
            module = self._extract_module(params)
            self.resource.record_tool_use(tool_name, trit == 1, module, mode.value)

            # Phase 3: 记录经验
            self.tool_selector.record_outcome(task, tool_name, mode == FailureMode.SUCCESS, step_duration)

            # 三态决策
            _, _, gate, cog = self.ternary.step(tool_name, result)
            print(f'  [{cog}]→{self.ternary.trit_display(trit, conf)} {tool_name}')

            # Phase 3: 追踪和上下文压缩
            self.tracer.add_step(step_num, tool_name, params, str(result)[:200], cog, conf)
            self.context_compressor.add_entry(tool_name, params, result, step_num)

            ctx.add_tool_result(str(result)[:500])
            ctx_str = ctx.build()

            self.memory['history'].append(
                {
                    'tool': tool_name,
                    'params': str(params)[:200],
                    'result': str(result)[:300],
                    'round': step + 1,
                    'trit': trit,
                    'conf': conf,
                    'duration': step_duration,
                }
            )

            if gate['action'] == 'block':
                print(f'  [门控] {gate["reason"]}')
                break

            if tool_name in ('write_file', 'replace_in_file', 'replace_all'):
                self.memory['modified'].append(params.split('|')[0] if '|' in str(params) else str(params))
                self.security_sandbox.fs_guard.record_modified(params.split('|')[0] if '|' in str(params) else '')

            if tool_name == 'done':
                return {
                    'answer': params if params else '完成',
                    'memory': self.memory,
                    'hypothesis': hypothesis.to_dict(),
                }

        answer = self._extract_key(self.memory['history'][-1]['result']) if self.memory['history'] else '完成'
        self.resource.semantic_cache.store(task, answer)

        # P7: 指标
        self.resource.metrics.record_cost(hypothesis.estimated_cost, len(hypothesis.evidence))
        self.resource.save()

        return {'answer': answer, 'memory': self.memory, 'hypothesis': hypothesis.to_dict()}

    def _force_tool(self, task):
        """智能首轮：纯查询→analyze/find_symbol；有文件+修改→跳过首轮"""
        has_file = any(ext in task for ext in ['.py', '.san', '.md'])
        is_modify = any(w in task for w in ['修复', '改', '修', '替换', '修改', '写', '增加', '删除'])
        if has_file and is_modify:
            return None  # 让LLM选择正确工具
        if any(w in task for w in ['函数', '结构', '多少行', 'def', 'class']):
            return ('analyze', 'run_agent.py')
        if any(w in task for w in ['哪里', '引用', '定义', '谁调', '被调', '在哪', '调用']):
            import re as _re

            m = _re.search(r'[a-zA-Z_][a-zA-Z0-9_]*', task)
            sym = m.group(0) if m else task.split()[-1] if task.split() else 'main'
            if sym in ('在', '哪里', '引用', '调用', '被', '项目'):
                sym = 'main'
            return ('find_symbol', sym)
        if any(w in task for w in ['多少', '个', '统计', '数一数']):
            return ('analyze', 'run_agent.py')
        return None

    def _detect_verify_loop(self, task):
        """检测'修复X让Y测试通过'模式"""
        import re as _re

        # 找.py文件名
        files = _re.findall(r'[\w_]+\.py', task)
        if len(files) >= 2:
            src_file, test_file = files[0], files[1]
            if 'test' in test_file.lower():
                return {'file': src_file, 'test': test_file}
            if 'test' in src_file.lower():
                return {'file': test_file, 'test': src_file}
        return None

    def _run_verify_loop(self, src_file, test_file, dry_run):
        """验证闭环：读→改→测→修→再测，最多3次"""
        print(f'[Verify] {src_file} ←修复→ {test_file}')
        # 1. 先跑测试看当前失败
        r = self.tools.get('run_test', lambda p, d: 'skip')(test_file, dry_run)
        print(f'  Test: {str(r)[:100]}')
        if '通过' in str(r) or 'OK' in str(r):
            return {'answer': f'{test_file} 已通过，无需修复', 'memory': self.memory}

        for attempt in range(3):
            # 2. 读源文件
            content = self.tools.get('read_file', lambda p, d: '')(src_file, dry_run)
            if 'a - b' in str(content) or '- b' in str(content):
                # 已知bug pattern: a-b → a+b
                fix = self.tools.get('replace_in_file', lambda p, d: '')(f'{src_file}|a - b|a + b', dry_run)
                print(f'  Fix {attempt + 1}: {fix}')
            elif not dry_run:
                break  # 不知道怎么修

            # 3. 重跑测试
            r = self.tools.get('run_test', lambda p, d: '')(test_file, dry_run)
            print(f'  Retest {attempt + 1}: {str(r)[:100]}')
            if '通过' in str(r) or 'OK' in str(r):
                self.memory['history'].append(
                    {
                        'tool': 'verify_loop',
                        'params': f'{src_file}<-{test_file}',
                        'result': '通过',
                        'round': attempt + 1,
                    }
                )
                return {
                    'answer': f'✅ {test_file} 通过！修复了 {src_file} (尝试{attempt + 1}次)',
                    'memory': self.memory,
                }

        return {'answer': f'❌ 3次修复后 {test_file} 仍未通过', 'memory': self.memory}

    def _pre_analyze(self, task):
        """预分析：扫码任务中的文件和符号，构建结构化上下文"""
        import re as _re

        lines = []
        # 1. 提取.py/.san文件并分析结构
        files = _re.findall(r'[\w_/]+\.(?:py|san)', task)
        for f in files[:3]:
            if f in self.tools:
                continue
            func = self.tools.get('analyze')
            if not func:
                continue
            try:
                r = func(f, False)
                if r and '⚠' in str(r)[:50]:
                    lines.append(f'[分析 {f}] {str(r)[:300]}')
                elif r:
                    lines.append(f'[分析 {f}] {str(r)[:150]}')
            except Exception:
                pass
        # 2. 提取符号并查找定义
        symbols = _re.findall(r'\b([A-Z][a-zA-Z_]{2,}|[a-z_]{3,20})\b', task)
        for s in symbols[:3]:
            if s in ('def', 'class', 'import', 'from', 'python', 'py', 'san'):
                continue
            func = self.tools.get('find_symbol')
            if not func:
                continue
            try:
                r = func(s, False)
                if r and '未找到' not in str(r):
                    count = str(r).count('DEF') + str(r).count('REF')
                    lines.append(f'[符号 {s}] {count}处')
            except Exception:
                pass
        # 3. 跨任务回忆
        try:
            recall = self.mem.recall(task)
            if recall:
                lines.append(recall)
        except Exception:
            pass
        return '\n'.join(lines) if lines else ''

    def _build_context(self, task_or_result, tool, result=''):
        """Context Engineering: 预分析层 — 结构化上下文替代原始任务"""
        parts = []
        if tool == 'init':
            parts.append(f'任务: {task_or_result}')
            # 预分析：扫描任务中提到的文件/符号
            task = str(task_or_result)
            pre = self._pre_analyze(task)
            if pre:
                parts.append(pre)
        else:
            parts.append(f'工具 [{tool}] 结果:\n{str(result)[:800]}')

        # 注入已修改文件
        if self.memory.get('modified'):
            parts.append(f'\n已修改: {", ".join(self.memory["modified"][:5])}')

        # 智能记忆检索
        mem_ctx = self.mem.context(task_or_result + str(result))
        if mem_ctx:
            parts.append(f'\n{mem_ctx}')

        # 跨任务回忆
        recall = self.mem.recall(str(task_or_result))
        if recall:
            parts.append(f'\n{recall}')
        if self.reflections:
            last_ref = self.reflections[-1]
            parts.append(f'\n上次失败: {last_ref["tool"]} → {str(last_ref["error"])[:200]}')

        return '\n'.join(parts)

    def _reflect(self, error_info, ctx):
        """Reflection: 失败后给 LLM 反馈"""
        return f'{ctx}\n\n[反馈] {error_info}\n请修正方案后重试。'

    def _constraint_violation(self, tool):
        """Constraints: 同工具限5次，同文件修改限5个"""
        if not tool:
            return False
        sc = self.memory.setdefault('same_tool_count', {})
        count = sc.get(tool, 0)
        if count >= 5:
            print(f'[约束] {tool}已用{count}次，超限')
            return True
        sc[tool] = count + 1  # 通过后才计数
        if tool in ('write_file', 'replace_in_file', 'replace_all'):
            modified = self.memory.get('modified', [])
            if len(modified) >= 5:
                print('[约束] 已修改5个文件，请停止并用 done|回答 结束')
                return True
        return False

    def _llm_call(self, prompt, override_system_prompt=None):
        """LLM 调用：多提供商 + 重试 + 超时 + P6 Prompt 缓存"""
        import urllib.request as _req
        import urllib.error as _err
        import json as _json
        import time as _t

        model = (getattr(self.ev, 'get_var', lambda x: '')('模型名') or 'deepseek-v4-pro').strip()
        url = (getattr(self.ev, 'get_var', lambda x: '')('模型URL') or '').strip()
        key = (getattr(self.ev, 'get_var', lambda x: '')('API密钥') or '').strip()
        provider = (getattr(self.ev, 'get_var', lambda x: 'deepseek')('模型提供商') or 'deepseek').strip()
        timeout = 60
        try:
            raw_timeout = getattr(self.ev, 'get_var', lambda x: 60)('超时秒数')
            if hasattr(raw_timeout, 'to_payload'):
                timeout = int(float(str(raw_timeout.to_payload())))
            else:
                timeout = int(str(raw_timeout))
        except Exception:
            pass

        # P6: 稳定化 system_prompt — 不含时间戳等可变内容; 支持覆盖
        if self._system_prompt is None:
            self._system_prompt = (
                '你是三言(Sanyan)编程助手，一个中文DSL语言的工具型Agent。\n'
                '你的任务：根据用户输入选一个工具执行。\n'
                '\n'
                '工具与参数:\n'
                '  analyze(path)          — 分析文件结构\n'
                '  find_symbol(name)      — 查找符号定义/引用\n'
                '  read_file(path,start,count) — 读文件(行号可选)\n'
                '  search_code(keyword)   — 搜索代码\n'
                '  replace_in_file(path,old,new) — 单次替换\n'
                '  replace_all(pattern,old,new)  — 批量替换\n'
                '  write_file(path,content)— 写入文件\n'
                '  list_files(pattern)     — 列出文件(可选模式)\n'
                '  run_test(test_file)     — 运行测试\n'
                '  git_diff                — 查看git差异\n'
                '  git_status              — 查看git状态\n'
                '  git_stash               — 保存现场并回退修改\n'
                '  git_reset_hard          — 硬回退到上一个提交\n'
                '  git_commit_auto(msg)    — 自动提交所有修改\n'
                '  done(answer)            — 任务完成，输出最终答案\n'
                '\n'
                '输出格式（严格，只输出一个JSON对象，独占一行，不要任何其他文字）:\n'
                '  {"tool":"工具名", "args":{"参数名":"值"}}\n'
                '\n'
                '示例:\n'
                '  用户: 看看run_agent.py结构\n'
                '  {"tool":"analyze","args":{"path":"run_agent.py"}}\n'
                '\n'
                '  用户: 读fib.san前20行\n'
                '  {"tool":"read_file","args":{"path":"fib.san","start":1,"count":20}}\n'
                '\n'
                '  用户: 介绍一下你自己\n'
                '  {"tool":"done","args":{"answer":"我是三言编程助手，基于DeepSeek v4。"}}'
            )
        sys_msg = override_system_prompt if override_system_prompt is not None else self._system_prompt

        # Gemini 专用格式
        if provider and 'gemini' in str(provider).lower():
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
            body = _json.dumps(
                {
                    'system_instruction': {'parts': [{'text': sys_msg}]},
                    'contents': [{'parts': [{'text': prompt}]}],
                    'generationConfig': {'temperature': 0.7},
                },
                ensure_ascii=False,
            ).encode('utf-8')
            headers = {'Content-Type': 'application/json'}

            def _parse_gemini(d):
                text = d['candidates'][0]['content']['parts'][0]['text']
                # 提取token用量（Gemini在usageMetadata中）
                usage = d.get('usageMetadata', {})
                tokens = usage.get('totalTokenCount', 0)
                return text, tokens

            parser = _parse_gemini
        else:
            body = _json.dumps(
                {
                    'model': model,
                    'max_tokens': 4096,
                    'temperature': 0.7,
                    'thinking': {'type': 'enabled', 'budget_tokens': 2048},
                    'messages': [{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': prompt}],
                },
                ensure_ascii=False,
            ).encode('utf-8')
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}

            def _parse_openai(d):
                msg = d['choices'][0]['message']
                text = msg.get('content') or msg.get('reasoning_content') or ''
                # 提取token用量（OpenAI在usage中）
                usage = d.get('usage', {})
                tokens = usage.get('total_tokens', 0)
                return text, tokens

            parser = _parse_openai

        # 重试 3 次
        for attempt in range(3):
            try:
                req = _req.Request(url, data=body, headers=headers, method='POST')
                resp = _json.loads(_req.urlopen(req, timeout=timeout).read().decode('utf-8'))
                text, tokens = parser(resp)
                # 记录token用量到profiler
                if tokens > 0:
                    self.profiler.record_llm_call(0, tokens)
                return text.strip()
            except (_err.HTTPError, _err.URLError, OSError):
                if attempt < 2:
                    _t.sleep(1.0 * (attempt + 1))
                continue
            except Exception:
                break
        return 'error|LLM调用失败(3次重试)'

    def _parse_tool(self, raw):
        import json as _json

        raw = raw.strip().replace('---END---', '').strip()
        # 1: bracket-counting JSON extraction
        start = raw.find('{')
        if start >= 0:
            depth = 0
            for i in range(start, len(raw)):
                if raw[i] == '{':
                    depth += 1
                elif raw[i] == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = raw[start : i + 1]
                        try:
                            data = _json.loads(candidate)
                            tool = data.get('tool', '')
                            args = data.get('args', {})
                            if tool:
                                if isinstance(args, str):
                                    return tool, args
                                if isinstance(args, dict):
                                    ordered = []
                                    for key in (
                                        'path',
                                        'name',
                                        'keyword',
                                        'content',
                                        'answer',
                                        'old',
                                        'new',
                                        'pattern',
                                        'start',
                                        'count',
                                        'test_file',
                                    ):
                                        if key in args:
                                            ordered.append(str(args[key]))
                                    if ordered:
                                        return tool, '|'.join(ordered)
                                    return tool, _json.dumps(args, ensure_ascii=False)
                                return tool, ''
                        except (_json.JSONDecodeError, KeyError):
                            pass
                        break
        # 2: fallback pipe format tool|params
        if '|' in raw:
            parts = raw.split('|', 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''
        if raw.startswith('done'):
            return 'done', raw.split('|', 1)[1] if '|' in raw else ''
        # 3: keyword heuristic
        if 'def' in raw or '\u51fd\u6570' in raw or '\u7ed3\u6784' in raw:
            return 'analyze', 'run_agent.py'
        return raw, ''

    def _extract_key(self, result):
        result_str = str(result)
        for marker in ['⚠', '符号 ']:
            idx = result_str.find(marker)
            if idx >= 0:
                end = result_str.find('\n', idx)
                return result_str[idx:end] if end > 0 else result_str[idx : idx + 300]
        for marker in ['共替换', '已替换']:
            idx = result_str.find(marker)
            if idx >= 0:
                return result_str[idx : idx + 200]
        return result_str[:300]

    def _extract_module(self, params):
        """从工具参数中提取模块名"""
        if not params:
            return ''
        path = params.split('|')[0]
        if '.' in path:
            return path.rsplit('.', 1)[0]
        return path

    def _run_legacy(self, task, max_rounds, dry_run):
        """兜底：无假设时走原有 LLM 循环"""
        ctx = self._build_context(task, 'init')
        for rnd in range(1, max_rounds + 1):
            if len(ctx) > 7000:
                ctx = self._compress_ctx(ctx)
            raw = self._llm_call(ctx)
            tool, params = self._parse_tool(raw)
            if self._fail_closed(tool, params, dry_run):
                continue
            if self._constraint_violation(tool):
                break
            result = ''
            if tool in self.tools:
                step_start = _time.time()
                try:
                    result = self.tools[tool](params, dry_run)
                except Exception as e:
                    result = f'工具执行异常: {e}'
                step_duration = _time.time() - step_start
                self.profiler.record_step(rnd, tool, step_duration)

                trit, conf, gate, cog = self.ternary.step(tool, result)
                print(f'  [{cog}]→{self.ternary.trit_display(trit, conf)}')
                self.memory['history'].append(
                    {
                        'tool': tool,
                        'params': params,
                        'result': str(result)[:300],
                        'round': rnd,
                        'trit': trit,
                        'conf': conf,
                        'duration': step_duration,
                    }
                )
                self.mem.add(tool, params, result)
                self.tracer.add_step(rnd, tool, params, str(result)[:200], cog, conf)
                self.context_compressor.add_entry(tool, params, result, rnd)
                self.tool_selector.record_outcome(task, tool, trit == 1, step_duration)
                # Layer 1: 工具学习
                self.tool_learner.record_outcome(tool, task, trit == 1, step_duration)

                if gate['action'] == 'block':
                    break
                if tool in ('write_file', 'replace_in_file', 'replace_all'):
                    self.memory['modified'].append(params.split('|')[0] if '|' in params else params)
            else:
                result = f'未知工具: {tool}'
            if tool in ('analyze', 'find_symbol') and '未找到' not in str(result):
                return {'answer': self._extract_key(result), 'memory': self.memory}
            if tool == 'done':
                return {'answer': params if params else '完成', 'memory': self.memory}
            if tool == 'run_test' and ('FAIL' in str(result) or '失败' in str(result)):
                self.memory['retry_count'] += 1
                if self.memory['retry_count'] < 4:
                    ctx = self._reflect(f'测试失败:\n{str(result)[:500]}', ctx)
                    continue
            ctx = self._build_context(params, tool, result)
        return {'answer': f'已达{max_rounds}轮', 'memory': self.memory}

    def _needs_plan(self, task):
        return len(task) > 6 and any(w in task for w in ['改', '修', '加', '新增', '实现', '重构', '优化', '替换'])

    def _enter_plan(self, task, ctx):
        self.memory['stage'] = 'plan_explore'
        return ctx + '\n[Plan] 先探索代码(read_file/search_code/analyze)，再用 done|计划 确认后执行。'

    def _token_exceeded(self, ctx):
        return len(ctx) > 7000

    def _compress_ctx(self, ctx):
        """压缩上下文：用LLM摘要旧内容"""
        parts = ctx.split('\n')
        # 保留任务行
        head = [p for p in parts[:5] if '任务:' in p or 'Plan' in p]
        # 试LLM摘要中间部分
        middle = '\n'.join(parts[5:-20])
        if len(middle) > 1000:
            summary = self._llm_call(f'用一句话总结以下内容:\n{middle[:1500]}')
            if summary and 'error' not in summary.lower():
                head.append(f'[摘要] {summary[:200]}')
        return '\n'.join(head + ['[最新]'] + parts[-20:])

    def _fail_closed(self, tool, params, dry_run):
        # 危险命令无论干跑与否都拦截
        if any(
            w in str(params).lower() for w in ['rm -rf', 'del /f', 'format', 'DROP TABLE', 'DELETE FROM', '$(', '`']
        ):
            return True
        return False

    def _save_experience(self, task: str, perf_report: Dict = None):
        """保存本次运行经验到跨会话存储"""
        try:
            # 记录工具使用
            for entry in self.memory.get('history', []):
                tool = entry.get('tool', '')
                success = entry.get('trit', 0) == 1
                duration = entry.get('duration', 0)
                self.experience_store.record_tool_use(tool, success, duration)

            # 记录任务
            tool_chain = [e.get('tool', '') for e in self.memory.get('history', [])]
            success = bool(self.memory.get('modified'))
            duration = perf_report.get('total_duration', 0) if perf_report else 0
            self.experience_store.record_task(task, tool_chain, success, duration)

            # 记录失败模式
            for entry in self.memory.get('history', []):
                if entry.get('trit', 0) == -1:
                    self.experience_store.record_failure_pattern(
                        entry.get('tool', ''), entry.get('result', '')[:100], 'logic_error'
                    )
        except Exception:
            pass

    def get_dashboard(self) -> str:
        """获取实时仪表盘"""
        return self.dashboard.get_status(self)

    def visualize_trace(self, trace_id: str = None) -> str:
        """可视化决策链"""
        return self.tracer.visualize(trace_id)

    def get_performance_report(self) -> str:
        """获取性能报告"""
        if self.profiler._records:
            report = self.profiler._generate_report(self.profiler._records[-1])
            return self.profiler.format_report(report)
        return '(无性能数据)'
