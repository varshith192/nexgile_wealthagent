"""Live provider adapters.

These are the seams a hosted model plugs into. Each one implements the same
`AIProvider` interface as `MockAIService` and falls back to the deterministic
rules whenever a key is missing or a call fails — the product must never go
dark because an external service is unavailable.

To go live:
    1. Set AI_PROVIDER=anthropic (or openai) and AI_API_KEY in the backend env.
    2. Install the provider SDK.
    3. Implement `_complete()` below.

Nothing else in the application changes.
"""

from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)


class LiveProviderBase(AIProvider):
    """Shared plumbing for hosted providers.

    The financial rules still run first: the deterministic layer produces the
    numbers and the model is only ever asked to phrase them. That ordering is
    deliberate and must survive any future edit — see §4 of the product spec.
    """

    mode = "live"
    sdk_package = ""
    default_model = ""

    def __init__(self, api_key: str | None, model: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model or self.default_model
        self.timeout = timeout
        self._fallback = MockAIService()
        self._client: Any | None = None

    # -- configuration ------------------------------------------------
    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def info(self) -> AIProviderInfo:
        return AIProviderInfo(
            name=self.name,
            mode="live" if self.is_configured else "mock",
            model=self.model,
            description=(
                f"{self.name.title()} narration layered over the deterministic calculation engine."
                if self.is_configured
                else f"{self.name.title()} is selected but no API key is set; the deterministic rules engine is serving requests."
            ),
            capabilities=["insights", "recommendations", "next_actions", "document_classification", "calculation_explanation", "grounded_question_answering"],
            requires_api_key=True,
            is_configured=self.is_configured,
        )

    # -- the single method a real integration needs to fill in --------
    def _complete(self, system: str, prompt: str) -> str:  # pragma: no cover - integration seam
        """Send one prompt to the hosted model and return the raw text reply.

        Implement with the provider SDK. Raise on failure; callers fall back to
        the deterministic layer.
        """
        raise NotImplementedError(
            f"Install the {self.sdk_package} SDK and implement _complete() to enable the {self.name} provider."
        )

    def _narrate(self, system: str, prompt: str) -> str | None:
        if not self.is_configured:
            return None
        try:
            return self._complete(system, prompt)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("AI provider %s unavailable, using deterministic output: %s", self.name, exc)
            return None

    # -- interface ----------------------------------------------------
    GUARDRAIL = (
        "You are WealthAgent, a wealth-management analyst. You will be given figures that have already been "
        "verified by a deterministic calculation engine. Never invent, recompute or adjust a number. Explain only "
        "what the supplied data supports, name the as-of date, and state assumptions and limitations plainly. "
        "Do not give investment, tax or legal advice; frame everything as something to review with an advisor."
    )

    def generate_insights(self, context: AIContext) -> list[Insight]:
        insights = self._fallback.generate_insights(context)
        narration = self._narrate(
            self.GUARDRAIL,
            "Rewrite the summary of each insight below in clear, plain language. Keep every number exactly as given. "
            f"Return JSON as a list of objects with keys 'key' and 'summary'.\n\n{json.dumps([i.model_dump(mode='json') for i in insights])}",
        )
        if not narration:
            return insights
        try:
            rewrites = {row["key"]: row["summary"] for row in json.loads(narration)}
        except (json.JSONDecodeError, KeyError, TypeError):
            return insights
        for insight in insights:
            if insight.key in rewrites:
                insight.summary = rewrites[insight.key]
                insight.source = f"{self.name}_narration_over_deterministic_rules"
        return insights

    def generate_recommendations(self, context: AIContext) -> list[RecommendationDraft]:
        return self._fallback.generate_recommendations(context)

    def suggest_actions(self, context: AIContext) -> list[NextAction]:
        return self._fallback.suggest_actions(context)

    def classify_document(self, filename: str, metadata: dict[str, Any] | None = None) -> DocumentClassification:
        return self._fallback.classify_document(filename, metadata)

    def explain(self, calculation: dict[str, Any], audience: str = "client") -> Explanation:
        baseline = self._fallback.explain(calculation, audience)
        narration = self._narrate(
            self.GUARDRAIL,
            f"Explain this calculation for a {audience}. Keep every number identical.\n\n{json.dumps(calculation, default=str)}",
        )
        if narration:
            baseline.body = narration
            baseline.source = f"{self.name}_narration_over_deterministic_rules"
        return baseline

    def answer(self, question: str, context: AIContext) -> AgentAnswer:
        baseline = self._fallback.answer(question, context)
        narration = self._narrate(
            self.GUARDRAIL,
            "Answer the question using only these verified facts. Keep every number identical.\n\n"
            f"Question: {question}\n\nFacts: {json.dumps([f.model_dump(mode='json') for f in baseline.grounded_facts])}",
        )
        if narration:
            baseline.answer = narration
            baseline.source = f"{self.name}_narration_over_deterministic_rules"
        return baseline


class AnthropicProvider(LiveProviderBase):
    name = "anthropic"
    sdk_package = "anthropic"
    default_model = "claude-opus-5"

    def _complete(self, system: str, prompt: str) -> str:  # pragma: no cover - integration seam
        # from anthropic import Anthropic
        # client = self._client or Anthropic(api_key=self.api_key)
        # self._client = client
        # message = client.messages.create(
        #     model=self.model,
        #     max_tokens=2000,
        #     system=system,
        #     messages=[{"role": "user", "content": prompt}],
        # )
        # return message.content[0].text
        raise NotImplementedError(
            "Install the anthropic SDK and uncomment the implementation in AnthropicProvider._complete()."
        )


class OpenAIProvider(LiveProviderBase):
    name = "openai"
    sdk_package = "openai"
    default_model = "gpt-4o"

    def _complete(self, system: str, prompt: str) -> str:  # pragma: no cover - integration seam
        # from openai import OpenAI
        # client = self._client or OpenAI(api_key=self.api_key)
        # self._client = client
        # response = client.chat.completions.create(
        #     model=self.model,
        #     messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        # )
        # return response.choices[0].message.content or ""
        raise NotImplementedError(
            "Install the openai SDK and uncomment the implementation in OpenAIProvider._complete()."
        )
