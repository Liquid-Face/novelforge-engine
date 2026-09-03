"""Sequential per-layer foundation generation and evaluation graph."""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from novelforge.llm.provider import LLMProvider
from novelforge.observability.reporter import PipelineReporter
from novelforge.project import ProjectLayout
from novelforge.tools import foundation as T
from novelforge.observability.evaluation_logs import write_attempt_snapshot


LAYERS = ("world", "characters", "outline", "canon", "voice")
GENERATORS = {
    "world": T.gen_world,
    "characters": T.gen_characters,
    "outline": T.gen_outline,
    "canon": T.gen_canon,
    "voice": T.voice_fingerprint,
}
PATHS = {
    "world": "world_path",
    "characters": "characters_path",
    "outline": "outline_path",
    "canon": "canon_path",
    "voice": "voice_path",
}


class FoundationState(TypedDict):
    layout: ProjectLayout
    llm: LLMProvider
    reporter: PipelineReporter
    layer: str
    stop_layer: str | None
    force: bool
    feedback: str
    score: float
    best_score: float
    iterations: int
    max_iterations: int
    candidate: str
    candidate_path: str
    candidate_locked: bool
    generation_prompt: str
    generation_system_prompt: str
    generation_writer: dict


def _node_generate(state: FoundationState, layer: str) -> FoundationState:
    if state["layer"] != layer:
        state["layer"] = layer
        state["feedback"] = ""
        state["best_score"] = -1.0
        state["iterations"] = 0
        state["candidate_locked"] = False
        state["generation_prompt"] = ""
        state["generation_system_prompt"] = ""
        state["generation_writer"] = {}
    state["reporter"].node(f"gen_{layer}")
    layout = state["layout"]
    path = getattr(layout, PATHS[layer])
    manifest = layout.manifest()
    if manifest.is_human_edited(str(path.relative_to(layout.root)), layout.root) and not state["force"]:
        state["candidate"] = layout.read(path)
        state["candidate_locked"] = True
        state["candidate_path"] = str(path.relative_to(layout.root))
        state["reporter"].artifact(state["candidate_path"], "skipped (human-edited)")
    else:
        result = GENERATORS[layer](layout, state["llm"], feedback=state["feedback"], force=state["force"])
        state["candidate"] = result["content"]
        state["candidate_path"] = result["path"]
        state["candidate_locked"] = False
        state["generation_prompt"] = result.get("prompt", "")
        state["generation_system_prompt"] = result.get("system_prompt", "")
        state["generation_writer"] = result.get("writer", {})
    state["reporter"].token_usage(state["llm"])
    return state


def _write_evaluation_log(state: FoundationState, result: dict, accepted: bool) -> None:
    if not state["layout"].config.logging.log_evaluate:
        return
    layer = state["layer"]
    directory = state["layout"].logs_dir / "foundation" / layer
    iteration = state["iterations"]
    write_attempt_snapshot(
        directory,
        iteration,
        request=(f"System: {state['generation_system_prompt']}\n\n{state['generation_prompt']}"
                 if state["generation_prompt"] else None),
        content=state["candidate"],
        metadata={
            "layer": layer,
            "iteration": iteration,
            "score": state["score"],
            "threshold": state["layout"].config.thresholds.foundation_score,
            "accepted": accepted,
            "best_so_far": state["best_score"],
            "feedback": result.get("feedback", ""),
            "writer": state["generation_writer"],
        },
    )


def _node_evaluate(state: FoundationState, layer: str) -> FoundationState:
    state["reporter"].node(f"evaluate_{layer}")
    state["layer"] = layer
    state["iterations"] += 1
    if state["candidate_locked"]:
        result = {"layer_score": state["best_score"] if state["best_score"] >= 0 else 0.0, "feedback": "live artifact is human-edited"}
    else:
        result = T.evaluate_foundation_layer(layout=state["layout"], llm=state["llm"], layer=layer, content=state["candidate"])
    state["score"] = float(result.get("layer_score", 0.0))
    threshold = state["layout"].config.thresholds.foundation_score
    accepted = not state["candidate_locked"] and (state["best_score"] < 0 or state["score"] > state["best_score"])
    if accepted:
        written = state["layout"].write_guarded(state["layout"].root / state["candidate_path"], state["candidate"], force=state["force"])
        if written:
            state["best_score"] = state["score"]
            state["reporter"].artifact(state["candidate_path"], "created/updated")
        else:
            state["candidate_locked"] = True
            accepted = False
            state["reporter"].artifact(state["candidate_path"], "skipped (human-edited)")
    state["feedback"] = result.get("feedback", "")
    state["reporter"].cycle(f"Foundation {layer}", state["iterations"], state["max_iterations"])
    state["reporter"].score(f"{layer}_score", state["score"], threshold)
    state["reporter"].feedback(state["feedback"], state["layout"].config.logging.log_evaluate)
    _write_evaluation_log(state, result, accepted)
    state["reporter"].token_usage(state["llm"])

    ps = state["layout"].pipeline_state()
    ps.foundation_layer_scores[layer] = state["best_score"] if state["best_score"] >= 0 else state["score"]
    ps.foundation_score = min(ps.foundation_layer_scores.values()) if ps.foundation_layer_scores else state["score"]
    ps.save(state["layout"].pipeline_state_path)
    return state


def _make_generate(layer):
    return lambda state: _node_generate(state, layer)


def _make_evaluate(layer):
    return lambda state: _node_evaluate(state, layer)


def _route_after_evaluate(state: FoundationState) -> str:
    layer = state["layer"]
    threshold = state["layout"].config.thresholds.foundation_score
    next_layer = LAYERS[LAYERS.index(layer) + 1] if layer != LAYERS[-1] else END
    should_stop = state["score"] >= threshold or state["iterations"] >= state["max_iterations"] or state["candidate_locked"]
    if should_stop and state["stop_layer"] == layer:
        state["reporter"].router("after_evaluate", END, reason=f"single-layer run completed: {layer}")
        return END
    if should_stop:
        state["reporter"].router("after_evaluate", str(next_layer), reason=f"{layer} accepted/budget/locked")
        return next_layer
    state["reporter"].router("after_evaluate", layer, reason=f"{layer} rejected; retrying")
    return layer


def build_foundation_graph(start_layer: str = "world"):
    if start_layer not in LAYERS:
        raise ValueError(f"Unknown foundation layer: {start_layer}")
    graph = StateGraph(FoundationState)
    for layer in LAYERS:
        graph.add_node(layer, _make_generate(layer))
        graph.add_node(f"eval_{layer}", _make_evaluate(layer))
        graph.add_edge(layer, f"eval_{layer}")
    graph.set_entry_point(start_layer)
    destinations = {layer: layer for layer in LAYERS}
    destinations[END] = END
    for layer in LAYERS:
        graph.add_conditional_edges(f"eval_{layer}", _route_after_evaluate, destinations)
    return graph.compile()
