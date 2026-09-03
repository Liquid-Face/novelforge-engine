from __future__ import annotations
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.observability.reporter import PipelineReporter, build_reporter_from_config
from novelforge.graphs.foundation_graph import build_foundation_graph
from novelforge.graphs.drafting_graph import build_drafting_graph
from novelforge.graphs.revision_graph import build_revision_graph
from novelforge.graphs.review_graph import build_review_graph
from novelforge.tools import foundation as F
from novelforge.tools.export import build_tex, typeset_pdf, build_epub


def _make_reporter(layout: ProjectLayout, verbosity_override: str | None = None) -> PipelineReporter:
    logging_config = layout.config.logging
    if verbosity_override:
        logging_config = logging_config.model_copy(update={"console_verbosity": verbosity_override})
    return build_reporter_from_config(logging_config, layout.root)


def _layout_llm_reporter(project_dir: str, verbosity_override: str | None = None) -> tuple[ProjectLayout, LLMProvider, PipelineReporter]:
    layout = ProjectLayout.open(project_dir)
    layout.ensure_dirs()
    reporter = _make_reporter(layout, verbosity_override)
    llm = LLMProvider(layout.config.llm, reporter=reporter)
    return layout, llm, reporter


def _persist_run_tokens(layout: ProjectLayout, llm: LLMProvider, reporter: PipelineReporter) -> None:
    project_tokens = layout.project_token_usage()
    project_tokens.merge_run(llm.usage_totals.prompt_tokens, llm.usage_totals.completion_tokens)
    project_tokens.save(layout.token_usage_path)
    reporter.project_token_usage(project_tokens)


def _role_params_table(layout: ProjectLayout) -> dict:
    rows = {}
    for role, role_cfg in layout.config.llm.roles.items():
        rows[f"llm.{role}.primary"] = f"{role_cfg.primary.provider} / {role_cfg.primary.model}"
        rows[f"llm.{role}.fallback"] = f"{role_cfg.fallback.provider} / {role_cfg.fallback.model}" if role_cfg.fallback else "none"
    return rows


def _run_params(layout: ProjectLayout) -> dict:
    cfg = layout.config
    params = {
        "project.title": cfg.project.title,
        "project.genre": cfg.project.genre,
        "project.chapters_total": cfg.project.chapters_total,
        "project.chapter_length_words": cfg.project.chapter_length_words,
        "thresholds.foundation_score": cfg.thresholds.foundation_score,
        "thresholds.foundation_max_iterations": cfg.thresholds.foundation_max_iterations,
        "thresholds.chapter_score": cfg.thresholds.chapter_score,
        "thresholds.revision_max_cycles": cfg.thresholds.revision_max_cycles,
        "thresholds.revision_plateau_delta": cfg.thresholds.revision_plateau_delta,
        "thresholds.review_max_rounds": cfg.thresholds.review_max_rounds,
        "logging.console_verbosity": cfg.logging.console_verbosity,
        "logging.log_to_file": cfg.logging.log_to_file,
        "logging.log_file_path": cfg.logging.log_file_path if cfg.logging.log_to_file else "n/a",
        "logging.log_evaluate": cfg.logging.log_evaluate,
        "logging.show_token_counts": cfg.logging.show_token_counts,
    }
    params.update(_role_params_table(layout))
    return params


def _stream_graph(graph, initial_state: dict, reporter: PipelineReporter, recursion_limit: int = 200) -> dict:
    final_state = dict(initial_state)
    for step in graph.stream(initial_state, config={"recursion_limit": recursion_limit}, stream_mode="values"):
        final_state = step
        last_node = list(step.keys())[-1] if isinstance(step, dict) else "?"
        reporter.stream_state(last_node, step if isinstance(step, dict) else {})
    return final_state


def get_status(project_dir: str) -> tuple:
    layout = ProjectLayout.open(project_dir)
    return layout.pipeline_state(), layout.config


def run_foundation(project_dir: str, force: bool = False, verbosity_override: str | None = None) -> dict:
    layout, llm, reporter = _layout_llm_reporter(project_dir, verbosity_override)
    ps = layout.pipeline_state()
    ps.foundation_layer_scores = {}
    ps.foundation_score = None
    ps.save(layout.pipeline_state_path)
    reporter.run_banner("stage: foundation", project_dir, _run_params(layout), layout.project_token_usage())
    reporter.stage_start("foundation", graph_name="foundation_graph")
    graph = build_foundation_graph()
    initial = {"layout": layout, "llm": llm, "reporter": reporter, "layer": "world", "stop_layer": None, "force": force, "feedback": "", "score": 0.0, "best_score": -1.0, "iterations": 0, "max_iterations": layout.config.thresholds.foundation_max_iterations, "candidate": "", "candidate_path": "", "candidate_locked": False, "generation_prompt": "", "generation_system_prompt": "", "generation_writer": {}}
    final_state = _stream_graph(graph, initial, reporter, recursion_limit=200)
    ps = layout.pipeline_state()
    ps.phase = "draft"
    ps.save(layout.pipeline_state_path)
    reporter.stage_end("foundation", llm=llm)
    _persist_run_tokens(layout, llm, reporter)
    return {"foundation_score": layout.pipeline_state().foundation_score, "foundation_layer_scores": layout.pipeline_state().foundation_layer_scores}


def run_foundation_single(project_dir: str, layer: str, force: bool = False, verbosity_override: str | None = None) -> str:
    layout, llm, reporter = _layout_llm_reporter(project_dir, verbosity_override)
    reporter.run_banner(f"stage: foundation.{layer}", project_dir, _run_params(layout), layout.project_token_usage())
    reporter.stage_start(f"foundation.{layer}", graph_name="foundation_graph")
    graph = build_foundation_graph(start_layer=layer)
    initial = {"layout": layout, "llm": llm, "reporter": reporter, "layer": layer, "stop_layer": layer, "force": force, "feedback": "", "score": 0.0, "best_score": -1.0, "iterations": 0, "max_iterations": layout.config.thresholds.foundation_max_iterations, "candidate": "", "candidate_path": "", "candidate_locked": False, "generation_prompt": "", "generation_system_prompt": "", "generation_writer": {}}
    final_state = _stream_graph(graph, initial, reporter, recursion_limit=200)
    reporter.stage_end(f"foundation.{layer}", llm=llm)
    _persist_run_tokens(layout, llm, reporter)
    return final_state.get("candidate", "")


def run_draft(project_dir: str, from_chapter: int = 1, to_chapter: int | None = None, verbosity_override: str | None = None) -> dict:
    layout, llm, reporter = _layout_llm_reporter(project_dir, verbosity_override)
    reporter.run_banner("stage: draft", project_dir, _run_params(layout), layout.project_token_usage())
    reporter.stage_start("draft", graph_name="drafting_graph")
    last = to_chapter or layout.config.project.chapters_total
    graph = build_drafting_graph()
    initial = {"layout": layout, "llm": llm, "reporter": reporter, "current_chapter": from_chapter, "last_chapter": last, "retries": 0, "max_retries": layout.config.thresholds.max_draft_retries, "score": 0.0, "best_score": -1.0, "best_text": "", "best_iteration": -1, "draft_result": {}}
    final_state = _stream_graph(graph, initial, reporter, recursion_limit=500)
    reporter.stage_end("draft", llm=llm)
    _persist_run_tokens(layout, llm, reporter)
    return {"last_chapter_reached": final_state.get("current_chapter", from_chapter)}


def run_revision(project_dir: str, from_chapter: int = 1, to_chapter: int | None = None, cycles: int | None = None, verbosity_override: str | None = None) -> None:
    layout, llm, reporter = _layout_llm_reporter(project_dir, verbosity_override)
    reporter.run_banner("stage: revision", project_dir, _run_params(layout), layout.project_token_usage())
    reporter.stage_start("revision", graph_name="revision_graph")
    last = to_chapter or layout.config.project.chapters_total
    max_cycles = cycles or layout.config.thresholds.revision_max_cycles
    graph = build_revision_graph()
    for chapter_index in range(from_chapter, last + 1):
        initial = {"layout": layout, "llm": llm, "reporter": reporter, "chapter_index": chapter_index, "cycle": 0, "max_cycles": max_cycles, "plateau_delta": layout.config.thresholds.revision_plateau_delta, "score": 0.0, "cuts": [], "reactions": []}
        _stream_graph(graph, initial, reporter, recursion_limit=200)
    reporter.stage_end("revision", llm=llm)
    _persist_run_tokens(layout, llm, reporter)


def run_review(project_dir: str, verbosity_override: str | None = None) -> None:
    layout, llm, reporter = _layout_llm_reporter(project_dir, verbosity_override)
    reporter.run_banner("stage: review", project_dir, _run_params(layout), layout.project_token_usage())
    reporter.stage_start("review", graph_name="review_graph")
    cfg = layout.config
    target_chapters = list(range(1, cfg.project.chapters_total + 1))
    graph = build_review_graph()
    initial = {"layout": layout, "llm": llm, "reporter": reporter, "round": 0, "max_rounds": cfg.thresholds.review_max_rounds, "actionable_items": [], "target_chapters": target_chapters}
    _stream_graph(graph, initial, reporter, recursion_limit=100)
    reporter.stage_end("review", llm=llm)
    _persist_run_tokens(layout, llm, reporter)


def run_export(project_dir: str, formats: list[str] | None = None, verbosity_override: str | None = None) -> dict:
    layout, llm, reporter = _layout_llm_reporter(project_dir, verbosity_override)
    reporter.run_banner("stage: export", project_dir, _run_params(layout), layout.project_token_usage())
    reporter.stage_start("export", graph_name="direct-call")
    formats = formats or layout.config.export.formats
    results = {}
    if "pdf" in formats:
        reporter.node("build_tex")
        tex = build_tex(layout)
        reporter.artifact(str(tex.relative_to(layout.root)), "created/updated")
        reporter.node("typeset_pdf")
        pdf = typeset_pdf(layout)
        results["pdf"] = str(pdf) if pdf else "tex generated; no LaTeX engine found to compile PDF"
    if "epub" in formats:
        reporter.node("build_epub")
        epub = build_epub(layout)
        reporter.artifact(str(epub.relative_to(layout.root)), "created/updated")
        results["epub"] = str(epub)
    reporter.stage_end("export", llm=llm)
    _persist_run_tokens(layout, llm, reporter)
    return results


def run_full_pipeline(project_dir: str, verbosity_override: str | None = None) -> None:
    layout = ProjectLayout.open(project_dir)
    reporter = _make_reporter(layout, verbosity_override)
    reporter.run_banner("full pipeline", project_dir, _run_params(layout), layout.project_token_usage())
    run_foundation(project_dir, verbosity_override=verbosity_override)
    run_draft(project_dir, verbosity_override=verbosity_override)
    run_revision(project_dir, verbosity_override=verbosity_override)
    run_review(project_dir, verbosity_override=verbosity_override)
    run_export(project_dir, verbosity_override=verbosity_override)


def run_stage(stage: str, project_dir: str, from_chapter: int = 1, to_chapter: int | None = None,
              cycles: int | None = None, formats: list[str] | None = None, force: bool = False,
              verbosity_override: str | None = None) -> None:
    if stage == "foundation":
        run_foundation(project_dir, force=force, verbosity_override=verbosity_override)
    elif stage.startswith("foundation."):
        run_foundation_single(project_dir, stage.split(".", 1)[1], force=force, verbosity_override=verbosity_override)
    elif stage == "draft":
        run_draft(project_dir, from_chapter, to_chapter, verbosity_override=verbosity_override)
    elif stage == "revision":
        run_revision(project_dir, from_chapter, to_chapter, cycles, verbosity_override=verbosity_override)
    elif stage == "review":
        run_review(project_dir, verbosity_override=verbosity_override)
    elif stage == "export":
        run_export(project_dir, formats, verbosity_override=verbosity_override)
    else:
        raise ValueError(f"Unknown stage: {stage}")
