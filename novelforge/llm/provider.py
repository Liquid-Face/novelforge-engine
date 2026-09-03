"""
Role-first, provider-agnostic LLM access layer.

Every pipeline role (writer/evaluator/reviewer) owns its own primary
endpoint and an optional fallback endpoint (see novelforge.config.RoleConfig).
This lets each role be routed independently -- e.g. a small local Ollama
model for drafting while evaluator/reviewer use a large-context cloud model
via AITUNNEL -- with its own independent failover target.

Both Ollama (http://localhost:11434/v1) and AITUNNEL (https://api.aitunnel.ru/v1)
expose an OpenAI-compatible Chat Completions API, so a single adapter covers
both -- and any other OpenAI-compatible endpoint -- without vendor lock-in.
No model or vendor name is hardcoded anywhere in this module.
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


class LLMProvider:
    """Single interface used by every tool in the pipeline. Resolves the
    correct endpoint for a given role and transparently fails over to that
    role's fallback endpoint (if configured) on error."""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._clients: dict[tuple[str, str | None], OpenAI] = {}

    def _client_for(self, endpoint: EndpointConfig) -> OpenAI:
        """Lazily builds and caches one OpenAI client per unique
        (base_url, api_key_env) pair, so roles sharing an endpoint reuse it."""
        key = (endpoint.base_url, endpoint.api_key_env)
        if key not in self._clients:
            api_key = os.environ.get(endpoint.api_key_env, "not-needed") if endpoint.api_key_env else "not-needed"
            self._clients[key] = OpenAI(base_url=endpoint.base_url, api_key=api_key)
        return self._clients[key]

    def _call(self, endpoint: EndpointConfig, system_prompt: str, user_prompt: str,
               temperature: float | None, max_tokens: int | None) -> LLMResult:
        client = self._client_for(endpoint)
        temp, mtok, timeout = self._config.resolved_defaults_for(endpoint)
        temp = temperature if temperature is not None else temp
        mtok = max_tokens if max_tokens is not None else mtok
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
        return LLMResult(
            text=resp.choices[0].message.content or "",
            model=endpoint.model,
            provider=endpoint.provider,
            usage=dict(resp.usage) if resp.usage else {},
        )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        role: RoleName = "writer",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        """Runs a chat completion using the endpoint configured for `role`,
        with automatic failover to that role's fallback endpoint on error."""
        role_config = self._config.roles[role]
        try:
            return self._call(role_config.primary, system_prompt, user_prompt, temperature, max_tokens)
        except (APIError, APITimeoutError, APIConnectionError) as exc:
            if not role_config.fallback:
                raise
            logger.warning("Primary endpoint for role '%s' failed (%s); using fallback.", role, exc)
            return self._call(role_config.fallback, system_prompt, user_prompt, temperature, max_tokens)
