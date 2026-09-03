"""
Rebuild derived documents (arc summary, outline) from the current chapter
text -- used when lore changes upstream and downstream docs must catch up.
"""
from __future__ import annotations
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.prompts.renderer import render_pair


def build_arc_summary(layout: ProjectLayout, llm: LLMProvider, force: bool = False) -> str:
    cfg = layout.config.project
    chapters_text = []
    for i in range(1, cfg.chapters_total + 1):
        p = layout.chapter_path(i)
        if p.exists():
            chapters_text.append(f"Глава {i}: {layout.read(p)[:1500]}")
    system, prompt = render_pair("build_arc_summary", chapters_text="\n\n".join(chapters_text),
                                 genre=cfg.genre, language=cfg.language,
                                 target_audience=cfg.target_audience)
    result = llm.complete(system_prompt=system, user_prompt=prompt, role="evaluator")
    layout.write_guarded(layout.arc_summary_path, result.text, force=force)
    return result.text
