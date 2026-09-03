"""
Revision-phase tools: adversarial editing, reader panel, brief generation,
and rewriting a chapter from a brief.
"""
from __future__ import annotations
import json
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.prompts.renderer import render

DEFAULT_PERSONAS = [
    ("Genre Fan", "заядлый читатель этого жанра, ищущий динамику и напряжение"),
    ("Literary Critic", "требовательный литературный критик, ценящий стиль"),
    ("Casual Reader", "случайный читатель без специальных ожиданий"),
    ("Skeptical Editor", "редактор издательства, ищущий причины отказать"),
]


def adversarial_edit(layout: ProjectLayout, llm: LLMProvider, chapter_index: int, cut_percent: int = 10) -> list[dict]:
    chapter_text = layout.read(layout.chapter_path(chapter_index))
    prompt = render("adversarial_edit", chapter_text=chapter_text, cut_percent=cut_percent)
    result = llm.complete(system_prompt="You are a ruthless prose editor.", user_prompt=prompt, role="evaluator")
    try:
        return json.loads(result.text)
    except json.JSONDecodeError:
        return []


def reader_panel(layout: ProjectLayout, llm: LLMProvider, chapter_index: int) -> list[dict]:
    chapter_text = layout.read(layout.chapter_path(chapter_index))
    reactions = []
    for name, desc in DEFAULT_PERSONAS:
        prompt = render("reader_panel", persona_name=name, persona_description=desc, chapter_text=chapter_text)
        result = llm.complete(system_prompt="You role-play as a reader persona.", user_prompt=prompt, role="evaluator")
        try:
            reactions.append(json.loads(result.text))
        except json.JSONDecodeError:
            reactions.append({"persona": name, "reaction": result.text, "would_continue_reading": None})
    return reactions


def gen_brief(layout: ProjectLayout, llm: LLMProvider, chapter_index: int, feedback_bundle: str, force: bool = False) -> str:
    prompt = render("gen_brief", chapter_index=chapter_index, feedback_bundle=feedback_bundle)
    result = llm.complete(system_prompt="You write concise, actionable revision briefs.", user_prompt=prompt, role="evaluator")
    brief_path = layout.briefs_dir / f"brief_ch_{chapter_index:02d}.md"
    layout.write_guarded(brief_path, result.text, force=force)
    return result.text


def gen_revision(layout: ProjectLayout, llm: LLMProvider, chapter_index: int, force: bool = False) -> str:
    from novelforge.tools.drafting import draft_chapter
    brief_path = layout.briefs_dir / f"brief_ch_{chapter_index:02d}.md"
    brief = layout.read(brief_path)
    return draft_chapter(layout, llm, chapter_index, revision_brief=brief, force=force)


def apply_cuts(layout: ProjectLayout, chapter_index: int, cuts: list[dict], force: bool = False) -> str:
    """Mechanically removes/compresses quoted fragments flagged by
    adversarial_edit -- no LLM call, pure text transform."""
    text = layout.read(layout.chapter_path(chapter_index))
    for cut in cuts:
        quote = cut.get("quote", "")
        if quote and quote in text:
            text = text.replace(quote, "" if cut.get("action") == "cut" else "")
    layout.write_guarded(layout.chapter_path(chapter_index), text, force=force)
    return text
