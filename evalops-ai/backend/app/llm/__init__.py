"""Provider registry."""

from __future__ import annotations

from app.llm.base import LLMProvider, ProviderNotConfigured
from app.llm.local import LocalProvider, MockScriptedProvider

PROVIDERS = ("local", "mock_scripted", "gemini", "openai")


def get_provider(name: str) -> LLMProvider:
    if name == "local":
        return LocalProvider()
    if name == "mock_scripted":
        return MockScriptedProvider()
    if name == "gemini":
        from app.llm.gemini import GeminiProvider

        return GeminiProvider()
    if name == "openai":
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    raise ProviderNotConfigured(f"unknown provider '{name}'")


__all__ = ["PROVIDERS", "get_provider"]
