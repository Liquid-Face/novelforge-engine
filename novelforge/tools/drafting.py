"""
Drafting-phase tools: writing and evaluating a single chapter.
"""
from __future__ import annotations
import json
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.prompts.renderer import render_pair


def _parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    return json.loads(cleaned)


def _extract_chapter_beats(outline_text: str, chapter_index: int) -> str:
    """Naively slices the outline markdown around the chapter heading; a
    more robust structured-outline parser can replace this without touching
    any other tool."""
    marker = f"## Глава {chapter_index}"
    marker_en = f"## Chapter {chapter_index}"
    for m in (marker, marker_en):
        if m in outline_text:
            start = outline_text.index(m)
            rest = outline_text[start:]
            next_marker_pos = min(
                [rest.find(x, len(m)) for x in ("\n## ",) if rest.find(x, len(m)) != -1] or [len(rest)]
            )
            return rest[:next_marker_pos]
    return outline_text


def draft_chapter(layout: ProjectLayout, llm: LLMProvider, chapter_index: int,
                   revision_brief: str = "", force: bool = False, iteration: int = 0) -> dict:
    cfg = layout.config.project
    outline = layout.read(layout.outline_path)
    system, prompt = render_pair(
        "draft_chapter",
        chapter_index=chapter_index,
        genre=cfg.genre,
        language=cfg.language,
        target_audience=cfg.target_audience,
        voice=layout.read(layout.voice_path),
        canon=layout.read(layout.canon_path),
        chapter_beats=_extract_chapter_beats(outline, chapter_index),
        arc_summary=layout.read(layout.arc_summary_path),
        revision_brief=revision_brief,
        length_min=cfg.chapter_length_words[0],
        length_max=cfg.chapter_length_words[1],
    )
    result = llm.complete(system_prompt=system, user_prompt=prompt, role="writer")
    layout.write_guarded(layout.chapter_path(chapter_index), result.text, force=force)
    return {"text": result.text, "prompt": prompt, "system_prompt": system,
            "writer": {"provider": result.provider, "model": result.model,
                        "fallback": getattr(result, "fallback", False)}}


def evaluate_chapter(layout: ProjectLayout, llm: LLMProvider, chapter_index: int) -> dict:
    outline = layout.read(layout.outline_path)
    chapter_text = layout.read(layout.chapter_path(chapter_index))
    system, prompt = render_pair(
        "evaluate_chapter",
        chapter_beats=_extract_chapter_beats(outline, chapter_index),
        voice=layout.read(layout.voice_path),
        chapter_text=chapter_text,
        language=layout.config.project.language,
        genre=layout.config.project.genre,
        target_audience=layout.config.project.target_audience,
    )
    result = llm.complete(system_prompt=system, user_prompt=prompt, role="evaluator")
    try:
        parsed = _parse_json_response(result.text)
        parsed["_evaluator"] = {"provider": result.provider, "model": result.model}
        return parsed
    except json.JSONDecodeError:
        return {"score": 0.0, "issues": [result.text], "raw": result.text,
                "_evaluator": {"provider": result.provider, "model": result.model}}
