"""
Phase 3b: dual-persona full-manuscript review, provider-agnostic (works with
any model reachable via LLMProvider -- local Ollama or AITUNNEL-hosted models).
"""
from __future__ import annotations
import json
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.prompts.renderer import render


def build_full_manuscript(layout: ProjectLayout) -> str:
    cfg = layout.config.project
    parts = []
    for i in range(1, cfg.chapters_total + 1):
        p = layout.chapter_path(i)
        if p.exists():
            parts.append(f"\n\n## Глава {i}\n\n{layout.read(p)}")
    return "".join(parts)


def review_manuscript(layout: ProjectLayout, llm: LLMProvider) -> dict:
    manuscript = build_full_manuscript(layout)
    prompt = render("review_manuscript", full_manuscript=manuscript)
    result = llm.complete(
        system_prompt="You are a dual-persona literary reviewer (critic + professor of fiction).",
        user_prompt=prompt,
        role="reviewer",
        max_tokens=8192,
    )
    try:
        return json.loads(result.text)
    except json.JSONDecodeError:
        return {"critic_review": result.text, "professor_review": "", "actionable_items": []}
