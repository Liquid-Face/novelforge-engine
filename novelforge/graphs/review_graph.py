"""
Phase 3b: dual-persona full-manuscript review loop. Stops when actionable
items are exhausted (<= review_stop_max_items) or max_rounds reached.
"""
from __future__ import annotations
from typing import TypedDict
from langgraph.graph import StateGraph, END
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.tools.review import review_manuscript
from novelforge.tools.revision import gen_brief, gen_revision


class ReviewState(TypedDict):
    layout: ProjectLayout
    llm: LLMProvider
    round: int
    max_rounds: int
    actionable_items: list
    target_chapters: list[int]


def _node_review(state: ReviewState) -> ReviewState:
    result = review_manuscript(state["layout"], state["llm"])
    state["actionable_items"] = result.get("actionable_items", [])
    ps = state["layout"].pipeline_state()
    ps.review_round = state["round"] + 1
    ps.save(state["layout"].pipeline_state_path)
    return state


def _node_fix_items(state: ReviewState) -> ReviewState:
    bundle = "\n".join(f"- {item}" for item in state["actionable_items"])
    for ch in state["target_chapters"]:
        gen_brief(state["layout"], state["llm"], ch, bundle, force=False)
        gen_revision(state["layout"], state["llm"], ch)
    state["round"] += 1
    return state


def _route_after_review(state: ReviewState) -> str:
    threshold = state["layout"].config.thresholds.review_stop_max_items
    if len(state["actionable_items"]) <= threshold or state["round"] >= state["max_rounds"]:
        return END
    return "fix_items"


def build_review_graph():
    g = StateGraph(ReviewState)
    g.add_node("review", _node_review)
    g.add_node("fix_items", _node_fix_items)

    g.set_entry_point("review")
    g.add_conditional_edges("review", _route_after_review, {"fix_items": "fix_items", END: END})
    g.add_edge("fix_items", "review")
    return g.compile()
