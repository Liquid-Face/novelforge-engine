"""
Revision phase graph (per chapter, run across all chapters by the CLI layer):
adversarial_edit -> apply_cuts -> reader_panel -> gen_brief -> gen_revision ->
evaluate, with plateau detection stopping the outer cycle loop.
"""
from __future__ import annotations
import json
from typing import TypedDict
from langgraph.graph import StateGraph, END
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.tools import revision as R
from novelforge.tools.drafting import evaluate_chapter


class RevisionState(TypedDict):
    layout: ProjectLayout
    llm: LLMProvider
    chapter_index: int
    cycle: int
    max_cycles: int
    plateau_delta: float
    score: float
    cuts: list
    reactions: list


def _node_adversarial(state: RevisionState) -> RevisionState:
    state["cuts"] = R.adversarial_edit(state["layout"], state["llm"], state["chapter_index"])
    return state


def _node_apply_cuts(state: RevisionState) -> RevisionState:
    R.apply_cuts(state["layout"], state["chapter_index"], state["cuts"])
    return state


def _node_reader_panel(state: RevisionState) -> RevisionState:
    state["reactions"] = R.reader_panel(state["layout"], state["llm"], state["chapter_index"])
    return state


def _node_brief(state: RevisionState) -> RevisionState:
    bundle = json.dumps({"cuts": state["cuts"], "reader_panel": state["reactions"]}, ensure_ascii=False)
    R.gen_brief(state["layout"], state["llm"], state["chapter_index"], bundle)
    return state


def _node_revise(state: RevisionState) -> RevisionState:
    R.gen_revision(state["layout"], state["llm"], state["chapter_index"])
    return state


def _node_evaluate(state: RevisionState) -> RevisionState:
    result = evaluate_chapter(state["layout"], state["llm"], state["chapter_index"])
    state["score"] = float(result.get("score", 0.0))
    ps = state["layout"].pipeline_state()
    ps.revision_score_history.append(state["score"])
    ps.revision_cycle = state["cycle"] + 1
    ps.save(state["layout"].pipeline_state_path)
    state["cycle"] += 1
    return state


def _route_after_evaluate(state: RevisionState) -> str:
    ps = state["layout"].pipeline_state()
    if state["cycle"] >= state["max_cycles"] or ps.plateaued(state["plateau_delta"]):
        return END
    return "adversarial"


def build_revision_graph():
    g = StateGraph(RevisionState)
    g.add_node("adversarial", _node_adversarial)
    g.add_node("apply_cuts", _node_apply_cuts)
    g.add_node("reader_panel", _node_reader_panel)
    g.add_node("brief", _node_brief)
    g.add_node("revise", _node_revise)
    g.add_node("evaluate", _node_evaluate)

    g.set_entry_point("adversarial")
    g.add_edge("adversarial", "apply_cuts")
    g.add_edge("apply_cuts", "reader_panel")
    g.add_edge("reader_panel", "brief")
    g.add_edge("brief", "revise")
    g.add_edge("revise", "evaluate")
    g.add_conditional_edges("evaluate", _route_after_evaluate, {"adversarial": "adversarial", END: END})
    return g.compile()
