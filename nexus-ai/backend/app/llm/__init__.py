from functools import lru_cache

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


__all__ = ["LLMProvider", "LLMRequest", "Usage", "get_embedder", "get_llm"]
