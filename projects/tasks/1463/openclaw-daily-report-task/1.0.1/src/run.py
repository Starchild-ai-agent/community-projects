# -*- task-system: v3 -*-
#!/usr/bin/env python3
"""
OpenClaw 日报分析任务
Job ID: injected by task runtime

流程：
1) 调 localhost /chat 让 Agent 抓取 GitHub 并生成分析
2) Agent 按契约返回 JSON {summary, content}
3) 用健壮的多级解析器提取 summary 和 content
4) summary 作为通知标题，content 作为正文 push 给用户
"""
import requests, os, sys, json, re

JOB_ID = os.environ.get("JOB_ID")

# 强调"只输出 JSON"，并列出常见错误示例，降低 Agent 输出杂言的概率
RESPONSE_FORMAT = """

=== 输出格式（严格）===
你的整个回复必须是**一个 JSON 对象，不要有任何其他内容**：
- 不要在 JSON 前面写"好的 / 以下是 / 分析如下 / 数据已抓取"等引导语
- 不要在 JSON 后面写"希望有帮助 / 如有疑问"等结语
- 不要用 ```json 代码块包裹
- 直接以 `{` 开头，以 `}` 结尾

{"summary": "一句话标题（不超过 40 字，概括今日最重要的 1-2 件事，可带 emoji）", "content": "完整的 markdown 分析报告"}

summary 是用户在通知栏看到的标题，必须精炼抢眼。
content 是完整的 markdown 报告正文，JSON 字符串里所有换行用 \\n 转义，所有引号用 \\" 转义。
"""

TASK_MESSAGE = """请帮我分析 OpenClaw（https://github.com/openclaw/openclaw）过去 24 小时的最新提交和发布动态。

步骤：
1. 用 web_fetch 抓取 https://api.github.com/repos/openclaw/openclaw/commits?per_page=50 获取最新提交（用 Python datetime 计算 24 小时前的 ISO 时间拼接 since 参数）
2. 用 web_fetch 抓取 https://api.github.com/repos/openclaw/openclaw/releases?per_page=5 获取最新发布

然后：
- 筛选出真正有价值的新功能、架构改进、安全修复（跳过纯测试、CI、文档格式等噪音）
- 对每个值得关注的点，说明它是什么、为什么重要
- 结合我们自己的 Starchild 平台，给出具体可借鉴的建议
- 如果今天没有实质性更新，summary 写"今日无重要更新"，content 简单说明即可

用中文输出。""" + RESPONSE_FORMAT


def _find_balanced_json(s: str, start: int) -> str | None:
    """从 start 位置的 { 开始，考虑字符串字面量内的转义，扫描到匹配的 }。"""
    if start >= len(s) or s[start] != '{':
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        c = s[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return None


def extract_json(text: str) -> dict | None:
    """从 Agent 回复中稳健提取 {summary, content}。
    四级策略：
      1) 剥 ```json 代码块后 parse
      2) 整段直接 parse
      3) 平衡括号扫描（从每个 { 开始尝试），忽略字符串内的 {}
      4) 正则兜底提取 summary/content 字段
    """
    if not text:
        return None
    s = text.strip()

    # strict=False 允许 JSON 字符串内出现裸控制字符（换行、tab 等）
    # —— Agent 经常把 markdown 正文直接塞进 content 字段，不做 \n 转义
    # 1) 剥 markdown 代码块
    fence = re.search(r"```(?:json)?\s*\n(.*?)\n```", s, re.DOTALL)
    if fence:
        try:
            obj = json.loads(fence.group(1).strip(), strict=False)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 2) 整段直接 parse
    try:
        obj = json.loads(s, strict=False)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 3) 平衡括号扫描：从每个 { 位置尝试解析
    for match in re.finditer(r'\{', s):
        candidate = _find_balanced_json(s, match.start())
        if not candidate:
            continue
        try:
            obj = json.loads(candidate, strict=False)
            if isinstance(obj, dict) and ('summary' in obj or 'content' in obj):
                return obj
        except json.JSONDecodeError:
            continue

    # 4) 正则兜底
    summary_m = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', s)
    content_m = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', s, re.DOTALL)
    if content_m:
        try:
            return {
                "summary": json.loads(f'"{summary_m.group(1)}"') if summary_m else "",
                "content": json.loads(f'"{content_m.group(1)}"'),
            }
        except Exception:
            pass

    return None



def main():
    try:
        resp = requests.post("http://localhost:8000/chat", json={
            "message": TASK_MESSAGE,
            "call_source": "task",
            "internal_options": {"job_id": JOB_ID},
        }, timeout=(10, 300))
        reply = resp.json().get("reply", "") if resp.ok else ""
    except requests.exceptions.ReadTimeout:
        print("[ERROR] Agent call timed out", file=sys.stderr)
        sys.exit(1)

    if not reply.strip():
        print("[WARN] Empty reply from agent, nothing to push", file=sys.stderr)
        sys.exit(0)

    data = extract_json(reply)
    if data and isinstance(data, dict) and data.get("content"):
        summary = (data.get("summary") or "OpenClaw 日报分析").strip()
        content = data["content"].strip()
        print(f"[OK] Parsed JSON: summary={summary[:60]}")
    else:
        # 兜底：所有解析路径都失败了，用原文 push，但保留默认标题
        print(f"[WARN] JSON parse failed, falling back to raw reply.", file=sys.stderr)
        print(f"[WARN] Raw reply head: {reply[:300]}", file=sys.stderr)
        print(f"[WARN] Raw reply tail: {reply[-300:]}", file=sys.stderr)
        summary = "OpenClaw 日报分析"
        content = reply.strip()

    requests.post("http://localhost:8000/push", json={
        "message": content,
        "title": summary,
        "channel": "all",
        "job_id": JOB_ID,
    }, timeout=10)
    print("[OK] Pushed to user")


if __name__ == "__main__":
    main()
