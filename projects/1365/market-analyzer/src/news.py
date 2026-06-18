"""
News feed for market analysis context.

Sources:
- CryptoPanic: free API, crypto-focused, includes sentiment
- RSS fallback: CoinDesk, CoinTelegraph, The Block
- Optional Twitter/X search enrichment (if enabled)
"""

import asyncio
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from . import config


CRYPTOPANIC_TOKEN = os.getenv("CRYPTOPANIC_API_TOKEN", "")

# Twitter skill (script-mode) bridge
_SKILL_TWITTER_PATH = Path("/data/workspace/skills/twitter")
if _SKILL_TWITTER_PATH.exists() and str(_SKILL_TWITTER_PATH) not in sys.path:
    sys.path.insert(0, str(_SKILL_TWITTER_PATH))

try:
    from exports import twitter_search_tweets  # type: ignore
except Exception:
    twitter_search_tweets = None

# Symbol → CryptoPanic currency codes
SYMBOL_MAP = {
    "BTC/USDT": "BTC",
    "ETH/USDT": "ETH",
    "SOL/USDT": "SOL",
    "WOO/USDT": "WOO",
    "BNB/USDT": "BNB",
    "XRP/USDT": "XRP",
    "DOGE/USDT": "DOGE",
    "AVAX/USDT": "AVAX",
    "ARB/USDT": "ARB",
    "OP/USDT": "OP",
}

RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://www.theblock.co/rss.xml",
]


@dataclass
class NewsItem:
    title: str
    source: str
    timestamp: float
    url: str
    sentiment: str  # "positive", "negative", "neutral", or "unknown"
    currencies: list[str]


class NewsFeed:
    def __init__(self, poll_interval: int = 300):
        self._poll_interval = poll_interval
        self._cache: deque[NewsItem] = deque(maxlen=300)
        self._last_fetch: float = 0
        self._client = httpx.AsyncClient(timeout=15, follow_redirects=True)

    async def start(self):
        """Background loop that fetches news periodically."""
        while True:
            try:
                await self._fetch_all()
            except Exception as e:
                print(f"[NEWS] Fetch error: {e}")
            await asyncio.sleep(self._poll_interval)

    async def _fetch_all(self):
        tasks = [self._fetch_rss()]
        if CRYPTOPANIC_TOKEN:
            tasks.append(self._fetch_cryptopanic())
        if config.ENABLE_TWITTER_NEWS and twitter_search_tweets:
            tasks.append(self._fetch_twitter())

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                print(f"[NEWS] Source error: {r}")
        self._last_fetch = time.time()

    async def _fetch_cryptopanic(self):
        url = (
            f"https://cryptopanic.com/api/v1/posts/"
            f"?auth_token={CRYPTOPANIC_TOKEN}"
            f"&kind=news&public=true"
        )
        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("results", []):
            currencies = [
                c.get("code", "")
                for c in item.get("currencies", [])
            ]
            sentiment = "unknown"
            votes = item.get("votes", {})
            pos = votes.get("positive", 0) + votes.get("important", 0)
            neg = votes.get("negative", 0) + votes.get("toxic", 0)
            if pos > neg and pos > 0:
                sentiment = "positive"
            elif neg > pos and neg > 0:
                sentiment = "negative"
            elif pos > 0 or neg > 0:
                sentiment = "neutral"

            # Use the actual publish time, not fetch time, so age labels are real
            ts = time.time()
            published = item.get("published_at") or item.get("created_at")
            if published:
                try:
                    ts = datetime.fromisoformat(
                        published.replace("Z", "+00:00")
                    ).timestamp()
                except ValueError:
                    pass

            news = NewsItem(
                title=item.get("title", ""),
                source=item.get("source", {}).get("title", "cryptopanic"),
                timestamp=ts,
                url=item.get("url", ""),
                sentiment=sentiment,
                currencies=currencies,
            )

            self._append_if_new(news)

    async def _fetch_twitter(self):
        if not twitter_search_tweets:
            return

        # broad market query to gather fresh catalysts; symbol filtering
        # is handled later in get_for_symbol
        query = (
            "(bitcoin OR btc OR ethereum OR eth OR solana OR sol OR crypto) "
            "(ETF OR sec OR listing OR exploit OR hack OR upgrade OR partnership OR macro OR rates) "
            "-is:retweet lang:en"
        )

        try:
            payload = await asyncio.to_thread(twitter_search_tweets, query, None)
        except Exception as e:
            print(f"[NEWS] Twitter skill error: {e}")
            return

        tweets = payload.get("tweets", []) if isinstance(payload, dict) else []

        for tw in tweets[: max(1, config.TWITTER_NEWS_POSTS)]:
            text = (tw.get("text") or "").strip()
            if not text:
                continue

            ts = time.time()
            created = tw.get("created_at") or tw.get("createdAt")
            if created:
                try:
                    ts = datetime.fromisoformat(str(created).replace("Z", "+00:00")).timestamp()
                except ValueError:
                    pass

            url = tw.get("url") or ""
            tid = tw.get("id")
            user = tw.get("author", {}).get("userName") or tw.get("author", {}).get("username")
            if not url and tid and user:
                url = f"https://x.com/{user}/status/{tid}"

            currencies = self._extract_currencies(text)
            sentiment = self._naive_sentiment(text)
            headline = self._compact_text(text)

            news = NewsItem(
                title=headline,
                source="x.com",
                timestamp=ts,
                url=url,
                sentiment=sentiment,
                currencies=currencies,
            )
            self._append_if_new(news)

    def _append_if_new(self, news: NewsItem):
        # Deduplicate by exact title
        if any(n.title == news.title for n in self._cache):
            return
        self._cache.append(news)

    async def _fetch_rss(self):
        for feed_url in RSS_FEEDS:
            try:
                resp = await self._client.get(feed_url)
                resp.raise_for_status()
                root = ET.fromstring(resp.text)

                # Handle both RSS 2.0 and Atom
                items = root.findall(".//item")
                if not items:
                    items = root.findall(
                        ".//{http://www.w3.org/2005/Atom}entry"
                    )

                for item in items[:10]:  # latest 10 per feed
                    title_el = item.find("title")
                    if title_el is None:
                        title_el = item.find(
                            "{http://www.w3.org/2005/Atom}title"
                        )
                    link_el = item.find("link")
                    if link_el is None:
                        link_el = item.find(
                            "{http://www.w3.org/2005/Atom}link"
                        )

                    title = title_el.text if title_el is not None else ""
                    if link_el is not None:
                        url = link_el.text or link_el.get("href", "")
                    else:
                        url = ""

                    if not title:
                        continue

                    # Parse publish date
                    pub_ts = time.time()
                    pub_el = item.find("pubDate")
                    if pub_el is None:
                        pub_el = item.find(
                            "{http://www.w3.org/2005/Atom}published"
                        )
                    if pub_el is None:
                        pub_el = item.find(
                            "{http://www.w3.org/2005/Atom}updated"
                        )
                    if pub_el is not None and pub_el.text:
                        try:
                            from email.utils import parsedate_to_datetime
                            pub_ts = parsedate_to_datetime(pub_el.text).timestamp()
                        except Exception:
                            try:
                                # ISO 8601 fallback
                                dt = datetime.fromisoformat(pub_el.text.replace("Z", "+00:00"))
                                pub_ts = dt.timestamp()
                            except Exception:
                                pass

                    # Detect mentioned currencies from title
                    currencies = self._extract_currencies(title)

                    news = NewsItem(
                        title=title.strip(),
                        source=feed_url.split("/")[2],
                        timestamp=pub_ts,
                        url=url.strip() if url else "",
                        sentiment="unknown",
                        currencies=currencies,
                    )

                    self._append_if_new(news)

            except Exception as e:
                print(f"[NEWS] RSS error {feed_url}: {e}")

    def _extract_currencies(self, text: str) -> list[str]:
        """Extract crypto ticker mentions from text."""
        found = []
        text_upper = text.upper()
        keywords = {
            "BITCOIN": "BTC", "BTC": "BTC",
            "ETHEREUM": "ETH", "ETH": "ETH", "ETHER": "ETH",
            "SOLANA": "SOL", "SOL": "SOL",
            "WOO": "WOO",
            "BNB": "BNB", "BINANCE": "BNB",
            "XRP": "XRP", "RIPPLE": "XRP",
            "DOGE": "DOGE", "DOGECOIN": "DOGE",
            "AVALANCHE": "AVAX", "AVAX": "AVAX",
            "ARBITRUM": "ARB", "ARB": "ARB",
            "OPTIMISM": "OP",
        }
        for keyword, code in keywords.items():
            if re.search(rf"\b{keyword}\b", text_upper):
                if code not in found:
                    found.append(code)
        return found

    @staticmethod
    def _compact_text(text: str, max_len: int = 170) -> str:
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 1].rstrip() + "…"

    @staticmethod
    def _naive_sentiment(text: str) -> str:
        t = text.lower()
        pos_words = ("surge", "bull", "approval", "beats", "partnership", "launch", "upgrade", "growth")
        neg_words = ("dump", "bear", "reject", "hack", "exploit", "lawsuit", "ban", "liquidation")
        pos = sum(1 for w in pos_words if w in t)
        neg = sum(1 for w in neg_words if w in t)
        if pos > neg and pos > 0:
            return "positive"
        if neg > pos and neg > 0:
            return "negative"
        if pos or neg:
            return "neutral"
        return "unknown"

    def get_for_symbol(self, symbol: str, n: int = 10) -> list[NewsItem]:
        """Get recent news relevant to a trading pair.

        Symbol-specific items first (newest first), general market news
        fills the remaining slots.
        """
        code = SYMBOL_MAP.get(symbol, symbol.split("/")[0])
        items = sorted(self._cache, key=lambda i: i.timestamp, reverse=True)
        specific = [i for i in items if code in i.currencies]
        general = [i for i in items if not i.currencies]
        return (specific + general)[:n]

    def format_for_llm(self, symbol: str, n: int = 8) -> str:
        """Format recent news as text context for LLM injection."""
        items = self.get_for_symbol(symbol, n)
        if not items:
            return "No recent news available."

        lines = []
        for item in items:
            sentiment_tag = ""
            if item.sentiment != "unknown":
                sentiment_tag = f" [{item.sentiment}]"
            age_min = max(0, int((time.time() - item.timestamp) / 60))
            if age_min < 60:
                age_str = f"{age_min}m ago"
            else:
                age_str = f"{age_min // 60}h ago"
            lines.append(
                f"- {item.title}{sentiment_tag} ({item.source}, {age_str})"
            )

        return "\n".join(lines)

    async def close(self):
        await self._client.aclose()
