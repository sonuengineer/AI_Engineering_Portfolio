from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.llm.base import LLMProvider, LLMRequest, Usage
from app.llm.embeddings import GeminiEmbedder, HashingEmbedder, OpenAIEmbedder, build_embedder


@lru_cache
def get_llm() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "gemini":
        from app.llm.remote import GeminiProvider

        return GeminiProvider(s.gemini_api_key, s.gemini_model_fast, s.gemini_model_strong)
    if s.llm_provider == "openai":
        from app.llm.remote import OpenAIProvider

        return OpenAIProvider(s.openai_api_key, s.openai_model_fast, s.openai_model_strong)
    from app.llm.local import LocalProvider

    return LocalProvider()


@lru_cache
def get_embedder() -> "HashingEmbedder | GeminiEmbedder | OpenAIEmbedder":
    return build_embedder(get_settings())


def traced_generate(request: LLMRequest, schema: Any) -> Any:
    """Call the configured provider inside an 'llm.generate' span (sizes and usage only, no text)."""
    from app.core.telemetry import tracer

    with tracer.start_as_current_span("llm.generate") as span:
        span.set_attribute("llm.task", request.task)
        span.set_attribute("llm.tier", request.tier)
        span.set_attribute("llm.prompt_chars", len(request.system) + len(request.user))
        result, usage = get_llm().generate(request, schema)
        span.set_attribute("llm.provider", usage.provider)
        span.set_attribute("llm.model", usage.model)
        span.set_attribute("llm.input_tokens", usage.input_tokens)
        span.set_attribute("llm.output_tokens", usage.output_tokens)
        span.set_attribute("llm.tokens_are_estimates", usage.tokens_are_estimates)
        return result, usage


__all__ = ["LLMProvider", "LLMRequest", "Usage", "get_embedder", "get_llm", "traced_generate"]
