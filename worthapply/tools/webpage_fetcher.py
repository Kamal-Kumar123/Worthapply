"""Webpage fetcher — retrieves and extracts readable content from URLs."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0
_MAX_CONTENT_LENGTH = 100_000
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class FetchResult:
    url: str
    status_code: int = 0
    content: str = ""
    title: str = ""
    error: str | None = None
    elapsed_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code == 200


async def fetch_webpage(url: str) -> FetchResult:
    """Fetch a webpage and extract its main text content."""
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            headers=_HEADERS,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            resp = await client.get(url)
            elapsed = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    error=f"HTTP {resp.status_code}",
                    elapsed_ms=elapsed,
                )

            raw_html = resp.text[:_MAX_CONTENT_LENGTH]
            title, content = _extract_content(raw_html)

            return FetchResult(
                url=url,
                status_code=200,
                content=content,
                title=title,
                elapsed_ms=round(elapsed, 1),
            )
    except httpx.TimeoutException:
        elapsed = (time.perf_counter() - start) * 1000
        return FetchResult(url=url, error="Request timed out", elapsed_ms=elapsed)
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        return FetchResult(url=url, error=str(exc), elapsed_ms=elapsed)


def _extract_content(html: str) -> tuple[str, str]:
    """Extract title and main text from HTML. Returns (title, content)."""
    try:
        import trafilatura

        content = trafilatura.extract(html, include_comments=False, include_tables=True)
        if content:
            title = _extract_title_bs4(html)
            return title, content
    except ImportError:
        pass
    except Exception:
        pass

    return _extract_with_bs4(html)


def _extract_title_bs4(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("title")
    return tag.get_text(strip=True) if tag else ""


def _extract_with_bs4(html: str) -> tuple[str, str]:
    """Fallback extraction using BeautifulSoup."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    content = "\n".join(lines)

    if len(content) > _MAX_CONTENT_LENGTH:
        content = content[:_MAX_CONTENT_LENGTH]

    return title, content
