"""
Brave Search API integration for real-time market research.

When Tier 2 fires, this module actively searches for context about
specific assets and market conditions — not just passive news polling.
"""

import asyncio
import time
from dataclasses import dataclass

import httpx

from . import config

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_NEWS_URL = "https://api.search.brave.com/res/v1/news/search"


@dataclass
class SearchResult:
    title: str
    description: str
    url: str
    age: str
    source: str


class BraveResearcher:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=15)
        self._cache: dict[str, tuple[float, list[SearchResult]]] = {}
        self._cache_ttl = 300  # 5 min cache per query

    async def search_news(self, query: str, count: int = 10) -> list[SearchResult]:
        """Search Brave News API for recent market news."""
        if not config.BRAVE_API_KEY:
            return []

        cached = self._get_cached(f"news:{query}")
        if cached is not None:
            return cached

        try:
            resp = await self._client.get(
                BRAVE_NEWS_URL,
                params={"q": query, "count": count, "freshness": "pd"},
                headers={
                    "X-Subscription-Token": config.BRAVE_API_KEY,
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    url=item.get("url", ""),
                    age=item.get("age", ""),
                    source=item.get("meta_url", {}).get("hostname", ""),
                ))

            self._set_cached(f"news:{query}", results)
            return results

        except Exception as e:
            print(f"[RESEARCH] Brave news error: {e}")
            return []

    async def search_web(self, query: str, count: int = 8) -> list[SearchResult]:
        """Search Brave Web API for broader market context."""
        if not config.BRAVE_API_KEY:
            return []

        cached = self._get_cached(f"web:{query}")
        if cached is not None:
            return cached

        try:
            resp = await self._client.get(
                BRAVE_SEARCH_URL,
                params={"q": query, "count": count, "freshness": "pd"},
                headers={
                    "X-Subscription-Token": config.BRAVE_API_KEY,
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("web", {}).get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    url=item.get("url", ""),
                    age=item.get("age", ""),
                    source=item.get("meta_url", {}).get("hostname", ""),
                ))

            self._set_cached(f"web:{query}", results)
            return results

        except Exception as e:
            print(f"[RESEARCH] Brave web error: {e}")
            return []

    async def research_asset(self, symbol: str) -> str:
        """
        Run targeted research queries for a specific asset.
        Returns formatted text ready for LLM context injection.
        """
        base = symbol.split("/")[0]  # BTC/USDT → BTC
        name_map = {
            "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
            "WOO": "WOO Network", "BNB": "BNB", "XRP": "XRP Ripple",
            "DOGE": "Dogecoin", "AVAX": "Avalanche", "ARB": "Arbitrum",
            "OP": "Optimism",
        }
        name = name_map.get(base, base)

        # Run news + context searches in parallel
        news_results, context_results, macro_results = await _gather_safe(
            self.search_news(f"{name} crypto price news today"),
            self.search_web(f"{name} {base} analysis outlook"),
            self.search_news("crypto market Bitcoin macro sentiment today"),
        )

        sections = []

        if news_results:
            lines = []
            for r in news_results[:6]:
                age = f" ({r.age})" if r.age else ""
                lines.append(f"- {r.title}{age} — {r.source}")
            sections.append(f"**{base} News:**\n" + "\n".join(lines))

        if context_results:
            lines = []
            for r in context_results[:4]:
                desc = r.description[:150] if r.description else r.title
                lines.append(f"- {desc} — {r.source}")
            sections.append(f"**{base} Analysis Context:**\n" + "\n".join(lines))

        if macro_results:
            lines = []
            for r in macro_results[:4]:
                age = f" ({r.age})" if r.age else ""
                lines.append(f"- {r.title}{age} — {r.source}")
            sections.append("**Macro/Market Sentiment:**\n" + "\n".join(lines))

        if not sections:
            return "No research results (Brave API key not set or search failed)."

        return "\n\n".join(sections)

    def _get_cached(self, key: str) -> list[SearchResult] | None:
        if key in self._cache:
            ts, results = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return results
            del self._cache[key]
        return None

    def _set_cached(self, key: str, results: list[SearchResult]):
        self._cache[key] = (time.time(), results)
        # Evict old entries
        now = time.time()
        expired = [k for k, (ts, _) in self._cache.items() if now - ts > self._cache_ttl]
        for k in expired:
            del self._cache[k]

    async def close(self):
        await self._client.aclose()


async def _gather_safe(*coros):
    results = await asyncio.gather(*coros, return_exceptions=True)
    return [r if not isinstance(r, Exception) else [] for r in results]
