"""
Provider-agnostic LLM access layer.

Both Ollama (http://localhost:11434/v1) and AITUNNEL (https://api.aitunnel.ru/v1)
expose an OpenAI-compatible Chat Completions API, so a single adapter covers
both -- and any other OpenAI-compatible endpoint -- without vendor lock-in.
No model or vendor name is hardcoded anywhere in this module.
"""
from __future__ import annotations
import os
import logging
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError

from novelforge.config import LLMConfig, LLMRoleModels

logger = logging.getLogger("novelforge.llm")

Role = str  # "writer" | "evaluator" | "reviewer"


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    usage: dict


class LLMProvider:
    """Single interface used by every tool in the pipeline."""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._primary = self._build_client(
            config.base_url, config.api_key_env, config.provider
        )
        self._primary_models = config.models
        self._fallback = None
        self._fallback_models = None
        if config.fallback_provider and config.fallback_base_url:
            self._fallback = self._build_client(
                config.fallback_base_url,
                config.fallback_api_key_env,
                config.fallback_provider,
            )
            self._fallback_models = config.fallback_models or config.models

    @staticmethod
    def _build_client(base_url: str, api_key_env: Optional[str], provider_name: str) -> OpenAI:
        api_key = os.environ.get(api_key_env, "not-needed") if api_key_env else "not-needed"
        return OpenAI(base_url=base_url, api_key=api_key)

    def _model_for(self, role: Role, models: LLMRoleModels) -> str:
        return getattr(models, role)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        role: Role = "writer",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResult:
        """Run a chat completion using the role-mapped model, with automatic
        failover to the configured fallback provider on error."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        temp = temperature if temperature is not None else self._config.temperature
        mtok = max_tokens if max_tokens is not None else self._config.max_tokens

        try:
            model = self._model_for(role, self._primary_models)
            resp = self._primary.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp,
                max_tokens=mtok,
                timeout=self._config.request_timeout_s,
            )
            return LLMResult(
                text=resp.choices[0].message.content or "",
                model=model,
                provider=self._config.provider,
                usage=dict(resp.usage) if resp.usage else {},
            )
        except (APIError, APITimeoutError, APIConnectionError) as exc:
            logger.warning("Primary provider failed (%s); attempting fallback.", exc)
            if not self._fallback:
                raise
            model = self._model_for(role, self._fallback_models)
            resp = self._fallback.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp,
                max_tokens=mtok,
                timeout=self._config.request_timeout_s,
            )
            return LLMResult(
                text=resp.choices[0].message.content or "",
                model=model,
                provider=self._config.fallback_provider or "fallback",
                usage=dict(resp.usage) if resp.usage else {},
            )
