"""Tests for LLM provider selection and base functionality."""

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from worthapply.providers.base import LLMProvider, LLMResponse, LLMUsage
from worthapply.providers.factory import get_provider


class TestLLMUsage:
    def test_default_values(self):
        usage = LLMUsage()
        assert usage.input_tokens == 0
        assert usage.estimated_cost_usd == 0.0

    def test_custom_values(self):
        usage = LLMUsage(
            model="grok-3-mini-fast",
            provider="xai",
            input_tokens=100,
            output_tokens=200,
        )
        assert usage.total_tokens == 0  # not auto-computed


class TestLLMResponse:
    def test_ok_response(self):
        resp = LLMResponse(content="Hello")
        assert resp.ok
        assert resp.content == "Hello"

    def test_error_response(self):
        resp = LLMResponse(error="API error")
        assert not resp.ok
        assert resp.error == "API error"


class TestProviderFactory:
    def test_xai_requires_api_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "xai"}, clear=False):
            env = os.environ.copy()
            env.pop("XAI_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(EnvironmentError, match="XAI_API_KEY"):
                    get_provider()

    def test_unknown_provider_raises(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}):
            with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
                get_provider()

    def test_local_provider_creates(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "local"}):
            provider = get_provider()
            assert provider.provider_name == "local"

    def test_default_is_xai(self):
        env = os.environ.copy()
        env.pop("LLM_PROVIDER", None)
        env["XAI_API_KEY"] = "test-key"
        with patch.dict(os.environ, env, clear=True):
            provider = get_provider()
            assert provider.provider_name == "xai"


class TestBaseCostTracking:
    def test_estimate_cost(self):
        from worthapply.providers.local_provider import LocalProvider

        provider = LocalProvider()
        cost = provider._estimate_cost(1000, 500)
        assert cost == 0.0  # local provider has zero cost

    def test_cumulative_tracking(self):
        from worthapply.providers.local_provider import LocalProvider

        provider = LocalProvider()
        assert provider.get_total_cost() == 0.0
        assert provider.get_total_tokens() == 0
        assert len(provider.get_cumulative_usage()) == 0
