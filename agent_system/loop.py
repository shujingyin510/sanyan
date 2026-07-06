"""Agent 主循环（兜底 LLM 循环）—— 从 AgentRuntime 抽出的 run_legacy(rt, ...)。

这是 REFACTOR_PLAN 目标形态里 core/loop.py 的落地：把最长的编排方法 `_run_legacy`
（规则快捷路径 → LLM 多轮循环 → 退化/超时/UR 停止 → 工具执行 → 反思重试）从
`AgentRuntime` 里搬出为**以 rt 为唯一入参**的模块函数；runtime 侧 `_run_legacy` 变薄委托。

**行为与原方法逐位一致**（仅 self.→rt.、位置搬迁，逻辑不动）。当前仍依赖 rt 的约 20 个
属性/私有方法，属"位移建模"——先立起 loop.py 模块边界，后续可逐步收窄 rt 接口。
"""

import os
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
    # SANYAN_SKIP_RULE_GEN（自更新闭环设置）：生成前奏烧 2-4 次 LLM 调用/分钟级延迟，
    # 产物垃圾参数规则本就被下方零改动闸门丢弃——预算全留给主循环
    if rt.rule_engine.llm_fn and not os.environ.get('SANYAN_SKIP_RULE_GEN'):
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
    nudged = False
    # 停机原因如实上报：旧实现所有 break 都落到"已达N轮"——0706 实跑三次面板全谎报
    # （实际分别死于 900s 预算、UR 退化×2），尸检被误导两回。
    stop = ''
    rt.memory['failures'] = rt.memory.get('failures', 0)

    for rnd in range(1, max_rounds + 1):
        # ── UR 退化检测 ──
        if rnd >= 2:
            recent = [str(h.get('result', ''))[:80] for h in rt.memory.get('history', [])[-4:] if 'result' in h]
            if results_degenerate(recent):
                stop = f'连续{len(recent)}轮相同输出，退化停止'
                print(f'  [UR] 连续{len(recent)}轮相同输出 → 退化，强制停止')
                break

        # ── 超时护杀 ──
        # 总预算默认 420s（7 分钟），SANYAN_LOOP_TIME_BUDGET 可调。0705 三连实跑：代理
        # 抖动时单次 LLM 重试吃 60-120s，420s 把三次尝试全掐死在编辑前（零编辑调用）——
        # 自更新闭环放宽到 900s（外层 --agent-timeout 子进程硬杀仍兜底，跑不飞）。
        try:
            budget = int(os.environ.get('SANYAN_LOOP_TIME_BUDGET', '420'))
        except ValueError:
            budget = 420  # 环境值损坏 → 回默认，护杀不失效
        total_elapsed = _time.time() - t_start
        if total_elapsed > budget:
            stop = f'总执行时间超过{budget}秒'
            print(f'  [TIMEOUT] 总执行时间超过{budget}秒，强制退出')
            rt.memory['failures'] += 1
            break
        if rnd > 1 and step_duration_last > 60:
            stop = f'单步耗时{step_duration_last:.0f}秒超限'
            print(f'  [TIMEOUT] 单步耗时{step_duration_last:.0f}秒，强制退出')
            rt.memory['failures'] += 1
            break

        # ── 徘徊顶推（自更新场景，一次性）──
        # 0705 第二轮实录：预算修好后模型 15 轮全在读/搜索（同一段 read_file 反复读了
        # 三遍），一次编辑不做。轮次过半**或时间过半**仍零改动就顶推一把（0706 实录：
        # 代理风暴下轮次走得慢，固定第 8 轮常来不及——预算先烧完）。
        if (
            not nudged
            and os.environ.get('SANYAN_REQUIRE_EDIT')
            and not rt.memory.get('modified')
            and (rnd > max_rounds // 2 or total_elapsed > budget / 2)
        ):
            nudged = True
            print('  [UR] 过半仍零改动 → 顶推：停止阅读，现在动手改文件')
            # 0706 第六轮实录：被顶推后模型的自然反应是"先替换原块"——引用尚不存在的辅助
            # 函数名，毫秒被拒。顶推文案点明顺序：先定义、后替换。
            ctx = rt._build_context(
                f'已用掉一半预算但还没有任何文件修改。停止继续阅读/搜索——你已经看过目标代码了。'
                f'现在就动手，按此顺序：第一步先把辅助函数的完整定义插入目标文件（与原函数平级）；'
                f'第二步再把原块替换成对它的调用。小步即可，外部会验证。原任务：{task}',
                'init',
            )

        # ── 上下文压缩 ──
        if context_too_large(ctx):
            ctx = rt._compress_ctx(ctx)

        # ── LLM 调用 ──
        try:
            raw = rt._llm_call(ctx)
            if isinstance(raw, str) and raw.startswith('error|'):
                # 句柄级彻底失败以哨兵串返回（error|LLM调用失败(3次重试)…），不是模型输出。
                # 曾被当普通文本流进解析：变成幻影 error"工具"烧轮，重复错误文案还把 UR
                # 退化检测毒成早夭（0706 实录 UR=0.45/0.47 在 r5-6 强停、顶推没活到）。
                # 转异常走下方既有失败路径：计连败、快中止、不进 llm_outputs。
                raise RuntimeError(raw[6:][:160] or 'LLM调用失败')
            # ═══ UR 退化检测：在 LLM 文本输出上计算 ═══
            llm_history = rt.memory.setdefault('llm_outputs', [])
            llm_history.append(str(raw)[:200])  # 取前200字符
            ur = llm_output_ur(llm_history)
            if ur is not None:
                stop = f'LLM输出退化 (UR={ur:.2f})'
                print(f'  [UR] LLM输出退化 (UR={ur:.2f})，强制停止')
                rt.memory['failures'] += 1
                break
        except Exception as e:
            llm_consecutive_fails += 1
            print(f'  [LLM] 调用失败 (r={rnd}): {e}')
            if llm_consecutive_fails >= 3:
                stop = f'LLM连续{llm_consecutive_fails}次调用失败'
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
            stop = f'约束违规停止（{tool}）'
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
                stop = f'三态门阻断: {gate.get("reason", "")}'
                break
            if tool in ('write_file', 'replace_in_file', 'replace_lines', 'replace_all') and cog == 'AFFIRM':
                # 只在本步认知为 AFFIRM（真落盘：已替换/已写入）时记改动。失败的替换
                # （未找到/语法错误被守卫还原→UNCERT）不再伪装成"修改文件"：否则面板谎报、
                # 学习器记假风格，⑥ 的零改动顶回也会被这条假记录骗过（尸检实录：r5
                # replace_in_file 判 UNCERT 0.10，面板却写"修改文件: ops/control_ops.py"）。
                from agent_system.agent_tools import param_path

                rt.memory['modified'].append(param_path(params))
        else:
            result = f'未知工具: {tool}'
        # 不再硬编码"成功"——让 UR 退化检测判定是否该停止
        if tool == 'done':
            # ⑥ 自更新场景（SANYAN_REQUIRE_EDIT）：任务必须落到文件改动。零改动 done 是
            # 弱模型的谎报"完成"（oracle 必判无 diff）——顶回并点名去改文件、别 run_shell
            # 数行数，把预算逼向真正的编辑。至多顶两次，仍无改动则停止交回上层判定。
            if os.environ.get('SANYAN_REQUIRE_EDIT') and not rt.memory.get('modified'):
                rt.memory['empty_done'] = rt.memory.get('empty_done', 0) + 1
                if rt.memory['empty_done'] <= 2:
                    print(f'  [UR] done 但零改动（第{rt.memory["empty_done"]}次）→ 顶回：任务要求改文件')
                    ctx = rt._build_context(
                        '你还没有修改任何文件，任务尚未完成。直接用 replace_in_file 或 write_file '
                        '修改目标代码——行数/长度由外部验证，不要用 run_shell 数行数。改完再 done。',
                        tool,
                        result,
                    )
                    continue
                print('  [UR] done 连续零改动顶回仍无进展 → 停止（交回上层判定）')
            elif rnd == 1:
                # 通用兜底：首轮就 done 往往无实质进展，观察一轮
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
    return {'answer': stop or f'已达{max_rounds}轮', 'memory': rt.memory}
