"""Builds the configured planner provider (LLM_PROVIDER=local|gemini|openai)."""

from __future__ import annotations

from app.core.config import Settings
from app.llm.base import PlannerProvider
from app.llm.local import LocalPlanner
from app.services.values import load_value_index


def build_planner(settings: Settings) -> PlannerProvider:
    if settings.llm_provider == "gemini":
        from app.llm.gemini import GeminiPlanner

        return GeminiPlanner(settings.gemini_api_key, settings.gemini_model, settings.analytics_as_of_date,
                             settings.max_rows)
    if settings.llm_provider == "openai":
        from app.llm.openai_provider import OpenAIPlanner

        return OpenAIPlanner(settings.openai_api_key, settings.openai_model, settings.analytics_as_of_date,
                             settings.max_rows)
    values = load_value_index(settings.analytics_reader_database_url)
    return LocalPlanner(values, settings.analytics_as_of_date, settings.max_rows)
