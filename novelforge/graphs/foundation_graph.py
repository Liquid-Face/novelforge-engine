"""
Foundation-loop graph: world -> characters -> outline -> canon -> voice ->
evaluate, looping back to regenerate only the weakest layer until the
foundation score clears the configured threshold (or iterations run out).
"""
from __future__ import annotations
from typing import TypedDict
from langgraph.graph import StateGraph, END
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.observability.reporter import PipelineReporter
from novelforge.tools import foundation as T


class FoundationState(TypedDict):
    layout: ProjectLayout
    llm: LLMProvider
    reporter: PipelineReporter
    feedback: str
    weak_layer: str
    score: float
    iterations: int
    max_iterations: int


def _report_artifact(reporter: PipelineReporter, result: dict) -> None:
    reporter.artifact(result["path"], "created/updated" if result["written"] else "skipped (human-edited)")


def _should_regenerate(state: FoundationState, layer: str) -> bool:
    return state["iterations"] == 0 or state["weak_layer"] == layer


def _node_world(state: FoundationState) -> FoundationState:
    state["reporter"].node("gen_world")
    if _should_regenerate(state, "world"):
        result = T.gen_world(state["layout"], state["llm"], feedback=state["feedback"])
        _report_artifact(state["reporter"], result)
    state["reporter"].token_usage(state["llm"])
    return state


def _node_characters(state: FoundationState) -> FoundationState:
    state["reporter"].node("gen_characters")
    if _should_regenerate(state, "characters"):
        result = T.gen_characters(state["layout"], state["llm"], feedback=state["feedback"])
        _report_artifact(state["reporter"], result)
    state["reporter"].token_usage(state["llm"])
    return state


def _node_outline(state: FoundationState) -> FoundationState:
    state["reporter"].node("gen_outline")
    if _should_regenerate(state, "outline"):
        result = T.gen_outline(state["layout"], state["llm"], feedback=state["feedback"])
        _report_artifact(state["reporter"], result)
    state["reporter"].token_usage(state["llm"])
    return state


def _node_canon(state: FoundationState) -> FoundationState:
    state["reporter"].node("gen_canon")
    if _should_regenerate(state, "canon"):
        result = T.gen_canon(state["layout"], state["llm"], feedback=state["feedback"])
        _report_artifact(state["reporter"], result)
    state["reporter"].token_usage(state["llm"])
    return state


def _node_voice(state: FoundationState) -> FoundationState:
    state["reporter"].node("voice_fingerprint")
    if _should_regenerate(state, "voice"):
        result = T.voice_fingerprint(state["layout"], state["llm"], feedback=state["feedback"])
        _report_artifact(state["reporter"], result)
    state["reporter"].token_usage(state["llm"])
    return state


def _node_evaluate(state: FoundationState) -> FoundationState:
    state["reporter"].node("evaluate_foundation")
    result = T.evaluate_foundation(state["layout"], state["llm"])
    state["score"] = float(result.get("foundation_score", 0.0))
    state["weak_layer"] = result.get("weak_layer", "world")
    state["feedback"] = result.get("feedback", "")
    state["iterations"] += 1

    threshold = state["layout"].config.thresholds.foundation_score
    state["reporter"].cycle("Foundation iteration", state["iterations"], state["max_iterations"])
    state["reporter"].score("foundation_score", state["score"], threshold)
    state["reporter"].token_usage(state["llm"])

    ps = state["layout"].pipeline_state()
    ps.foundation_score = state["score"]
    ps.save(state["layout"].pipeline_state_path)
    return state


def _route_after_evaluate(state: FoundationState) -> str:
    threshold = state["layout"].config.thresholds.foundation_score
    if state["score"] >= threshold:
        state["reporter"].router("after_evaluate", "END", reason=f"score {state['score']:.2f} >= threshold {threshold:.2f}")
        return END
    if state["iterations"] >= state["max_iterations"]:
        state["reporter"].router("after_evaluate", "END", reason=f"max_iterations {state['max_iterations']} reached")
        return END
    state["reporter"].router("after_evaluate", "world", reason=f"weakest layer: {state['weak_layer']}")
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
