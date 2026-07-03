"""Agent 主循环（兜底 LLM 循环）—— 从 AgentRuntime 抽出的 run_legacy(rt, ...)。

这是 REFACTOR_PLAN 目标形态里 core/loop.py 的落地：把最长的编排方法 `_run_legacy`
（规则快捷路径 → LLM 多轮循环 → 退化/超时/UR 停止 → 工具执行 → 反思重试）从
`AgentRuntime` 里搬出为**以 rt 为唯一入参**的模块函数；runtime 侧 `_run_legacy` 变薄委托。

**行为与原方法逐位一致**（仅 self.→rt.、位置搬迁，逻辑不动）。当前仍依赖 rt 的约 20 个
属性/私有方法，属"位移建模"——先立起 loop.py 模块边界，后续可逐步收窄 rt 接口。
"""

import time as _time

from agent_system.loop_policy import context_too_large, llm_output_ur, results_degenerate


def run_legacy(rt, task, max_rounds, dry_run):
    """兜底：无假设时走原有 LLM 循环"""
    # ── dry_run 快速路径：跳过 LLM，直接执行强制工具 ──
    if dry_run:
        forced = rt._force_tool(task)
        if forced:
            tool, params = forced
            if tool in rt.tools:
                result = rt.tools[tool](params, dry_run)
                rt.ternary.step(tool, result)
                rt.memory['history'].append(
                    {
                        'tool': tool,
                        'params': params,
                        'result': str(result)[:300],
                        'round': 1,
                        'trit': 1,
                        'conf': 0.9,
                    }
                )
                return {'answer': rt._extract_key(result), 'memory': rt.memory}
        return {'answer': 'dry_run完成', 'memory': rt.memory}

    # ── 规则引擎：先查规则，有规则直接执行 ──
    rule = rt.rule_engine.match_rule(task)
    if rule:
        print(f'  [规则] 匹配: {rule.name}')
        return rt._execute_rule(task, rule, dry_run)

    # ── 无匹配规则：尝试 LLM 生成新规则并立即执行 ──
    if rt.rule_engine.llm_fn:
        print('  [规则] 无匹配规则，尝试生成...')
        new_rule = rt.rule_engine.generate_rule(task)
        if new_rule:
            print(f'  [规则] 生成并执行: {new_rule.name}')
            print(f'  [规则] 工具链: {[s["tool"] for s in new_rule.steps]}')
            # 立即执行生成的规则
            from agent_system.agent_execution import RuleExecutor

            executor = RuleExecutor(
                tools=rt.tools,
                rule_engine=rt.rule_engine,
                template_manager=rt.template_manager,
                llm_call=rt._llm_call,
                memory=rt.memory,
            )
            result = executor.execute_rule(task, new_rule, dry_run)
            result['auto_rule'] = new_rule.name
            if rt.memory.get('modified'):
                return result
            # 生成规则的步骤参数常含未绑定模板（{func} 等垃圾参数）：跑完零改动
            # 还可能 done 谎报"完成"（P2 首跑实测：劫持整轮、oracle 判无 diff）。
            # 零文件改动不收工，落回下方 LLM 多轮循环真正干活。
            print('  [规则] 生成规则执行零改动 → 回退 LLM 多轮循环')

    ctx = rt._build_context(task, 'init')
    t_start = _time.time()
    llm_consecutive_fails = 0
    step_duration_last = 0.0
    rt.memory['failures'] = rt.memory.get('failures', 0)

    for rnd in range(1, max_rounds + 1):
        # ── UR 退化检测 ──
        if rnd >= 2:
            recent = [str(h.get('result', ''))[:80] for h in rt.memory.get('history', [])[-4:] if 'result' in h]
            if results_degenerate(recent):
                print(f'  [UR] 连续{len(recent)}轮相同输出 → 退化，强制停止')
                break

        # ── 超时护杀 ──
        total_elapsed = _time.time() - t_start
        if total_elapsed > 300:  # 总超时5分钟
            print('  [TIMEOUT] 总执行时间超过300秒，强制退出')
            rt.memory['failures'] += 1
            break
        if rnd > 1 and step_duration_last > 60:
            print(f'  [TIMEOUT] 单步耗时{step_duration_last:.0f}秒，强制退出')
            rt.memory['failures'] += 1
            break

        # ── 上下文压缩 ──
        if context_too_large(ctx):
            ctx = rt._compress_ctx(ctx)

        # ── LLM 调用 ──
        try:
            raw = rt._llm_call(ctx)
            # ═══ UR 退化检测：在 LLM 文本输出上计算 ═══
            llm_history = rt.memory.setdefault('llm_outputs', [])
            llm_history.append(str(raw)[:200])  # 取前200字符
            ur = llm_output_ur(llm_history)
            if ur is not None:
                print(f'  [UR] LLM输出退化 (UR={ur:.2f})，强制停止')
                rt.memory['failures'] += 1
                break
        except Exception as e:
            llm_consecutive_fails += 1
            print(f'  [LLM] 调用失败 (r={rnd}): {e}')
            if llm_consecutive_fails >= 3:
                print(f'  [LLM] 连续{llm_consecutive_fails}次调用失败，退出')
                rt.memory['failures'] += 1
                break
            continue
        else:
            llm_consecutive_fails = 0

        tool, params = rt._parse_tool(raw)
        if tool is None:
            rt.memory['failures'] += 1
            print(f'  [PARSE] LLM返回格式错误 (r={rnd}): {str(raw)[:100]}')
            continue

        print(f'  [r{rnd}] 工具={tool} 参数={str(params)[:60]}')

        if rt._fail_closed(tool, params, dry_run):
            continue
        if rt._constraint_violation(tool):
            break
        result = ''
        if tool in rt.tools:
            step_start = _time.time()
            try:
                result = rt.tools[tool](params, dry_run)
            except Exception as e:
                result = f'工具执行异常: {e}'
                rt.memory['failures'] += 1
            step_duration = _time.time() - step_start
            step_duration_last = step_duration
            rt.profiler.record_step(rnd, tool, step_duration)

            trit, conf, gate, cog = rt.ternary.step(tool, result)
            print(f'  [{cog}]→{rt.ternary.trit_display(trit, conf)}')
            rt.memory['history'].append(
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
            rt.mem.add(tool, params, result)
            rt.tracer.add_step(rnd, tool, params, str(result)[:200], cog, conf)
            rt.context_compressor.add_entry(tool, params, result, rnd)
            rt.tool_selector.record_outcome(task, tool, trit == 1, step_duration)

            if gate['action'] == 'block':
                break
            if tool in ('write_file', 'replace_in_file', 'replace_all'):
                from agent_system.agent_tools import param_path

                rt.memory['modified'].append(param_path(params))
        else:
            result = f'未知工具: {tool}'
        # 不再硬编码"成功"——让 UR 退化检测判定是否该停止
        if tool == 'done':
            # UR 保护：第一轮就 done 说明无实质进展，继续观察
            if rnd == 1:
                print('  [UR] 首轮done → 可能无实质进展，继续观察')
                ctx = rt._build_context(params, tool, result)
                continue
            calibrated_answer = params if params else '完成'
            try:
                from agent_system.truth_calibration import get_calibrator

                r = get_calibrator().calibrate(str(params), rt.memory.get('task', ''))
                if r.uncertainty in ('high',):
                    calibrated_answer = f'{params}  [校准: 置信度 {r.confidence:.2f}]'
            except Exception:
                pass
            return {'answer': calibrated_answer, 'memory': rt.memory}
        if tool == 'run_test' and rt._test_failed(result):
            rt.memory['retry_count'] += 1
            if rt.memory['retry_count'] < 4:
                ctx = rt._reflect(f'测试失败:\n{str(result)[:500]}', ctx)
                continue
        ctx = rt._build_context(params, tool, result)
    return {'answer': f'已达{max_rounds}轮', 'memory': rt.memory}
