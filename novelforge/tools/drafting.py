"""
Drafting-phase tools: writing and evaluating a single chapter.
"""
from __future__ import annotations
import json
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.prompts.renderer import render


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
                   revision_brief: str = "", force: bool = False) -> str:
    cfg = layout.config.project
    outline = layout.read(layout.outline_path)
    prompt = render(
        "draft_chapter",
        chapter_index=chapter_index,
        genre=cfg.genre,
        language=cfg.language,
        voice=layout.read(layout.voice_path),
        canon=layout.read(layout.canon_path),
        chapter_beats=_extract_chapter_beats(outline, chapter_index),
        arc_summary=layout.read(layout.arc_summary_path),
        revision_brief=revision_brief,
        length_min=cfg.chapter_length_words[0],
        length_max=cfg.chapter_length_words[1],
    )
    result = llm.complete(system_prompt="You are a novelist ghostwriter.", user_prompt=prompt, role="writer")
    layout.write_guarded(layout.chapter_path(chapter_index), result.text, force=force)
    return result.text


def evaluate_chapter(layout: ProjectLayout, llm: LLMProvider, chapter_index: int) -> dict:
    outline = layout.read(layout.outline_path)
    chapter_text = layout.read(layout.chapter_path(chapter_index))
    prompt = render(
        "evaluate_chapter",
        chapter_beats=_extract_chapter_beats(outline, chapter_index),
        voice=layout.read(layout.voice_path),
        chapter_text=chapter_text,
    )
    result = llm.complete(system_prompt="You are an independent literary evaluator.", user_prompt=prompt, role="evaluator")
    try:
        return json.loads(result.text)
    except json.JSONDecodeError:
        return {"score": 0.0, "issues": [result.text]}
