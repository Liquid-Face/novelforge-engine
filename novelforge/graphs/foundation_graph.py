"""
Foundation phase graph: generate world -> characters -> outline -> canon ->
voice -> evaluate, looping back to the weakest layer until foundation_score
exceeds threshold.
"""
from __future__ import annotations
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.tools import foundation as T


class FoundationState(TypedDict):
    layout: ProjectLayout
    llm: LLMProvider
    feedback: str
    weak_layer: str
    score: float
    iterations: int
    max_iterations: int


def _node_world(state: FoundationState) -> FoundationState:
    if state["iterations"] == 0 or state["weak_layer"] == "world":
        T.gen_world(state["layout"], state["llm"], feedback=state["feedback"])
    return state


def _node_characters(state: FoundationState) -> FoundationState:
    if state["iterations"] == 0 or state["weak_layer"] == "characters":
        T.gen_characters(state["layout"], state["llm"], feedback=state["feedback"])
    return state


def _node_outline(state: FoundationState) -> FoundationState:
    if state["iterations"] == 0 or state["weak_layer"] == "outline":
        T.gen_outline(state["layout"], state["llm"], feedback=state["feedback"])
    return state


def _node_canon(state: FoundationState) -> FoundationState:
    if state["iterations"] == 0 or state["weak_layer"] == "canon":
        T.gen_canon(state["layout"], state["llm"])
    return state


def _node_voice(state: FoundationState) -> FoundationState:
    if state["iterations"] == 0 or state["weak_layer"] == "voice":
        T.voice_fingerprint(state["layout"], state["llm"])
    return state


def _node_evaluate(state: FoundationState) -> FoundationState:
    result = T.evaluate_foundation(state["layout"], state["llm"])
    state["score"] = float(result.get("foundation_score", 0.0))
    state["weak_layer"] = result.get("weak_layer", "world")
    state["feedback"] = result.get("feedback", "")
    state["iterations"] += 1
    ps = state["layout"].pipeline_state()
    ps.foundation_score = state["score"]
    ps.save(state["layout"].pipeline_state_path)
    return state


def _route_after_evaluate(state: FoundationState) -> str:
    threshold = state["layout"].config.thresholds.foundation_score
    if state["score"] >= threshold or state["iterations"] >= state["max_iterations"]:
        return END
    return "world"


def build_foundation_graph():
    g = StateGraph(FoundationState)
    g.add_node("world", _node_world)
    g.add_node("characters", _node_characters)
    g.add_node("outline", _node_outline)
    g.add_node("canon", _node_canon)
    g.add_node("voice", _node_voice)
    g.add_node("evaluate", _node_evaluate)

    g.set_entry_point("world")
    g.add_edge("world", "characters")
    g.add_edge("characters", "outline")
    g.add_edge("outline", "canon")
    g.add_edge("canon", "voice")
    g.add_edge("voice", "evaluate")
    g.add_conditional_edges("evaluate", _route_after_evaluate, {"world": "world", END: END})
    return g.compile()
