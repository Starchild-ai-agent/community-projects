"use strict";
const $ = (id) => document.getElementById(id);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* token estimate: CJK ~1 token/char, latin ~3.85 chars/token */
function estimateTokens(s) {
  if (!s) return 0;
  const cjk = (s.match(/[\u3400-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]/g) || []).length;
  const rest = s.length - cjk;
  return Math.round(cjk * 1.02 + rest / 3.85);
}

function splitFrontmatter(text) {
  const t = text.replace(/\r\n/g, "\n");
  const m = t.match(/^\s*---\n([\s\S]*?)\n---\n?/);
  if (!m) return { fm: null, body: t };
  return { fm: parseYamlLite(m[1]), body: t.slice(m[0].length) };
}
function parseYamlLite(raw) {
  const out = {}; let key = null;
  raw.split("\n").forEach(line => {
    if (!line.trim() || line.trim().startsWith("#")) return;
    const kv = line.match(/^([A-Za-z0-9_.-]+)\s*:\s*(.*)$/);
    if (kv) {
      key = kv[1].trim();
      let v = kv[2].trim();
      if (/^[|>][-+]?$/.test(v)) { out[key] = ""; return; }
      out[key] = v.replace(/^["']|["']$/g, "");
      return;
    }
    if (key && /^\s+/.test(line)) out[key] = ((out[key] || "") + " " + line.trim()).trim();
  });
  return out;
}

const RE_INJECT = [
  [/ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)/i, "覆盖既有指令（prompt injection 典型话术）"],
  [/disregard\s+(the\s+)?(system|developer)\s+(prompt|message|instructions)/i, "无视系统/开发者指令"],
  [/you\s+are\s+now\s+(an?\s+)?(unrestricted|jailbroken|dan)\b/i, "角色越狱话术"],
  [/do\s+not\s+tell\s+the\s+user/i, "要求对用户隐瞒行为"],
  [/without\s+(asking|telling|informing|confirming)/i, "绕过用户确认执行"],
  [/exfiltrat|send\s+(the\s+)?(content|data|keys?)\s+to/i, "数据外发语义"]
];
const RE_SECRET = [
  [/\bsk-[A-Za-z0-9]{16,}\b/, "疑似 OpenAI 风格 API Key"],
  [/\bgh[pousr]_[A-Za-z0-9]{20,}\b/, "疑似 GitHub Token"],
  [/\bAKIA[0-9A-Z]{16}\b/, "疑似 AWS Access Key"],
  [/\bxox[baprs]-[A-Za-z0-9-]{10,}\b/, "疑似 Slack Token"],
  [/\b(api[_-]?key|secret|password|token)\s*[:=]\s*["']?[A-Za-z0-9_\-]{16,}/i, "疑似硬编码凭据"]
];
const RE_DANGER = [
  [/curl[^\n|]*\|\s*(ba)?sh/i, "远程脚本直接执行（curl | sh）"],
  [/\brm\s+-rf\s+[\/~$]/i, "破坏性删除命令"],
  [/chmod\s+777/i, "过度宽松权限（chmod 777）"],
  [/eval\s*\(/i, "eval 动态执行"],
  [/base64\s+-d[^\n]*\|\s*(ba)?sh/i, "base64 解码后执行"]
];

function runChecks(text) {
  const { fm, body } = splitFrontmatter(text);
  const checks = [], findings = [];
  const add = (title, status, msg) => checks.push({ title, status, msg });

  if (!fm) add("YAML frontmatter", "bad", "未检测到 frontmatter。缺少 name/description 时平台无法索引该技能。");
  else add("YAML frontmatter", "ok", "已检测到 frontmatter 块。");

  const name = fm && fm.name ? String(fm.name).trim() : "";
  if (!name) add("name 字段", "bad", "缺少 <code>name</code>。建议小写连字符 slug，≤64 字符。");
  else if (!/^[a-z0-9][a-z0-9._-]{1,63}$/.test(name)) add("name 字段", "warn", `<code>${esc(name)}</code> 不符合 slug 规范（小写/数字/连字符）。`);
  else add("name 字段", "ok", `命名规范：<code>${esc(name)}</code>`);

  const desc = fm && fm.description ? String(fm.description) : "";
  const dLen = desc.length;
  if (!desc) add("description 字段", "bad", "缺少 description —— 这是模型决定「何时调用」的唯一依据。");
  else if (dLen < 30) add("description 字段", "warn", `描述偏短（${dLen} 字符），建议写清「做什么 + 何时用 + 触发词」。`);
  else if (dLen > 1024) add("description 字段", "warn", `描述过长（${dLen} 字符），可能被截断；建议 ≤1024。`);
  else add("description 字段", "ok", `长度合适（${dLen} 字符）。`);

  const trig = (desc.match(/use when|when the user|whenever|if the user|用于|当用户|适用于|触发|当你/g) || []).length;
  const trigRatio = clamp(trig / 2, 0, 1);
  if (desc && trig === 0) add("可检索性 / 触发条件", "warn", "描述里没有「何时使用」的触发语句，模型可能想不起调用它。");
  else if (desc) add("可检索性 / 触发条件", trig >= 2 ? "ok" : "warn",
    `检测到 ${trig} 处触发语。${trig >= 2 ? "" : "建议补 1–2 句用户可能说的原话。"}`);

  const b = (body || "").trim();
  if (b.length < 80) add("正文内容", "bad", `正文仅 ${b.length} 字符，缺少可执行的操作说明。`);
  else add("正文内容", "ok", `正文 ${b.length} 字符。`);

  const steps = (b.match(/^\s*(?:\d+[.)]|[-*]\s)\s+\S/gm) || []).length;
  const hasCode = /```/.test(b);
  if (steps === 0 && !hasCode) add("可执行步骤", "warn", "没有编号步骤或代码块，模型只能自由发挥，结果不稳定。");
  else add("可执行步骤", "ok", `步骤/列表 ${steps} 条${hasCode ? "，含代码块" : ""}。`);

  const refs = (b.match(/references\/|scripts\/|assets\/|templates\//g) || []).length;
  if (refs === 0 && b.length > 4000) add("渐进披露", "warn", "主文件较长却无任何 references/ scripts/ 引用，建议拆分以节省上下文。");
  else add("渐进披露", "ok", refs ? `引用了 ${refs} 处外部资源。` : "体量适中，无需拆分。");

  const tok = estimateTokens(text);
  if (tok > 12000) add("Token 预算", "bad", `约 ${tok} token，远超建议值 5000，会挤占系统提示。`);
  else if (tok > 5000) add("Token 预算", "warn", `约 ${tok} token，超过 5000 建议线，考虑移到 references/。`);
  else add("Token 预算", "ok", `约 ${tok} token，处于舒适区。`);

  const secHits = [];
  RE_SECRET.forEach(([re, label]) => { const m = text.match(re); if (m) secHits.push({ label, sample: m[0] }); });
  if (secHits.length) {
    secHits.forEach(h => findings.push({ sev: "high", k: "secret", v: `${h.label}：<code>${esc(h.sample.slice(0, 26))}…</code> 请改用环境变量。` }));
    add("密钥泄露", "bad", `发现 ${secHits.length} 处疑似硬编码凭据。`);
  } else add("密钥泄露", "ok", "未发现硬编码密钥。");

  const inj = [];
  RE_INJECT.forEach(([re, label]) => { if (re.test(text)) inj.push(label); });
  if (inj.length) {
    inj.forEach(l => findings.push({ sev: "high", k: "inject", v: `提示注入模式：${esc(l)}` }));
    add("提示注入模式", "bad", `命中 ${inj.length} 条可疑语义。`);
  } else add("提示注入模式", "ok", "未命中常见注入话术。");

  const dang = [];
  RE_DANGER.forEach(([re, label]) => { const m = text.match(re); if (m) dang.push({ label, sample: m[0] }); });
  if (dang.length) {
    dang.forEach(h => findings.push({ sev: "med", k: "danger", v: `危险命令：${esc(h.label)} → <code>${esc(h.sample.slice(0, 32))}</code>` }));
    add("危险命令", "warn", `发现 ${dang.length} 处高风险命令，需人工确认是否必要。`);
  } else add("危险命令", "ok", "未发现破坏性命令。");

  const urls = [...new Set((text.match(/https?:\/\/[^\s)>\]]+/g) || []))];
  if (urls.length > 6) findings.push({ sev: "low", k: "url", v: `引用了 ${urls.length} 个外部链接，注意供应链与内容漂移风险。` });

  const mutates = /创建|删除|发送|发布|deploy|转账|payment|swap|\bpost\b|\bwrite\b/i.test(b);
  const guarded = /注意|warning|caution|确认|confirm|confirmation|dry[- ]run|preview/i.test(b);
  if (mutates && !guarded) {
    findings.push({ sev: "med", k: "side", v: "技能会改变外部状态（写/发/交易），但正文未提示确认或 dry-run。" });
    add("副作用声明", "warn", "存在写操作，却没有确认/预演提示。");
  } else add("副作用声明", "ok", "未发现未声明的危险副作用。");

  const W = { ok: 1, warn: .5, bad: 0 };
  const base = checks.length ? checks.reduce((s, c) => s + W[c.status], 0) / checks.length : 0;
  let score = Math.round(base * 100);
  score -= findings.filter(f => f.sev === "high").length * 5;
  score -= findings.filter(f => f.sev === "med").length * 2;
  score = clamp(score, 0, 100);

  return { checks, findings, score, tok, trigRatio, steps, refs, name, lines: text.split("\n").length };
}

const ICON = { ok: "✓", warn: "!", bad: "✕" };
let lastReport = null;

function render(text) {
  const r = runChecks(text);
  lastReport = r;

  $("ringArc").style.strokeDashoffset = String(283 - (283 * r.score / 100));
  $("scoreVal").innerHTML = `${r.score}<small>分</small>`;

  const g = r.score >= 90 ? ["A · 可直接发布", "结构完整，未发现明显阻塞性风险。", "#34d399"]
    : r.score >= 78 ? ["B · 可用，建议微调", "核心要素齐备，按下方建议补齐细节。", "#a3e635"]
    : r.score >= 62 ? ["C · 需要修补", "存在若干会影响稳定性或可发现性的问题。", "#fbbf24"]
    : ["D · 不建议发布", "缺少关键要素或命中高风险项。", "#fb7185"];
  $("grade").textContent = g[0];
  $("grade").style.color = g[2];
  $("verdictTxt").textContent = g[1];

  $("sTok").textContent = r.tok.toLocaleString();
  $("sLine").textContent = r.lines.toLocaleString();
  $("sStep").textContent = r.steps;
  $("sRef").textContent = r.refs;

  const tp = clamp(r.tok / 5000 * 100, 2, 100);
  $("tokBar").style.width = tp + "%";
  $("tokBar").className = r.tok > 12000 ? "fill-bad" : r.tok > 5000 ? "fill-warn" : "fill-ok";
  $("tokLbl").textContent = `${r.tok.toLocaleString()} / 5,000`;

  $("trigBar").style.width = (r.trigRatio * 100).toFixed(0) + "%";
  $("trigBar").className = r.trigRatio >= .99 ? "fill-ok" : r.trigRatio >= .5 ? "fill-warn" : "fill-bad";
  $("trigLbl").textContent = r.trigRatio >= .99 ? "强" : r.trigRatio >= .5 ? "中" : "弱";

  $("checks").innerHTML = r.checks.map(c => `
    <div class="chk">
      <div class="dot d-${c.status}">${ICON[c.status]}</div>
      <div class="txt"><div class="t">${esc(c.title)}</div><div class="m">${c.msg}</div></div>
    </div>`).join("");

  const order = { high: 0, med: 1, low: 2 };
  const fs = r.findings.slice().sort((a, b) => order[a.sev] - order[b.sev]);
  $("fCount").textContent = fs.length ? `(${fs.length})` : "";
  $("findings").innerHTML = fs.length
    ? fs.map(f => `<div class="fnd ${f.sev}"><div class="k">${f.sev}</div><div class="v">${f.v}</div></div>`).join("")
    : `<div class="empty">未发现风险项 —— 这个技能看起来挺干净。</div>`;
}

function reportMd() {
  if (!lastReport) return "";
  const r = lastReport, L = [];
  const strip = s => s.replace(/<[^>]+>/g, "");
  L.push(`# SkillAudit 报告 — ${r.name || "(未命名技能)"}`, "");
  L.push(`- 评分：**${r.score}/100**`, `- 估算 token：${r.tok}（建议 ≤ 5000）`,
    `- 行数：${r.lines}`, `- 步骤/列表：${r.steps}`, "");
  L.push("## 规则检查");
  r.checks.forEach(c => L.push(`- [${c.status === "ok" ? "x" : " "}] **${c.title}** — ${strip(c.msg)}`));
  L.push("", "## 风险与建议");
  if (!r.findings.length) L.push("_无_");
  r.findings.forEach(f => L.push(`- \`${f.sev}\` ${strip(f.v)}`));
  L.push("", `_由 SkillAudit 生成 · ${new Date().toISOString()} · 本地静态分析_`);
  return L.join("\n");
}

/* ---- events ---- */
$("run").addEventListener("click", () => {
  const t = $("src").value;
  if (!t.trim()) {
    $("hint").textContent = "先粘贴或选择一个 SKILL.md";
    $("hint").style.color = "#fb7185";
    return;
  }
  $("hint").style.color = "";
  $("hint").textContent = "已分析 ✓";
  render(t);
});
$("clear").addEventListener("click", () => {
  $("src").value = ""; $("filetag").textContent = ""; $("hint").textContent = "⌘/Ctrl + Enter";
  ["sTok", "sLine", "sStep", "sRef"].forEach(id => $(id).textContent = "—");
  $("checks").innerHTML = '<div class="empty">尚无数据。</div>';
  $("findings").innerHTML = '<div class="empty">尚无发现。</div>';
  $("scoreVal").innerHTML = "–<small>分</small>";
  $("ringArc").style.strokeDashoffset = "283";
  $("grade").textContent = "等待体检"; $("grade").style.color = "";
  $("verdictTxt").textContent = "载入一个 SKILL.md，检查 frontmatter 合规、结构完整度、提示注入与密钥泄露风险。";
  $("tokBar").style.width = "0"; $("trigBar").style.width = "0";
  $("tokLbl").textContent = "—"; $("trigLbl").textContent = "—"; $("fCount").textContent = "";
  lastReport = null;
});
$("pick").addEventListener("click", () => $("file").click());
$("file").addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  const rd = new FileReader();
  rd.onload = () => {
    $("src").value = rd.result;
    $("filetag").textContent = `已载入 ${f.name} · ${(f.size / 1024).toFixed(1)} KB`;
    render(rd.result);
  };
  rd.readAsText(f);
});

const drop = $("drop");
["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("hot"); }));
["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("hot"); }));
drop.addEventListener("drop", e => {
  const f = e.dataTransfer.files[0]; if (!f) return;
  const rd = new FileReader();
  rd.onload = () => { $("src").value = rd.result; $("filetag").textContent = `已载入 ${f.name}`; render(rd.result); };
  rd.readAsText(f);
});

document.addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); $("run").click(); }
});

$("copy").addEventListener("click", async () => {
  const md = reportMd(); if (!md) return;
  try {
    await navigator.clipboard.writeText(md);
    $("copy").textContent = "已复制 ✓";
    setTimeout(() => $("copy").textContent = "复制 Markdown 报告", 1600);
  } catch (_) {}
});
$("dl").addEventListener("click", () => {
  const md = reportMd(); if (!md) return;
  const b = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(b);
  a.download = `skillaudit-${(lastReport && lastReport.name) || "report"}.md`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
});

const SAMPLE = `---
name: rss-digest
description: Convert an RSS/Atom feed URL into a daily digest. Use when the user asks to summarize a blog feed, track a site's new posts, or build a morning reading list.
version: 1.0.0
---

# RSS Digest

Pull the feed, keep only items published since the last run, and summarize them.

## When to use
- 用户说"帮我总结这个博客的最新文章"
- 需要每天跟踪某个站点的更新
- 想生成晨间阅读清单

## Steps
1. Fetch the feed URL with \`curl -sL <url>\`.
2. Parse \`<item>\` / \`<entry>\` nodes, keep the newest 10.
3. For each item, write a 2-sentence summary.
4. Output a markdown list: title — link — summary.

## Notes
- Respect robots.txt and cache results in \`references/cache.json\`.
- If the feed returns 304, report "no new items".
`;
$("loadSample").addEventListener("click", () => {
  $("src").value = SAMPLE;
  $("filetag").textContent = "示例：rss-digest";
  $("hint").textContent = "已分析 ✓";
  render(SAMPLE);
});
