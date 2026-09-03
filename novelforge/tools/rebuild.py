"""
Rebuild derived documents (arc summary, outline) from the current chapter
text -- used when lore changes upstream and downstream docs must catch up.
"""
from __future__ import annotations
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider


def build_arc_summary(layout: ProjectLayout, llm: LLMProvider, force: bool = False) -> str:
    cfg = layout.config.project
    chapters_text = []
    for i in range(1, cfg.chapters_total + 1):
        p = layout.chapter_path(i)
        if p.exists():
            chapters_text.append(f"Глава {i}: {layout.read(p)[:1500]}")
    joined = "\n\n".join(chapters_text)
    prompt = (
        "Составь краткое хронологическое резюме сюжетных событий по главам ниже, "
        "не длиннее 800 слов, для использования как контекст при написании следующей главы.\n\n"
        f"{joined}"
    )
    result = llm.complete(system_prompt="You summarize novel plot progression concisely.", user_prompt=prompt, role="evaluator")
    layout.write_guarded(layout.arc_summary_path, result.text, force=force)
    return result.text
