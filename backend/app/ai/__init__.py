"""Isolated AI layer. Swap the provider, keep the application."""

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
    SupportingFact,
)
from app.ai.mock_ai import MockAIService
from app.ai.service import AIService, get_ai_service

__all__ = [
    "AgentAnswer",
    "AIContext",
    "AIProvider",
    "AIProviderInfo",
    "AIService",
    "DocumentClassification",
    "Explanation",
    "Insight",
    "MockAIService",
    "NextAction",
    "RecommendationDraft",
    "SupportingFact",
    "get_ai_service",
]
