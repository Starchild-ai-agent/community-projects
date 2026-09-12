import express from "express";
import OpenAI from "openai";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const app = express();
const client = new OpenAI({ maxRetries: 0, apiKey: process.env.OPENAI_API_KEY });
const port = process.env.PORT || 3000;
const indexPath = resolve("index.html");

const LIVE_PROMPT = `你是 Starchild 的语音界面。用户通过语音和你对话，你就是 Starchild 本身——不要把自己描述成"接线员"或"转接员"，也不要说"让我帮你问问后台"。

说话风格：简洁、自然、口语化，像打电话给一位懂技术的助理。每次回答一两句话就好，除非用户要求展开。用用户的语言（默认简体中文）回答。

Delegation policy:
Backend tools:
- Starchild agent: 你的大脑本体，能查资料、执行任务、多步推理。所有需要动脑或动手的事都交给它。
Delegate to the backend when:
- 用户询问任何实时信息、新闻、市场数据、价格
- 用户询问 Starchild 的状态、能力，或要求执行任何任务
- 答案需要推理、查资料或多步操作
Do not delegate to the backend when:
- 打招呼、闲聊、或重复已经给出的结果
- 需要先简短澄清用户意图
Delegate before giving an answer that depends on backend work.
Do not guess the result while waiting.`;

app.use(express.json({ limit: "256kb" }));
app.get("/", async (_req, res) => {
  res.type("html").send(await readFile(indexPath, "utf8"));
});

// Voice-session continuity: live session id -> conversation history.
// Each entry: {role: 'user'|'agent', text}. Sent along with every /chat call
// so the agent keeps context across delegations in the same call.
const histories = new Map(); // liveSessionId -> Array<{role,text}>
const MAX_HISTORY = 20;

function historyText(sessionId) {
  const h = histories.get(sessionId) || [];
  return h
    .slice(-MAX_HISTORY)
    .map((m) => (m.role === "user" ? `用户: ${m.text}` : `Starchild: ${m.text}`))
    .join("\n");
}

// Local-only demo. Add auth before exposing publicly.
app.post("/api/session", async (req, res) => {
  if (typeof req.body?.sdp !== "string" || !req.body.sdp.trim()) {
    return res.status(400).json({ error: "An SDP offer is required" });
  }
  if (!process.env.OPENAI_API_KEY) {
    return res.status(503).json({ error: "OPENAI_API_KEY not set" });
  }
  try {
    const result = await client.live.create({
      session: {
        model: "gpt-live-1",
        instructions: LIVE_PROMPT,
        delegation: { type: "client" },
      },
      transport: { type: "webrtc", sdp: req.body.sdp },
    });
    const sid = result?.session?.id;
    if (sid && !histories.has(sid)) histories.set(sid, []);
    res.status(201).json(result);
  } catch (error) {
    if (!(error instanceof OpenAI.APIError)) throw error;
    console.error("Live session creation failed", error.status, error.message);
    res.status(error.status || 500).json({ error: error.message });
  }
});

// Async tasks: frontend POSTs to start, then polls GET /api/agent/:id.
// Each HTTP round-trip is instant, so the public gateway never 504s.
const tasks = new Map(); // taskId -> {status:'running'|'done'|'error', reply?, error?}
let taskSeq = 0;

app.post("/api/agent", async (req, res) => {
  const { session_id: sessionId, text } = req.body || {};
  if (typeof text !== "string" || !text.trim()) {
    return res.status(400).json({ error: "text is required" });
  }
  const sid = typeof sessionId === "string" ? sessionId : "default";
  if (!histories.has(sid)) histories.set(sid, []);
  const h = histories.get(sid);
  h.push({ role: "user", text: text.trim() });

  const message =
    (h.length > 1
      ? `以下是本次语音通话此前的对话（供上下文参考）：\n${historyText(sid).slice(0, 6000)}\n\n`
      : "") + `用户现在说：${text.trim()}\n\n请简洁口语化地回答（1-2句话，适合语音播报），默认简体中文。`;

  const taskId = `t${Date.now()}_${++taskSeq}`;
  tasks.set(taskId, { status: "running", progress: [] });
  res.json({ task_id: taskId });

  // Run the brain call in background; frontend polls for the result.
  (async () => {
    const prog = tasks.get(taskId).progress;
    const push = (kind, detail) => {
      prog.push({ t: Date.now(), kind, detail: String(detail).slice(0, 200) });
      if (prog.length > 50) prog.shift();
    };
    try {
      const r = await fetch("http://localhost:8000/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, call_source: "internal" }),
        signal: AbortSignal.timeout(600000),
      });
      if (!r.ok || !r.body) throw new Error(`agent HTTP ${r.status}`);
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "", reply = "";
      for (;;) {
        const { value, done: eof } = await reader.read();
        if (eof) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            if (ev.type === "text_delta") reply += ev.data?.text || "";
            else if (ev.type === "turn_start") push("turn", `开始第 ${ev.data?.turn ?? "?"} 轮思考`);
            else if (ev.type === "tool_start") push("tool", `调用工具 ${ev.data?.tool_name || ""}：${ev.data?.input?.activity || ev.data?.input?.query || ""}`);
            else if (ev.type === "tool_complete") push("tool_done", `工具 ${ev.data?.tool_name || ""} 返回${ev.data?.success === false ? "（失败）" : ""}`);
            else if (ev.type === "agent_complete") { buf = ""; break; }
          } catch (_) {}
        }
      }
      reply = reply.trim() || "（大脑暂时没有返回）";
      h.push({ role: "agent", text: reply });
      tasks.set(taskId, { status: "done", reply, progress: prog });
    } catch (err) {
      console.error("agent call failed", err.message);
      tasks.set(taskId, { status: "error", error: `Starchild 大脑调用失败: ${err.message}`, progress: prog });
    }
    setTimeout(() => tasks.delete(taskId), 300000);
  })();
});

app.get("/api/agent/:id", (req, res) => {
  const t = tasks.get(req.params.id);
  if (!t) return res.status(404).json({ error: "task not found" });
  res.json(t);
});

app.post("/api/session/:id/end", (req, res) => {
  histories.delete(req.params.id);
  res.json({ ok: true });
});

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, key: !!process.env.OPENAI_API_KEY });
});

app.listen(port, "0.0.0.0", () => {
  console.log(`gpt-live demo listening on :${port}`);
});
