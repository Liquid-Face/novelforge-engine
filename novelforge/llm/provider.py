"""
Role-first, provider-agnostic LLM access layer with cumulative token-usage
tracking (per run) and reporter callbacks for role/model/fallback visibility.
"""
from __future__ import annotations
import os
import logging
from dataclasses import dataclass
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError

from novelforge.config import LLMConfig, EndpointConfig, RoleName

logger = logging.getLogger("novelforge.llm")


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    usage: dict
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class TokenUsageTotals:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    has_usage_data: bool = False

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        if prompt_tokens or completion_tokens:
            self.has_usage_data = True
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens


class LLMProvider:
    """Single interface used by every tool in the pipeline. Resolves the
    correct endpoint for a given role, fails over to that role's fallback
    endpoint on error, and accumulates token usage totals for the run.

    Reporter injection keeps role/model/fallback observability local to the
    LLM boundary (where the truth actually exists), instead of duplicating it
    in graph nodes or tools.
    """

    def __init__(self, config: LLMConfig, reporter=None):
        self._config = config
        self._reporter = reporter
        self._clients: dict[tuple[str, str | None], OpenAI] = {}
        self.usage_totals = TokenUsageTotals()

    def _client_for(self, endpoint: EndpointConfig) -> OpenAI:
        key = (endpoint.base_url, endpoint.api_key_env)
        if key not in self._clients:
            api_key = os.environ.get(endpoint.api_key_env, "not-needed") if endpoint.api_key_env else "not-needed"
            self._clients[key] = OpenAI(base_url=endpoint.base_url, api_key=api_key)
        return self._clients[key]

    def _call(self, endpoint: EndpointConfig, system_prompt: str, user_prompt: str,
               temperature: float | None, max_tokens: int | None, role: RoleName,
               is_fallback: bool = False) -> LLMResult:
        client = self._client_for(endpoint)
        temp, mtok, timeout = self._config.resolved_defaults_for(endpoint)
        temp = temperature if temperature is not None else temp
        mtok = max_tokens if max_tokens is not None else mtok

        if self._reporter:
            self._reporter.role_call(role, endpoint.provider, endpoint.model, fallback=is_fallback)
            self._reporter.llm_request_waiting(role, endpoint.provider, endpoint.model)

        resp = client.chat.completions.create(
            model=endpoint.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temp,
            max_tokens=mtok,
            timeout=timeout,
        )
        usage = dict(resp.usage) if resp.usage else {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        self.usage_totals.record(prompt_tokens, completion_tokens)

        if self._reporter:
            self._reporter.llm_response_received(role, endpoint.provider, endpoint.model, prompt_tokens, completion_tokens)

        return LLMResult(
            text=resp.choices[0].message.content or "",
            model=endpoint.model,
            provider=endpoint.provider,
            usage=usage,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        role: RoleName = "writer",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        role_config = self._config.roles[role]
        try:
            return self._call(role_config.primary, system_prompt, user_prompt, temperature, max_tokens, role, is_fallback=False)
        except (APIError, APITimeoutError, APIConnectionError) as exc:
            if not role_config.fallback:
                raise
            logger.warning("Primary endpoint for role '%s' failed (%s); using fallback.", role, exc)
            if self._reporter:
                self._reporter.warning(
                    f"Primary endpoint failed for role '{role}' ({role_config.primary.provider} / {role_config.primary.model}); using fallback."
                )
            return self._call(role_config.fallback, system_prompt, user_prompt, temperature, max_tokens, role, is_fallback=True)
