"""
Drafting phase graph: sequential chapter loop, draft -> evaluate -> keep/retry.
On keep, arc_summary is rebuilt before moving to the next chapter so the next
draft has up-to-date prior-events context.
"""
from __future__ import annotations
from typing import TypedDict
from langgraph.graph import StateGraph, END
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.tools import drafting as T
from novelforge.tools.rebuild import build_arc_summary
from novelforge.state.pipeline_state import ChapterRecord


class DraftState(TypedDict):
    layout: ProjectLayout
    llm: LLMProvider
    current_chapter: int
    last_chapter: int
    retries: int
    max_retries: int
    score: float


def _node_draft(state: DraftState) -> DraftState:
    T.draft_chapter(state["layout"], state["llm"], state["current_chapter"])
    return state


def _node_evaluate(state: DraftState) -> DraftState:
    result = T.evaluate_chapter(state["layout"], state["llm"], state["current_chapter"])
    state["score"] = float(result.get("score", 0.0))
    ps = state["layout"].pipeline_state()
    ps.chapters[state["current_chapter"]] = ChapterRecord(
        index=state["current_chapter"],
        status="evaluated",
        score=state["score"],
        retries=state["retries"],
    )
    ps.save(state["layout"].pipeline_state_path)
    return state


def _node_arc_summary(state: DraftState) -> DraftState:
    build_arc_summary(state["layout"], state["llm"])
    state["current_chapter"] += 1
    state["retries"] = 0
    return state


def _route_after_evaluate(state: DraftState) -> str:
    threshold = state["layout"].config.thresholds.chapter_score
    kept = state["score"] >= threshold or state["retries"] >= state["max_retries"]
    if not kept:
        state["retries"] += 1
        return "retry"
    if state["current_chapter"] >= state["last_chapter"]:
        return "done"
    return "advance"


def build_drafting_graph():
    g = StateGraph(DraftState)
    g.add_node("draft", _node_draft)
    g.add_node("evaluate", _node_evaluate)
    g.add_node("arc_summary", _node_arc_summary)

    g.set_entry_point("draft")
    g.add_edge("draft", "evaluate")
    g.add_conditional_edges(
        "evaluate", _route_after_evaluate,
        {"retry": "draft", "advance": "arc_summary", "done": END},
    )
    g.add_edge("arc_summary", "draft")
    return g.compile()
