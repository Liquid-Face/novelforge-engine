"""
Phase 3b: dual-persona full-manuscript review, provider-agnostic (works with
any model reachable via LLMProvider -- local Ollama or AITUNNEL-hosted models).
"""
from __future__ import annotations
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.prompts.renderer import render_pair
from novelforge.tools.response import has_string_fields, parse_json_object


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
    cfg = layout.config.project
    system, prompt = render_pair("review_manuscript", full_manuscript=manuscript,
                                 language=cfg.language, genre=cfg.genre,
                                 target_audience=cfg.target_audience)
    result = llm.complete(
        system_prompt=system,
        user_prompt=prompt,
        role="reviewer",
        max_tokens=8192,
    )
    parsed = parse_json_object(result.text, ("critic_review", "professor_review", "actionable_items"))
    if (parsed is not None
            and has_string_fields(parsed, ("critic_review", "professor_review"))
            and isinstance(parsed["actionable_items"], list)
            and all(isinstance(item, str) for item in parsed["actionable_items"])):
        return parsed
    return {"critic_review": result.text, "professor_review": "", "actionable_items": []}
