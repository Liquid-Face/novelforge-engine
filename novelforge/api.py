"""
Public, UI-agnostic API. Both the CLI and any future web/GUI layer should
call these functions instead of duplicating orchestration logic.
"""
from __future__ import annotations
from pathlib import Path
from novelforge.project import ProjectLayout
from novelforge.config import ProjectConfig
from novelforge.llm.provider import LLMProvider
from novelforge.graphs.foundation_graph import build_foundation_graph
from novelforge.graphs.drafting_graph import build_drafting_graph
from novelforge.graphs.revision_graph import build_revision_graph
from novelforge.graphs.review_graph import build_review_graph
from novelforge.tools import foundation as F
from novelforge.tools.export import build_tex, typeset_pdf, build_epub


def _layout_and_llm(project_dir: str) -> tuple[ProjectLayout, LLMProvider]:
    layout = ProjectLayout.open(project_dir)
    layout.ensure_dirs()
    return layout, LLMProvider(layout.config.llm)


def get_status(project_dir: str) -> tuple:
    layout = ProjectLayout.open(project_dir)
    return layout.pipeline_state(), layout.config


def run_foundation(project_dir: str, force: bool = False) -> dict:
    layout, llm = _layout_and_llm(project_dir)
    graph = build_foundation_graph()
    final_state = graph.invoke({
        "layout": layout, "llm": llm, "feedback": "", "weak_layer": "world",
        "score": 0.0, "iterations": 0, "max_iterations": 8,
    })
    ps = layout.pipeline_state()
    ps.phase = "draft"
    ps.save(layout.pipeline_state_path)
    return {"foundation_score": final_state["score"]}


def run_foundation_single(project_dir: str, layer: str, force: bool = False) -> str:
    layout, llm = _layout_and_llm(project_dir)
    dispatch = {
        "world": F.gen_world, "characters": F.gen_characters,
        "outline": F.gen_outline, "canon": F.gen_canon, "voice": F.voice_fingerprint,
    }
    if layer not in dispatch:
        raise ValueError(f"Unknown foundation layer: {layer}")
    fn = dispatch[layer]
    return fn(layout, llm, force=force) if layer in ("canon", "voice") else fn(layout, llm, feedback="", force=force)


def run_draft(project_dir: str, from_chapter: int = 1, to_chapter: int | None = None) -> dict:
    layout, llm = _layout_and_llm(project_dir)
    last = to_chapter or layout.config.project.chapters_total
    graph = build_drafting_graph()
    final_state = graph.invoke({
        "layout": layout, "llm": llm, "current_chapter": from_chapter,
        "last_chapter": last, "retries": 0,
        "max_retries": layout.config.thresholds.max_draft_retries, "score": 0.0,
    }, config={"recursion_limit": 500})
    return {"last_chapter_reached": final_state["current_chapter"]}


def run_revision(project_dir: str, from_chapter: int = 1, to_chapter: int | None = None, cycles: int | None = None) -> None:
    layout, llm = _layout_and_llm(project_dir)
    last = to_chapter or layout.config.project.chapters_total
    max_cycles = cycles or layout.config.thresholds.revision_max_cycles
    graph = build_revision_graph()
    for chapter_index in range(from_chapter, last + 1):
        graph.invoke({
            "layout": layout, "llm": llm, "chapter_index": chapter_index, "cycle": 0,
            "max_cycles": max_cycles, "plateau_delta": layout.config.thresholds.revision_plateau_delta,
            "score": 0.0, "cuts": [], "reactions": [],
        }, config={"recursion_limit": 200})


def run_review(project_dir: str) -> None:
    layout, llm = _layout_and_llm(project_dir)
    cfg = layout.config
    target_chapters = list(range(1, cfg.project.chapters_total + 1))
    graph = build_review_graph()
    graph.invoke({
        "layout": layout, "llm": llm, "round": 0,
        "max_rounds": cfg.thresholds.review_max_rounds,
        "actionable_items": [], "target_chapters": target_chapters,
    }, config={"recursion_limit": 100})


def run_export(project_dir: str, formats: list[str] | None = None) -> dict:
    layout, _ = _layout_and_llm(project_dir)
    formats = formats or layout.config.export.formats
    results = {}
    if "pdf" in formats:
        build_tex(layout)
        pdf = typeset_pdf(layout)
        results["pdf"] = str(pdf) if pdf else "tex generated; no LaTeX engine found to compile PDF"
    if "epub" in formats:
        results["epub"] = str(build_epub(layout))
    return results


def run_full_pipeline(project_dir: str) -> None:
    run_foundation(project_dir)
    run_draft(project_dir)
    run_revision(project_dir)
    run_review(project_dir)
    run_export(project_dir)


def run_stage(stage: str, project_dir: str, from_chapter: int = 1, to_chapter: int | None = None,
              cycles: int | None = None, formats: list[str] | None = None, force: bool = False) -> None:
    if stage == "foundation":
        run_foundation(project_dir, force=force)
    elif stage.startswith("foundation."):
        run_foundation_single(project_dir, stage.split(".", 1)[1], force=force)
    elif stage == "draft":
        run_draft(project_dir, from_chapter, to_chapter)
    elif stage == "revision":
        run_revision(project_dir, from_chapter, to_chapter, cycles)
    elif stage == "review":
        run_review(project_dir)
    elif stage == "export":
        run_export(project_dir, formats)
    else:
        raise ValueError(f"Unknown stage: {stage}")
