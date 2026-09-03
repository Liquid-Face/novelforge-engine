from __future__ import annotations
from typing import TypedDict
from langgraph.graph import StateGraph, END
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.observability.reporter import PipelineReporter
from novelforge.tools import drafting as T
from novelforge.tools.rebuild import build_arc_summary
from novelforge.state.pipeline_state import ChapterRecord

class DraftState(TypedDict):
    layout: ProjectLayout
    llm: LLMProvider
    reporter: PipelineReporter
    current_chapter: int
    last_chapter: int
    retries: int
    max_retries: int
    score: float


def _node_draft(state: DraftState) -> DraftState:
    state["reporter"].node(f"draft_chapter(ch={state['current_chapter']})")
    T.draft_chapter(state["layout"], state["llm"], state["current_chapter"])
    state["reporter"].token_usage(state["llm"])
    return state


def _node_evaluate(state: DraftState) -> DraftState:
    state["reporter"].node(f"evaluate_chapter(ch={state['current_chapter']})")
    result = T.evaluate_chapter(state["layout"], state["llm"], state["current_chapter"])
    state["score"] = float(result.get("score", 0.0))
    threshold = state["layout"].config.thresholds.chapter_score
    state["reporter"].cycle(f"Chapter {state['current_chapter']} retry", state["retries"], state["max_retries"])
    state["reporter"].score(f"chapter_{state['current_chapter']}_score", state["score"], threshold)
    state["reporter"].token_usage(state["llm"])
    ps = state["layout"].pipeline_state()
    ps.chapters[state["current_chapter"]] = ChapterRecord(index=state["current_chapter"], status="evaluated", score=state["score"], retries=state["retries"])
    ps.save(state["layout"].pipeline_state_path)
    return state


def _node_arc_summary(state: DraftState) -> DraftState:
    state["reporter"].node("build_arc_summary")
    build_arc_summary(state["layout"], state["llm"])
    state["reporter"].token_usage(state["llm"])
    state["current_chapter"] += 1
    state["retries"] = 0
    return state


def _route_after_evaluate(state: DraftState) -> str:
    threshold = state["layout"].config.thresholds.chapter_score
    kept = state["score"] >= threshold or state["retries"] >= state["max_retries"]
    if not kept:
        state["retries"] += 1
        state["reporter"].router("after_evaluate", "retry", reason=f"score {state['score']:.2f} < threshold {threshold:.2f}")
        return "retry"
    if state["current_chapter"] >= state["last_chapter"]:
        state["reporter"].router("after_evaluate", "done", reason="last chapter reached")
        return "done"
    state["reporter"].router("after_evaluate", "advance", reason=f"score {state['score']:.2f} accepted")
    return "advance"


def build_drafting_graph():
    g = StateGraph(DraftState)
    g.add_node("draft", _node_draft)
    g.add_node("evaluate", _node_evaluate)
    g.add_node("arc_summary", _node_arc_summary)
    g.set_entry_point("draft")
    g.add_edge("draft", "evaluate")
    g.add_conditional_edges("evaluate", _route_after_evaluate, {"retry": "draft", "advance": "arc_summary", "done": END})
    g.add_edge("arc_summary", "draft")
    return g.compile()
