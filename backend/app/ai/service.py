"""The one entry point the rest of the application uses to reach the AI layer.

Callers never import a provider directly. They call `AIService`, which resolves
the configured provider once and degrades to the deterministic rules engine if
a live provider is selected without a key.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.ai.base import (
    AgentAnswer,
    AIContext,
    AIProvider,
    AIProviderInfo,
    DocumentClassification,
    Explanation,
    Insight,
    NextAction,
    RecommendationDraft,
)
from app.ai.mock_ai import MockAIService
from app.ai.providers import AnthropicProvider, OpenAIProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

PROVIDER_REGISTRY: dict[str, type[AIProvider]] = {
    "mock": MockAIService,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}


def build_provider() -> AIProvider:
    """Resolve AI_PROVIDER into a live instance, falling back when unconfigured."""
    key = (settings.ai_provider or "mock").lower()
    provider_cls = PROVIDER_REGISTRY.get(key)

    if provider_cls is None:
        logger.warning("Unknown AI_PROVIDER %r; using the deterministic rules engine.", key)
        return MockAIService()

    if provider_cls is MockAIService:
        return MockAIService()

    if not settings.ai_api_key:
        # AI_API_KEY is optional by design; the product must run without it.
        logger.info("AI_PROVIDER=%s selected without AI_API_KEY; serving deterministic insights.", key)
        return MockAIService()

    return provider_cls(api_key=settings.ai_api_key, model=settings.ai_model, timeout=settings.ai_timeout_seconds)


class AIService:
    """Facade over whichever provider is configured."""

    def __init__(self, provider: AIProvider | None = None) -> None:
        self.provider = provider or build_provider()

    @property
    def info(self) -> AIProviderInfo:
        return self.provider.info()

    def insights(self, context: AIContext) -> list[Insight]:
        return self.provider.generate_insights(context)

    def recommendations(self, context: AIContext) -> list[RecommendationDraft]:
        return self.provider.generate_recommendations(context)

    def actions(self, context: AIContext) -> list[NextAction]:
        return self.provider.suggest_actions(context)

    def classify_document(self, filename: str, metadata: dict[str, Any] | None = None) -> DocumentClassification:
        return self.provider.classify_document(filename, metadata)

    def explain(self, calculation: dict[str, Any], audience: str = "client") -> Explanation:
        return self.provider.explain(calculation, audience)

    def answer(self, question: str, context: AIContext) -> AgentAnswer:
        return self.provider.answer(question, context)


@lru_cache
def get_ai_service() -> AIService:
    return AIService()
