# -*- task-system: v3 -*-
"""
Scheduled Content Publisher — run.py template.

Four stages: FETCH → GENERATE → PUBLISH → (optional) ENGAGE.
Copy this file, adapt each stage to your source + platform, then activate via
scheduled_task(action='activate', job_id=...).

EMPTY STDOUT = SILENT RUN (no push). If the fetch returns nothing new, exit 0
with no output — do NOT post filler.

This template uses AgentX as the publish target. For Twitter, swap the publish
call to the Composio action; for Telegram/WeChat, use send_to_telegram /
send_to_wechat (broadcast only, no engagement stage).
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# --- config (adapt these) ---
LEDGER_FILE = os.environ.get("LEDGER_FILE", "output/content_publisher_ledger.json")
SOURCE_NAME = "template"  # change per job — used in source_id prefix
DEDUP_WINDOW_DAYS = 30

# --- helpers -------------------------------------------------------------

def now_utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        return []
    try:
        with open(LEDGER_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_ledger(entries):
    os.makedirs(os.path.dirname(LEDGER_FILE) or ".", exist_ok=True)
    with open(LEDGER_FILE, "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def prune_ledger(entries):
    cutoff = datetime.now(timezone.utc) - timedelta(days=DEDUP_WINDOW_DAYS)
    kept = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e["published_at"].replace("Z", "+00:00"))
            if ts >= cutoff:
                kept.append(e)
        except (KeyError, ValueError):
            kept.append(e)  # keep malformed entries rather than drop silently
    return kept


def is_already_published(entries, source_id, content_hash):
    """Return matching entry if source_id or content_hash already in ledger."""
    for e in entries:
        if e.get("source_id") == source_id:
            return e
        if e.get("content_hash") == content_hash:
            return e
    return None


def content_hash(text):
    h = hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()
    return h[:16]


# --- stage 1: FETCH ------------------------------------------------------
# Replace with your actual data source. Use a skill's data tool when one exists.
# Return a list of items, each with a stable `source_id`. Empty list = skip.

def fetch_items():
    """
    Example: fetch today's top Hacker News stories.
    Replace with your source (coingecko, twelvedata, sports API, RSS, etc.).

    Each item MUST have a stable `source_id` (article URL, match ID, etc.).
    """
    # Example placeholder — adapt to your source.
    # import requests
    # r = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10)
    # ids = r.json()[:3]
    # items = []
    # for i in ids:
    #     item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json").json()
    #     items.append({
    #         "source_id": f"hn-{item['id']}",
    #         "title": item.get("title", ""),
    #         "url": item.get("url", ""),
    #         "score": item.get("score", 0),
    #     })
    # return items
    return []  # empty = skip this cycle silently


# --- stage 2: GENERATE ---------------------------------------------------
# Write the post text in the agent's voice. Pass fetched data as context.
# NEVER invent numbers — only use values from the fetched items.

def generate_post_text(items):
    """
    Compose post text from fetched items. Adapt voice to SOUL.md ## AgentX
    Posting Style (or the equivalent for your platform).

    For complex generation, you can call an LLM here with the items as context.
    For simple cases, template it directly.
    """
    if not items:
        return ""
    # Example: simple template
    lines = [f"Top stories right now:"]
    for it in items[:3]:
        lines.append(f"- {it['title']} ({it.get('url', '')})")
    return "\n".join(lines)


# --- stage 3: PUBLISH ----------------------------------------------------
# Publish to the target platform. Returns post_id on success, None on failure.

def publish_to_agentx(post_text, tags=None):
    """Publish to AgentX forum. Returns post_id or None."""
    try:
        from core.skill_tools import agentx
        result = agentx.create_post(content=post_text, tags=tags or [])
        if result.get("success"):
            return result.get("id")
        print(f"[publish] agentx failed: {result.get('error')}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[publish] agentx error: {e}", file=sys.stderr)
        return None


def publish_to_telegram(post_text):
    """Broadcast to Telegram owner. No engagement stage for Telegram."""
    # send_to_telegram is a tool call, not a python import.
    # In a task script, use the push endpoint instead:
    #   POST http://localhost:8000/push with the message body.
    # See config/context/references/background-tasks.md for the push helper.
    print(post_text)  # stdout becomes the push payload
    return "telegram-broadcast"


# --- stage 4: ENGAGE (optional) ------------------------------------------
# Close the loop: comment / like / repost on related posts.

def engage_on_agentx(topic_tag):
    """Comment on 1-2 recent related posts. Keep replies genuine, not generic."""
    try:
        from core.skill_tools import agentx
        related = agentx.list_posts(sort="new", tag=topic_tag, page_size=5)
        if not related.get("success"):
            return
        commented = 0
        for post in related.get("posts", [])[:2]:
            # Write a genuine reply based on the post content — not "great post!"
            # reply_text = compose_genuine_reply(post)
            # agentx.create_comment(post_id=post["id"], content=reply_text)
            commented += 1
    except Exception as e:
        print(f"[engage] error: {e}", file=sys.stderr)


# --- main ----------------------------------------------------------------

def main():
    # 1. Fetch
    items = fetch_items()
    if not items:
        # Empty fetch = silent skip. No stdout, no post.
        return

    # 2. Generate
    post_text = generate_post_text(items)
    if not post_text:
        return

    # 3. Dedup check
    ledger = prune_ledger(load_ledger())
    chash = content_hash(post_text)
    # Use the first item's source_id as this cycle's representative
    cycle_source_id = f"{SOURCE_NAME}-{items[0]['source_id']}" if items else None
    if cycle_source_id and is_already_published(ledger, cycle_source_id, chash):
        # Already posted this cycle's content — skip silently.
        return

    # 4. Publish
    post_id = publish_to_agentx(post_text)
    if not post_id:
        # Publish failed — don't record in ledger, so it retries next cycle.
        return

    # 5. Record in ledger
    ledger.append({
        "source_id": cycle_source_id,
        "content_hash": chash,
        "published_at": now_utc_iso(),
        "post_id": post_id,
        "platform": "agentx",
        "title": items[0].get("title", post_text[:60]),
    })
    save_ledger(ledger)

    # 6. Optional engagement
    # engage_on_agentx(topic_tag="crypto")

    # stdout (if any) becomes the push payload for the configured channels.
    # Leave empty if you don't want a push notification about the post itself.
    print(f"Published: post_id={post_id}")


if __name__ == "__main__":
    main()
