// .opencode/plugins/sanyan.js — Sanyan Runtime Plugin
// 将三态引擎 + 规则引擎 + UR 检测嵌入 OpenCode agent 循环

const TRIT_SYMBOLS = { 1: "●●●", "-1": "○○○", 0: "◐◐◐" };
const COG_NAMES = { AFFIRM: "确信", NEGATE: "拒绝", UNCERT: "不确定" };

// ── 三态引擎 (纯 JS 实现，无依赖) ──
class TernaryEngine {
  constructor() {
    this.history = [];      // [{trit, conf, cog, tool}]
    this.hesitation = 0;
    this.urHistory = [];    // LLM 输出历史 (用于退化检测)
    this.ruleHits = [];
    this.toolChain = [];
  }

  // 五态分类
  classify(tool, result) {
    const r = String(result || "").toLowerCase();
    if (r.includes("error") || r.includes("traceback") || r.includes("fail"))
      return "NEGATE";
    if (r.includes("no such file") || r.includes("not found"))
      return "UNCERT";  // 文件不存在 = 可恢复
    if (r.includes("通过") || r.includes("ok") || r.includes("success") || r.includes("written"))
      return "AFFIRM";
    if (tool === "bash" && r.includes("0"))
      return "AFFIRM";
    if (tool === "done")
      return "AFFIRM";
    return "UNCERT";  // 默认不确定
  }

  // Kleene 传播
  propagate(upstream, current) {
    const K = { "-1,-1": -1, "-1,0": -1, "-1,1": -1, "0,-1": -1, "0,0": 0, "0,1": 0, "1,-1": -1, "1,0": 0, "1,1": 1 };
    return K[`${upstream},${current}`] ?? current;
  }

  // 置信度
  toolConf(tool) {
    const TC = { read: 0.9, list: 0.9, search: 0.85, grep: 0.85, edit: 0.6, write: 0.5, bash: 0.7, done: 1.0 };
    return TC[tool] || 0.7;
  }

  step(tool, result) {
    const cog = this.classify(tool, result);
    const trit = { AFFIRM: 1, NEGATE: -1, UNCERT: 0 }[cog] || 0;
    const conf = (({ AFFIRM: 0.9, NEGATE: 0.85, UNCERT: 0.4 })[cog] || 0.5) * this.toolConf(tool);

    let upstream = { trit: 1, conf: 1.0 };
    if (this.history.length > 0) upstream = this.history[this.history.length - 1];

    const propagated = this.propagate(upstream.trit, trit);
    const propagatedConf = Math.min(0.99, upstream.conf * conf);

    if (trit === 0) this.hesitation++;
    else this.hesitation = 0;

    const entry = { trit: propagated, conf: propagatedConf, cog, tool };
    this.history.push(entry);
    if (this.history.length > 12) this.history.shift();

    // 门控判定
    let gate = "continue";
    if (cog === "NEGATE" && propagatedConf > 0.6) gate = "block";
    if (this.hesitation >= 3) gate = "block";

    return { trit: propagated, conf: propagatedConf, cog, gate };
  }

  // UR 退化检测 (在 LLM 文本上)
  checkUR(llmText) {
    this.urHistory.push(String(llmText || "").slice(0, 200));
    if (this.urHistory.length > 6) this.urHistory.shift();
    if (this.urHistory.length < 3) return 1.0;
    // 10字符切片 → 计算 unique ratio
    const tokens = [];
    for (const t of this.urHistory) {
      for (let i = 0; i < Math.min(t.length, 100); i += 10)
        tokens.push(t.slice(i, i + 10));
    }
    if (tokens.length < 8) return 1.0;
    return new Set(tokens).size / tokens.length;
  }

  summary() {
    if (this.history.length === 0) return "无记录";
    const last = this.history[this.history.length - 1];
    return `${COG_NAMES[last.cog] || "?"}(${last.conf.toFixed(2)})`;
  }
}

// ── 规则引擎 (轻量版) ──
const RULES = [
  { pattern: /创建|新增|写.*\.py|新建.*\.py|实现.*模块/, name: "创建Python模块" },
  { pattern: /修复.*错误|fix.*error|修复.*bug/, name: "修复错误" },
  { pattern: /解释.*代码|分析.*代码/, name: "代码解释" },
  { pattern: /重构|优化.*代码/, name: "重构代码" },
];

function matchRule(task) {
  for (const r of RULES) {
    if (r.pattern.test(task)) return r;
  }
  return null;
}

// ── Plugin 入口 ──
export const SanyanRuntime = async ({ client, project, $ }) => {
  const engine = new TernaryEngine();

  await client.app.log({
    body: { service: "sanyan", level: "info", message: "Sanyan Runtime 已加载" },
  });

  return {
    // 工具执行后 → 三态分类
    "tool.execute.after": async (input, output) => {
      const { trit, conf, cog, gate } = engine.step(input.tool, String(output.result || ""));
      const symbol = TRIT_SYMBOLS[trit] || "———";

      await client.app.log({
        body: {
          service: "sanyan",
          level: cog === "NEGATE" ? "warn" : "info",
          message: `[${symbol}] ${cog} conf=${conf.toFixed(2)} tool=${input.tool} gate=${gate}`,
        },
      });

      // 门控拦截
      if (gate === "block") {
        await client.tui.showToast({
          body: { message: `⚠️ 三态门控: ${cog} (conf=${conf.toFixed(2)})`, variant: "warning" },
        });
      }
    },

    // LLM 消息 → UR 退化检测
    "message.part.updated": async (input, output) => {
      if (output.part?.type === "text") {
        const ur = engine.checkUR(output.part.text);
        if (ur < 0.30) {
          await client.app.log({
            body: { service: "sanyan", level: "warn", message: `UR退化检测: UR=${ur.toFixed(2)} < 0.30` },
          });
          await client.tui.showToast({
            body: { message: `🔄 检测到退化 (UR=${ur.toFixed(2)})`, variant: "error" },
          });
        }
      }
    },

    // 会话状态 → 输出 Sanyan 面板
    "session.status": async (input, output) => {
      if (output.status === "idle") {
        const summary = engine.summary();
        const rule = matchRule(input.task || "") || { name: "—" };
        const lastTools = engine.history.slice(-3).map(h => `${h.tool}: ${h.cog}`);
        const ur = engine.urHistory.length > 0
          ? engine.checkUR(engine.urHistory[engine.urHistory.length - 1])
          : 1.0;

        await client.app.log({
          body: {
            service: "sanyan",
            level: "info",
            message: [
              `╔══ Sanyan Panel ══╗`,
              `║ 三态: ${summary.padEnd(20)} ║`,
              `║ 规则: ${rule.name.padEnd(20)} ║`,
              `║ UR:   ${ur.toFixed(2).padEnd(20)} ║`,
              ...lastTools.map(t => `║  ${t.padEnd(20)} ║`),
              `╚══════════════╝`,
            ].join("\n"),
          },
        });
      }
    },

    // 自定义命令: /sanyan — 显示面板
    "tui.command.execute": async (input, output) => {
      if (input.command === "sanyan") {
        const h = engine.history;
        const lines = [
          `\n╔════ Sanyan Runtime ════╗`,
          `║ 三态: ${engine.summary().padEnd(18)}║`,
          `║ 规则: ${(matchRule(input.task || "") || { name: "—" }).name.padEnd(18)}║`,
          `║ 工具: ${h.length} 步`.padEnd(20) + "║",
        ];
        for (const e of h.slice(-5)) {
          const s = TRIT_SYMBOLS[e.trit] || "?";
          lines.push(`║  ${s} ${e.tool}`.padEnd(20) + "║");
        }
        lines.push("╚══════════════════════╝");
        await client.app.log({ body: { service: "sanyan", level: "info", message: lines.join("\n") } });
      }
    },
  };
};
