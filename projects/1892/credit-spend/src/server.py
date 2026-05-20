"""
Credit Spend Dashboard — proxy server.

Pulls live data from the Starchild Credit API (internal, scoped to *your* container)
and serves the static dashboard. Zero config, zero auth — every user runs their own.
"""
import asyncio
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

CREDIT_API = "http://starchild-credit-api.internal:8080"
HERE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Credit Spend Dashboard")


async def _get(client: httpx.AsyncClient, path: str, **params):
    r = await client.get(f"{CREDIT_API}{path}", params=params, timeout=15.0)
    r.raise_for_status()
    return r.json()


@app.get("/api/balance")
async def balance():
    async with httpx.AsyncClient() as c:
        return await _get(c, "/api/credits")


@app.get("/api/daily")
async def daily(days: int = 30):
    days = max(1, min(days, 90))
    async with httpx.AsyncClient() as c:
        return await _get(c, "/api/usage/daily", days=days)


@app.get("/api/breakdown")
async def breakdown(days: int = 30, max_pages: int = 40, page_size: int = 100):
    """
    Page through /api/charges and aggregate by call_type, agent_id, and model family.
    Capped at max_pages * page_size charges to keep it fast.
    """
    days = max(1, min(days, 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    by_call_type = defaultdict(lambda: {"credits": 0.0, "count": 0})
    by_agent = defaultdict(lambda: {"credits": 0.0, "count": 0})
    by_model_family = defaultdict(lambda: {"credits": 0.0, "count": 0})
    recent = []
    scanned = 0
    in_window = 0
    total_credits_window = 0.0

    async with httpx.AsyncClient() as c:
        page = 1
        while page <= max_pages:
            data = await _get(c, "/api/charges", page=page, page_size=page_size)
            charges = data.get("charges", [])
            if not charges:
                break

            stop = False
            for ch in charges:
                scanned += 1
                try:
                    ts = datetime.fromisoformat(ch["created_at"].replace(" ", "T"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                if ts < cutoff:
                    stop = True
                    break

                in_window += 1
                amt = float(ch.get("amount") or 0)
                total_credits_window += amt
                call_type = ch.get("call_type") or "unknown"
                agent = ch.get("agent_id") or "unknown"
                api_type = ch.get("api_type") or "unknown"

                # Classify model family for cleaner breakdown
                fam = _model_family(api_type)

                by_call_type[call_type]["credits"] += amt
                by_call_type[call_type]["count"] += 1
                by_agent[agent]["credits"] += amt
                by_agent[agent]["count"] += 1
                by_model_family[fam]["credits"] += amt
                by_model_family[fam]["count"] += 1

                if len(recent) < 50:
                    recent.append({
                        "ts": ch["created_at"],
                        "amount": amt,
                        "api_type": api_type,
                        "call_type": call_type,
                        "agent_id": agent,
                    })

            if stop or not data.get("pagination", {}).get("has_more"):
                break
            page += 1

    def _to_list(d):
        return sorted(
            [{"name": k, "credits": round(v["credits"], 6), "count": v["count"]} for k, v in d.items()],
            key=lambda x: -x["credits"],
        )

    return {
        "window_days": days,
        "scanned_charges": scanned,
        "charges_in_window": in_window,
        "total_credits_window": round(total_credits_window, 6),
        "by_call_type": _to_list(by_call_type),
        "by_agent": _to_list(by_agent),
        "by_model_family": _to_list(by_model_family),
        "recent": recent,
        "truncated": page > max_pages,
    }


def _model_family(api_type: str) -> str:
    """Bucket api_type strings into readable families."""
    s = (api_type or "").lower()
    if "claude" in s:
        if "opus" in s: return "Claude Opus"
        if "sonnet" in s: return "Claude Sonnet"
        if "haiku" in s: return "Claude Haiku"
        return "Claude (other)"
    if "gpt" in s or "openai" in s:
        if "codex" in s: return "GPT Codex"
        if "gpt-5" in s or "gpt5" in s: return "GPT-5"
        if "gpt-4" in s or "gpt4" in s: return "GPT-4"
        return "OpenAI (other)"
    if "gemini" in s or "google" in s:
        return "Gemini"
    if "deepseek" in s: return "DeepSeek"
    if "qwen" in s: return "Qwen"
    if "kimi" in s: return "Kimi"
    if "venice" in s: return "Venice"
    if "grok" in s or "xai" in s: return "Grok"
    if "minimax" in s: return "MiniMax"
    if "mimo" in s: return "MiMo"
    if "llama" in s or "meta-llama" in s: return "Llama"
    if "mistral" in s: return "Mistral"
    if "image" in s or "imagen" in s or "nano-banana" in s:
        return "Image generation"
    if "tts" in s or "voice" in s or "elevenlabs" in s:
        return "Voice / TTS"
    if "search" in s or "brave" in s or "tavily" in s:
        return "Web search"
    if "coingecko" in s or "coinglass" in s or "twelvedata" in s:
        return "Market data"
    return s or "unknown"


@app.get("/")
async def root():
    return FileResponse(os.path.join(HERE, "index.html"))


# Static assets (app.js, vendor, etc.)
app.mount("/static", StaticFiles(directory=HERE), name="static")


@app.get("/{path:path}")
async def fallback(path: str):
    # Serve sibling files (app.js, vendor/*) directly
    target = os.path.join(HERE, path)
    if os.path.isfile(target):
        return FileResponse(target)
    raise HTTPException(404, f"Not found: {path}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "7821"))
    uvicorn.run(app, host="0.0.0.0", port=port)
