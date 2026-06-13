"""Agent 项目引擎 — 分解 → 执行 → 验证 → 反馈 → 上报"""

import os
import re
import time
import json
import subprocess
import difflib
import glob
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class ProjectTask:
    name: str
    description: str
    tools: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    validation: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    feedback: str = ""
    retries: int = 0
    max_retries: int = 3


@dataclass
class ProjectResult:
    success: bool
    tasks: list[ProjectTask]
    summary: str


class ProjectOrchestrator:

    def __init__(self, rt=None, tools=None):
        self.rt = rt
        self.tools = tools or {}
        self.memory = {}
        self.errors = []

    def _llm_decompose(self, spec):
        if self.rt and self.rt.decomposition_engine:
            try:
                result = self.rt.decomposition_engine.decompose(spec)
                if result:
                    items = result if isinstance(result, list) else [result]
                    return [ProjectTask(name=it.get("name", "task"), description=it.get("desc", spec)) for it in items]
            except Exception as e:
                self.errors.append(f"decompose failed: {e}")
        return self._rule_decompose(spec)

    def _rule_decompose(self, spec):
        tasks = []
        for kw, (desc, tools) in {
            "写": ("实现代码", ["write_file"]), "定义": ("定义函数", ["write_file"]),
            "编译": ("编译验证", ["run_test"]), "测试": ("运行测试", ["run_test"]),
        }.items():
            if kw in spec:
                tasks.append(ProjectTask(name=desc, description=spec, tools=tools,
                    depends_on=[t.name for t in tasks[-1:]] if tasks else []))
        return tasks or [ProjectTask(name="实现", description=spec, tools=["write_file", "run_test"])]

    def _execute_task(self, task):
        task.status = TaskStatus.RUNNING
        try:
            from agent_tools import _spawn_sub_agent
            name = "proj_" + task.name.replace(" ", "_")[:20]
            r = _spawn_sub_agent("name=" + name + "\ntask=" + task.description)
            task.result = str(r)[:500]
        except Exception as e:
            task.result = "agent error: " + str(e)[:200]
        if not self._validate(task):
            task.status = TaskStatus.FAILED
            return False
        task.status = TaskStatus.DONE
        return True

    def _validate(self, task):
        if not task.validation:
            return True
        try:
            r = subprocess.run(task.validation.split() if isinstance(task.validation, str) else task.validation,
                capture_output=True, text=True, timeout=30, cwd=".")
            combined = (r.stdout + r.stderr).strip()
            if r.returncode != 0:
                parts = []
                test = re.search(r'(\w+\.py::\w+)', combined)
                if test: parts.append("test=" + test.group(1))
                ev = re.search(r'expected[= ]+(\S+).*?got[= ]+(\S+)', combined, re.I)
                if ev: parts.append("expected=" + ev.group(1) + " got=" + ev.group(2))
                ae = re.search(r'AssertionError:?\s*(.+)', combined)
                if ae: parts.append("assert=" + ae.group(1)[:200])
                fl = re.search(r'File "(.+?)", line (\d+)', combined)
                if fl: parts.append("file=" + fl.group(1) + ":" + fl.group(2))
                task.feedback = " | ".join(parts)[:400] if parts else combined[:400]
                return False
            task.feedback = "OK"
            return True
        except Exception as e:
            task.feedback = str(e)[:200]
            return False

    def _snapshot_files(self, patterns=None):
        if patterns is None:
            patterns = ("*.san", "*.py", "*.sasm")
        snap = {}
        for pat in patterns:
            for f in glob.glob(pat):
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        snap[f] = fh.read()
                except Exception:
                    pass
        return snap

    def _diff_files(self, before, after):
        diffs = []
        for f in set(before) | set(after):
            a = before.get(f, "")
            b = after.get(f, "")
            if a != b:
                d = list(difflib.unified_diff(a.splitlines(), b.splitlines(), fromfile="a/" + f, tofile="b/" + f, lineterm=""))
                lines2 = [x[:80] for x in d[:8]]
                diffs.append(f + ": " + "; ".join(lines2))
                if len(diffs) >= 2:
                    break
        return diffs

    def _detect_toggle(self, before, after, files):
        """检测来回改动: 同一文件从A→B→A 或 +3行后-3行"""
        for f in (set(before) | set(after)) & set(files):
            a = before.get(f, ""); b = after.get(f, "")
            if a == b and a != "":
                return True
            if a and b:
                diff = list(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm=""))
                adds = sum(1 for l in diff if l.startswith("+"))
                dels = sum(1 for l in diff if l.startswith("-"))
                if adds + dels == 0:
                    return True
        return False

    def _retry_loop(self, task):
        baseline = self._snapshot_files()
        prev_files = baseline
        retry_log = []
        modified_files = []

        while task.retries < task.max_retries:
            if task.retries > 0:
                curr_files = self._snapshot_files()
                diffs = self._diff_files(prev_files, curr_files)
                diff_str = "; ".join([d[:80] for d in diffs]) if diffs else "no change"
                failure = task.feedback[:200] if task.feedback else "unknown"

                entry = "[retry " + str(task.retries) + "] changed: " + diff_str[:120] + "\n  failure: " + failure[:120]
                retry_log.append(entry)

                task.description += "\n[history]\n" + "\n".join(retry_log[-4:])

                # same error twice on same location -> escalate
                if len(retry_log) >= 2:
                    pf = retry_log[-2].split("failure:")[1].strip() if "failure:" in retry_log[-2] else ""
                    cf = failure
                    if pf and pf[:60] == cf[:60]:
                        task.feedback = "same_error_twice: " + pf[:100]
                        return self._escalate(task)

                # toggle detection: 被改文件内容回到了原始状态 (相对于baseline)
                curr_modified = set(d.split(":")[0] for d in diffs if ": " in d)
                prev_modified = set(modified_files[-1]) if modified_files else set()
                overlap = prev_modified & curr_modified
                if overlap and self._detect_toggle(baseline, curr_files, overlap):
                    task.feedback = "toggle_detected: " + str([f[:40] for f in overlap])[:200]
                    return self._escalate(task)
                modified_files.append(list(curr_modified))

                prev_files = curr_files

            if self._execute_task(task):
                return True
            task.retries += 1
            task.status = TaskStatus.RETRY
            time.sleep(1)

        task.status = TaskStatus.FAILED
        self._escalate(task)
        return False

    def _escalate(self, task):
        dump = {"task": task.name, "description": task.description[:200],
                "retries": task.retries, "last_error": task.feedback[:300]}
        os.makedirs("build", exist_ok=True)
        fname = "build/escalate_" + task.name.replace(" ", "_")[:30] + ".json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(dump, f, ensure_ascii=False, indent=2)
        print()
        print("  >>> ESCALATE: " + task.name + " failed " + str(task.retries) + "x")
        print("  >>> error: " + task.feedback[:150])
        print("  >>> saved: " + fname)
        print()

    def _topological_order(self, tasks):
        name_to_task = {t.name: t for t in tasks}
        visited = set()
        order = []
        def dfs(name):
            if name in visited: return
            visited.add(name)
            t = name_to_task.get(name)
            if t:
                for dep in t.depends_on:
                    if dep in name_to_task: dfs(dep)
                order.append(t)
        for t in tasks:
            dfs(t.name)
        return order

    def run(self, spec, workspace="."):
        print("\n" + "=" * 50 + "\n  Project: " + spec[:60] + "\n" + "=" * 50 + "\n")
        print("[1/4] Decompose...")
        tasks = self._llm_decompose(spec)
        ordered = self._topological_order(tasks)
        print("      " + str(len(ordered)) + " sub-tasks\n")
        print("[2/4] Execute...")
        failed = 0
        for task in ordered:
            ok = self._retry_loop(task)
            print("  " + ("OK" if ok else "FAIL") + " " + task.name)
            if not ok:
                failed += 1
                if failed >= 3:
                    print("\n  Too many failures, stopping")
                    break
        print("\n[3/4] Verify...")
        all_ok = all(t.status == TaskStatus.DONE for t in tasks)
        print("[4/4] Report...")
        summary = "Project: " + spec + "\nTasks: " + str(len(tasks)) + " (" + str(sum(1 for t in tasks if t.status == TaskStatus.DONE)) + " done)"
        print(summary + "\n")
        return ProjectResult(success=all_ok, tasks=tasks, summary=summary)
