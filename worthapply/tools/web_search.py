"""Web search tool — searches the web for verification information.

Uses Serper API when SERPER_API_KEY is set; otherwise falls back to
DuckDuckGo HTML results so local/dev verification still works.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 12.0


@dataclass
class SearchResult:
    title: str = ""
    url: str = ""
    snippet: str = ""


@dataclass
class SearchResponse:
    query: str = ""
    results: list[SearchResult] = field(default_factory=list)
    error: str | None = None
    elapsed_ms: float = 0.0
    provider: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None


async def web_search(query: str, num_results: int = 5) -> SearchResponse:
    api_key = os.getenv("SERPER_API_KEY")
    if api_key:
        resp = await _serper_search(query, api_key, num_results)
        if resp.ok and resp.results:
            return resp
        # Fall through to DDG if Serper fails/empty
        logger.warning("Serper failed or empty (%s); trying DuckDuckGo", resp.error)

    return await _duckduckgo_search(query, num_results)


async def _serper_search(
    query: str, api_key: str, num_results: int
) -> SearchResponse:
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                json={"q": query, "num": num_results},
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
            )
            elapsed = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return SearchResponse(
                    query=query,
                    error=f"Search API HTTP {resp.status_code}",
                    elapsed_ms=elapsed,
                    provider="serper",
                )

            data = resp.json()
            results = []
            for item in data.get("organic", [])[:num_results]:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                    )
                )

            return SearchResponse(
                query=query,
                results=results,
                elapsed_ms=round(elapsed, 1),
                provider="serper",
            )
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        return SearchResponse(
            query=query,
            error=f"Search failed: {exc}",
            elapsed_ms=elapsed,
            provider="serper",
        )


async def _duckduckgo_search(query: str, num_results: int) -> SearchResponse:
    """Lightweight HTML fallback (no API key)."""
    start = time.perf_counter()
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, headers=headers, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            elapsed = (time.perf_counter() - start) * 1000
            if resp.status_code != 200:
                return SearchResponse(
                    query=query,
                    error=f"DuckDuckGo HTTP {resp.status_code}",
                    elapsed_ms=elapsed,
                    provider="duckduckgo",
                )

            results = _parse_ddg_html(resp.text, num_results)
            if not results:
                return SearchResponse(
                    query=query,
                    error="DuckDuckGo returned no parseable results",
                    elapsed_ms=round(elapsed, 1),
                    provider="duckduckgo",
                )
            return SearchResponse(
                query=query,
                results=results,
                elapsed_ms=round(elapsed, 1),
                provider="duckduckgo",
            )
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        return SearchResponse(
            query=query,
            error=f"DuckDuckGo search failed: {exc}",
            elapsed_ms=elapsed,
            provider="duckduckgo",
        )


def _parse_ddg_html(html: str, num_results: int) -> list[SearchResult]:
    results: list[SearchResult] = []
    # result blocks
    blocks = re.findall(
        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
        r'(?:.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>)?',
        html,
        flags=re.I | re.S,
    )
    for href, title, snippet in blocks:
        title_clean = re.sub(r"<[^>]+>", "", title).strip()
        snip_clean = re.sub(r"<[^>]+>", "", snippet or "").strip()
        link = href
        # DDG sometimes wraps redirects
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            from urllib.parse import unquote

            link = unquote(m.group(1))
        if title_clean and link.startswith("http"):
            results.append(
                SearchResult(title=title_clean, url=link, snippet=snip_clean)
            )
        if len(results) >= num_results:
            break
    return results
