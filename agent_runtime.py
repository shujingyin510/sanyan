"""AgentRuntime V3: 全栈决策引擎
SymbolTable缓存 + MemoryStore检索 + ProjectGraph + Planner + Reflection + Constraints
+ TernaryEngine: 三态决策 — Kleene传播 + 贝叶斯置信度 + 保护门控
"""
import re, glob as _glob

# ====== TernaryEngine: 三态决策核心 ======

class TernaryEngine:
    """三态决策引擎：移植自 decision.san
    
    每步工具调用 → cog分类 → 三态映射(-1/0/1) → Kleene传播 → 置信度衰减 → 保护门控
    """
    COG_MAP = {'AFFIRM': 1, 'NEGATE': -1}
    COG_NAMES = {'AFFIRM': '确信', 'NEGATE': '拒绝', 'UNCERT': '不确定', 'CONFLICTED': '矛盾', 'PENDING': '待定'}
    TRIT_NAMES = {1: '真', -1: '假', 0: '可能'}
    KLEENE = {
        (-1, -1): -1, (-1, 0): -1, (-1, 1): -1,
        (0, -1): -1, (0, 0): 0, (0, 1): 0,
        (1, -1): -1, (1, 0): 0, (1, 1): 1,
    }
    TOOL_CONFIDENCE = {
        'analyze': 0.90, 'find_symbol': 0.85, 'read_file': 0.90,
        'search_code': 0.85, 'replace_in_file': 0.60, 'replace_all': 0.50,
        'write_file': 0.50, 'run_test': 0.80, 'git_diff': 0.90, 'git_status': 0.90,
        'done': 1.0
    }
    
    def __init__(self, max_hesitation=3, min_gain=0.05):
        self.history = []  # [(trit, confidence)]
        self.hesitation = 0
        self.max_hesitation = max_hesitation
        self.min_gain = min_gain
    
    def classify(self, tool, result, scene_risk='低'):
        """工具执行后分类认知态"""
        result_str = str(result).lower()
        if '未找到' in result_str or 'error' in result_str:
            return 'NEGATE'
        if '⚠' in str(result) or '通过' in str(result) or 'ok' in str(result):
            return 'AFFIRM'
        if 'fail' in result_str or '失败' in result_str or '错误' in result_str:
            return 'NEGATE'
        # 修改类工具成功 → AFFIRM
        if tool in ('replace_in_file', 'replace_all', 'write_file'):
            return 'AFFIRM' if '已' in str(result) or '共' in str(result) else 'UNCERT'
        return 'AFFIRM'
    
    def map_trit(self, cog):
        return self.COG_MAP.get(cog, 0)
    
    def propagate(self, upstream_trit, current_trit):
        return self.KLEENE.get((upstream_trit, current_trit), current_trit)
    
    def confidence(self, cog, tool=''):
        base = {'AFFIRM': 0.9, 'NEGATE': 0.85, 'UNCERT': 0.4}.get(cog, 0.5)
        tool_conf = self.TOOL_CONFIDENCE.get(tool, 0.7)
        return min(0.99, max(0.01, base * tool_conf))
    
    def propagate_confidence(self, upstream_conf, current_conf):
        return min(0.99, max(0.01, upstream_conf * current_conf))
    
    def protect(self, risk, trit, confidence, history):
        if risk == '高' and trit <= 0:
            return {'action': 'block', 'reason': '高风险+不确定=拒绝', 'conf': confidence}
        if self.hesitation >= self.max_hesitation:
            vote = self._majority(history)
            return {'action': 'block', 'reason': f'犹豫{self.hesitation}次', 'vote': vote, 'conf': confidence}
        # 增益计算
        if history:
            hist_avg = sum(c for _, c in history[-5:]) / min(len(history), 5)
            gain = abs(confidence - hist_avg)
            if gain < self.min_gain:
                return {'action': 'continue', 'reason': '信息增益不足', 'conf': confidence}
        return {'action': 'continue', 'reason': '', 'conf': confidence}
    
    def step(self, tool, result, risk='低'):
        """执行一步三态决策，返回 (trit, conf, gate_action)"""
        cog = self.classify(tool, result, risk)
        trit = self.map_trit(cog)
        conf = self.confidence(cog, tool)
        
        upstream_trit = 1
        upstream_conf = 1.0
        if self.history:
            upstream_trit, upstream_conf = self.history[-1]
        
        propagated = self.propagate(upstream_trit, trit)
        propagated_conf = self.propagate_confidence(upstream_conf, conf)
        
        if trit == 0:
            self.hesitation += 1
        
        gate = self.protect(risk, propagated, propagated_conf, self.history)
        self.history.append((propagated, propagated_conf))
        
        return propagated, propagated_conf, gate, cog
    
    def _majority(self, hist):
        true_count = sum(1 for t, _ in hist if t == 1)
        false_count = sum(1 for t, _ in hist if t == -1)
        if true_count > false_count: return 1
        if false_count > true_count: return -1
        return 0
    
    def summary(self):
        if not self.history:
            return '无记录'
        last_trit, last_conf = self.history[-1]
        name = self.TRIT_NAMES.get(last_trit, '?')
        return f'{name}({last_conf:.2f})'
    
    def trit_display(self, trit, conf):
        bars = {-1: '○○○', 0: '◐◐◐', 1: '●●●'}
        return f'{self.TRIT_NAMES.get(trit, "?")} {bars.get(trit, "???")} [{conf:.2f}]'

class SymbolTable:
    """符号表缓存：查一次，全局复用"""
    def __init__(self):
        self._cache = {}  # symbol → {'def': [(file,line)], 'ref': [(file,line)]}
    
    def lookup(self, symbol):
        if symbol in self._cache:
            return self._cache[symbol]
        import glob as _glob
        defs, refs = [], []
        for ext in ['*.py', '*.san']:
            for fp in _glob.glob('**/' + ext, recursive=True):
                if '__pycache__' in fp: continue
                try:
                    with open(fp, encoding='utf-8', errors='ignore') as fh:
                        for lineno, line in enumerate(fh, 1):
                            if f'def {symbol}(' in line or f'class {symbol}' in line or f'定义 {symbol}' in line:
                                defs.append((fp, lineno))
                            elif symbol in line and 'import' not in line.lower():
                                refs.append((fp, lineno))
                except Exception: pass
                if len(defs) + len(refs) > 30: break
        self._cache[symbol] = {'def': defs[:10], 'ref': refs[:20]}
        return self._cache[symbol]
    
    def preload(self, task):
        """从任务中预提取符号并缓存"""
        import re as _re
        for m in _re.finditer(r'[a-zA-Z_][a-zA-Z0-9_]{1,20}', task):
            sym = m.group(0)
            if sym not in ('def', 'class', 'import', 'from', 'if', 'else', 'self', 'True', 'False'):
                self.lookup(sym)

class MemoryStore:
    """智能记忆检索：关键词匹配，非全量dump"""
    def __init__(self):
        self.entries = []
    def add(self, tool, params, result):
        import re as _re
        kw = _re.findall(r'[a-zA-Z_]\w{2,}', str(params) + str(result))
        self.entries.append({'tool': tool, 'result': str(result)[:200], 'kw': set(kw)})
    def context(self, query='', limit=3):
        if not self.entries: return ''
        qk = set(self._kw(query)) if query else set()
        scored = []
        for e in self.entries[-20:]:
            s = len(qk & e.get('kw', set())) if qk else 1
            if s > 0: scored.append((s, e))
        scored.sort(key=lambda x: -x[0])
        entries = [e for _, e in scored[:limit]] or self.entries[-limit:]
        return '[记忆] ' + ' | '.join(f'{e["tool"]}:{str(e["result"])[:60]}' for e in entries)
    def _kw(self, text):
        import re as _re
        return _re.findall(r'[a-zA-Z_]\w{2,}', text)

class ProjectGraph:
    """项目图：文件依赖关系"""
    def __init__(self, root='.'):
        self.deps = {}  # file → [imported_files]
        self._built = False
    
    def build(self, files=None):
        if self._built: return
        import glob as _glob
        files = files or _glob.glob('**/*.py', recursive=True)[:100]
        for fp in files:
            if '__pycache__' in fp: continue
            try:
                with open(fp, encoding='utf-8', errors='ignore') as fh:
                    deps = []
                    for line in fh:
                        if line.startswith('from ') or line.startswith('import '):
                            deps.append(line.strip()[:60])
                        if len(deps) > 10: break
                    if deps:
                        self.deps[fp] = deps
            except Exception: pass
        self._built = True
    
    def depends_on(self, file):
        return self.deps.get(file, [])

class AgentRuntime:
    """Agent V3: SymbolTable + ContextEngineering + Planner + Reflection"""
    def __init__(self, evaluator, sandbox):
        self.ev = evaluator; self.sandbox = sandbox
        self.tools = {}; self.symbols = SymbolTable()
        self.graph = ProjectGraph(); self.mem = MemoryStore()
        self.ternary = TernaryEngine()  # 三态决策引擎
        self.memory = {}; self.reflections = []
    
    def register(self, name, handler):
        self.tools[name] = handler
    
    def run(self, task, max_rounds=15, dry_run=False):
        self.memory = {
            'task': task, 'history': [], 'modified': [], 'stage': '分析',
            'failures': 0, 'same_tool_count': {}, 'retry_count': 0
        }
        # 预加载符号 + 项目图
        self.symbols.preload(task)
        self.graph.build()
        # 构建初始上下文
        ctx = self._build_context(task, 'init')
        # 智能首轮：检测任务类型 → 直接走对应工具
        forced = self._force_tool(task)
        if forced:
            tool, params = forced
            result = self.tools[tool](params, dry_run)
            trit, conf, gate, cog = self.ternary.step(tool, result)
            print(f'  [{cog}]→{self.ternary.trit_display(trit, conf)}')
            if '未找到' not in str(result):
                return {'answer': self._extract_key(result), 'memory': self.memory, 'ternary': f'{cog}→{self.ternary.summary()}'}
        
        for rnd in range(1, max_rounds + 1):
            if self._token_exceeded(ctx):
                ctx = self._compress_ctx(ctx)
            raw = self._llm_call(ctx)
            tool, params = self._parse_tool(raw)
            if self._fail_closed(tool, params, dry_run):
                ctx = self._reflect('操作被安全门控拦截: ' + tool, ctx)
                continue
            
            # Constraints
            if self._constraint_violation(tool):
                ctx = self._reflect(f'约束: {tool}已达上限', ctx)
                continue
            
            # Execute
            result = ''
            if tool in self.tools:
                try:
                    result = self.tools[tool](params, dry_run)
                except Exception as e:
                    result = f'工具执行异常: {e}'
                    self.reflections.append({'round': rnd, 'tool': tool, 'error': str(e)[:300]})
                # 三态决策：每步工具调用后评估
                trit, conf, gate, cog = self.ternary.step(tool, result)
                print(f'  [{cog}]→{self.ternary.trit_display(trit, conf)} {self.ternary.summary()}')
                if gate['action'] == 'block':
                    print(f'  [门控] {gate["reason"]}')
                    break
                self.memory['history'].append({'tool': tool, 'params': params, 'result': str(result)[:300], 'round': rnd, 'trit': trit, 'conf': conf})
                self.mem.add(tool, params, result)
                if tool in ('write_file', 'replace_in_file', 'replace_all'):
                    self.memory['modified'].append(params.split('|')[0] if '|' in params else params)
            else:
                result = f'未知工具: {tool}'
            
            # Auto-complete hooks
            if tool in ('analyze', 'find_symbol') and '未找到' not in str(result):
                return {'answer': self._extract_key(result), 'memory': self.memory}
            if tool == 'done':
                return {'answer': params if params else '完成', 'memory': self.memory}
            
            # Reflection: run_test failed?
            if tool == 'run_test' and ('FAIL' in str(result) or '失败' in str(result)):
                self.reflections.append({'round': rnd, 'tool': tool, 'error': str(result)[:300]})
                self.memory['retry_count'] += 1
                if self.memory['retry_count'] < 4:
                    ctx = self._reflect(f'测试失败:\n{str(result)[:500]}', ctx)
                    continue
            
            # 修改后未测试 → 自动后续
            if tool in ('write_file', 'replace_in_file', 'replace_all'):
                has_test = any(h['tool'] == 'run_test' for h in self.memory['history'])
                if not has_test:
                    ctx += f'\n[系统] 代码已修改，请run_test验证。'
            
            # Context Engineering: 注入选中的符号信息
            ctx = self._build_context(params, tool, result)
            
        return {'answer': f'已达{max_rounds}轮', 'memory': self.memory}
    
    def _force_tool(self, task):
        """智能首轮：根据任务类型直接选工具"""
        if any(w in task for w in ['函数','结构','多少行','def','class']):
            return ('analyze', 'run_agent.py')
        if any(w in task for w in ['哪里','引用','定义','谁调','被调','在哪','调用']):
            import re as _re
            m = _re.search(r'[a-zA-Z_][a-zA-Z0-9_]*', task)
            sym = m.group(0) if m else task.split()[-1] if task.split() else 'main'
            if sym in ('在','哪里','引用','调用','被','项目'): sym = 'main'
            return ('find_symbol', sym)
        if any(w in task for w in ['多少','个','统计','数一数']):
            return ('analyze', 'run_agent.py')
        return None

    def _build_context(self, task_or_result, tool, result=''):
        """Context Engineering: 组装最小但足够的上下文"""
        parts = []
        if tool == 'init':
            parts.append(f'任务: {task_or_result}')
        else:
            parts.append(f'工具 [{tool}] 结果:\n{str(result)[:800]}')
        
        # 注入已修改文件
        if self.memory.get('modified'):
            parts.append(f'\n已修改: {", ".join(self.memory["modified"][:5])}')
        
        # 智能记忆检索
        mem_ctx = self.mem.context(task_or_result + str(result))
        if mem_ctx:
            parts.append(f'\n{mem_ctx}')
        
        # 注入 Reflection
        if self.reflections:
            last_ref = self.reflections[-1]
            parts.append(f'\n上次失败: {last_ref["tool"]} → {str(last_ref["error"])[:200]}')
        
        return '\n'.join(parts)
    
    def _reflect(self, error_info, ctx):
        """Reflection: 失败后给 LLM 反馈"""
        return f'{ctx}\n\n[反馈] {error_info}\n请修正方案后重试。'
    
    def _constraint_violation(self, tool):
        """Constraints: 同工具限5次，同文件修改限5个"""
        if not tool: return False
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
    
    def _llm_call(self, prompt):
        try:
            model = str(getattr(self.ev, 'get_var', lambda x: 'deepseek-chat')('模型名')).strip()
            url = str(getattr(self.ev, 'get_var', lambda x: '')('模型URL')).strip()
            key = str(getattr(self.ev, 'get_var', lambda x: '')('API密钥')).strip()
            import urllib.request as _req, json as _json
            sys_msg = '可用工具: analyze(查文件结构), find_symbol(查符号), read_file(读文件|起始行|结束行), search_code(搜索), replace_in_file(单替换 路径|旧|新), replace_all(批量 模式|旧|新), write_file(写 路径|内容), list_files(列), run_test(测试), git_diff(git差异), git_status(git状态), done(完成|回答)。\n只输出: tool|params。如 analyze|run_agent.py'
            body = _json.dumps({'model': model, 'messages': [
                {'role': 'system', 'content': sys_msg},
                {'role': 'user', 'content': prompt}
            ], 'temperature': 0.7, 'max_tokens': 256}, ensure_ascii=False).encode('utf-8')
            req = _req.Request(url, data=body, headers={
                'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}, method='POST')
            return _json.loads(_req.urlopen(req, timeout=60).read().decode('utf-8'))['choices'][0]['message']['content'].strip()
        except Exception as e:
            return f'error|{e}'
    
    def _parse_tool(self, raw):
        raw = raw.strip().replace('---END---', '').strip('{}"\' ')
        if '|' in raw:
            parts = raw.split('|', 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''
        if raw.startswith('done'): return 'done', raw.split('|', 1)[1] if '|' in raw else ''
        # 智能首轮: 检测任务类型
        if 'def' in raw or '函数' in raw or '结构' in raw: return 'analyze', 'run_agent.py'
        return raw, ''
    
    def _extract_key(self, result):
        result_str = str(result)
        for marker in ['⚠', '共替换', '已替换', '符号 ']:
            idx = result_str.find(marker)
            if idx >= 0:
                return result_str[idx:idx+200]
        return result_str[:200]
    
    def _needs_plan(self, task):
        return len(task) > 6 and any(w in task for w in ['改','修','加','新增','实现','重构','优化','替换'])

    def _enter_plan(self, task, ctx):
        self.memory['stage'] = 'plan_explore'
        return ctx + '\n[Plan] 先探索代码(read_file/search_code/analyze)，再用 done|计划 确认后执行。'

    def _token_exceeded(self, ctx):
        return len(ctx) > 7000
    
    def _compress_ctx(self, ctx):
        parts = ctx.split('\n')
        head = [p for p in parts[:10] if '任务:' in p or 'Plan' in p]
        return '(上下文已压缩)\n' + '\n'.join(head + parts[-30:])
    
    def _fail_closed(self, tool, params, dry_run):
        # 危险命令无论干跑与否都拦截
        if any(w in str(params).lower() for w in ['rm -rf', 'del /f', 'format', 'DROP TABLE', 'DELETE FROM', '$(', '`']):
            return True
        return False
