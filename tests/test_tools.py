"""Tests for WorthApply tools."""

import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from worthapply.tools.resume_parser import parse_resume
from worthapply.tools.web_search import web_search, SearchResponse
from worthapply.tools.webpage_fetcher import fetch_webpage, FetchResult


class TestResumeParser:
    def test_unsupported_format(self):
        result = parse_resume("file.xyz", filename="file.xyz")
        assert result == ""

    def test_txt_file(self, tmp_path):
        txt = tmp_path / "resume.txt"
        txt.write_text("John Doe\nSoftware Engineer\nPython, Java, SQL")
        result = parse_resume(str(txt))
        assert "John Doe" in result
        assert "Python" in result


class TestWebSearch:
    def test_no_api_key_falls_back_to_duckduckgo(self):
        with patch.dict("os.environ", {}, clear=True):
            result = asyncio.run(web_search("test query"))
            assert result.provider == "duckduckgo"
            # Offline / blocked networks fail; otherwise DDG may return hits.
            if not result.ok:
                assert "DuckDuckGo" in (result.error or "")


class TestWebpageFetcher:
    def test_invalid_url(self):
        result = asyncio.run(fetch_webpage("not-a-url"))
        assert not result.ok
        assert result.error is not None

    def test_timeout_handling(self):
        result = asyncio.run(fetch_webpage("http://192.0.2.1:1"))
        assert not result.ok
