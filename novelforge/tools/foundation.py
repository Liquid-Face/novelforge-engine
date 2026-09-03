"""
Foundation-layer tools: build world, characters, outline, canon and voice
from a seed concept, then evaluate each layer independently.

Each tool renders its own Jinja2 template (see novelforge/prompts/templates)
with the exact context that template needs. Templates own the wording;
this module owns only which pieces of already-generated lore are fed into
which template -- it never hardcodes prompt text itself.
"""
from __future__ import annotations
import json
from pathlib import Path
from novelforge.prompts.renderer import render


def _artifact(layout, path: Path, content: str, prompt: str, result) -> dict:
    return {"content": content, "path": str(path.relative_to(layout.root)), "prompt": prompt,
            "system_prompt": "sys", "writer": {"provider": result.provider, "model": result.model,
            "fallback": getattr(result, "fallback", False)}}


def gen_world(layout, llm, feedback: str = "", force: bool = False) -> dict:
    prompt = render(
        "gen_world",
        genre=layout.config.project.genre,
        language=layout.config.project.language,
        seed=layout.read(layout.seed_path),
        feedback=feedback,
    )
    result = llm.complete(system_prompt="sys", user_prompt=prompt, role="writer")
    return _artifact(layout, layout.world_path, result.text, prompt, result)


def gen_characters(layout, llm, feedback: str = "", force: bool = False) -> dict:
    prompt = render(
        "gen_characters",
        genre=layout.config.project.genre,
        language=layout.config.project.language,
        seed=layout.read(layout.seed_path),
        world=layout.read(layout.world_path),
        feedback=feedback,
    )
    result = llm.complete(system_prompt="sys", user_prompt=prompt, role="writer")
    return _artifact(layout, layout.characters_path, result.text, prompt, result)


def gen_outline(layout, llm, feedback: str = "", force: bool = False) -> dict:
    prompt = render(
        "gen_outline",
        genre=layout.config.project.genre,
        language=layout.config.project.language,
        chapters_total=layout.config.project.chapters_total,
        seed=layout.read(layout.seed_path),
        world=layout.read(layout.world_path),
        characters=layout.read(layout.characters_path),
        feedback=feedback,
    )
    result = llm.complete(system_prompt="sys", user_prompt=prompt, role="writer")
    return _artifact(layout, layout.outline_path, result.text, prompt, result)


def gen_canon(layout, llm, feedback: str = "", force: bool = False) -> dict:
    prompt = render(
        "gen_canon",
        language=layout.config.project.language,
        world=layout.read(layout.world_path),
        characters=layout.read(layout.characters_path),
        outline=layout.read(layout.outline_path),
        feedback=feedback,
    )
    result = llm.complete(system_prompt="sys", user_prompt=prompt, role="evaluator")
    return _artifact(layout, layout.canon_path, result.text, prompt, result)


def voice_fingerprint(layout, llm, feedback: str = "", force: bool = False) -> dict:
    prompt = render(
        "voice_fingerprint",
        genre=layout.config.project.genre,
        language=layout.config.project.language,
        seed=layout.read(layout.seed_path),
        world=layout.read(layout.world_path),
        feedback=feedback,
    )
    result = llm.complete(system_prompt="sys", user_prompt=prompt, role="writer")
    return _artifact(layout, layout.voice_path, result.text, prompt, result)


def evaluate_foundation_layer(layout, llm, layer: str, content: str) -> dict:
    prompt = render(
        "evaluate_foundation_layer",
        layer=layer,
        content=content,
        language=layout.config.project.language,
        genre=layout.config.project.genre,
        target_audience=layout.config.project.target_audience,
        chapters_total=layout.config.project.chapters_total,
    )
    result = llm.complete(system_prompt="sys", user_prompt=prompt, role="evaluator")
    try:
        cleaned = result.text.strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = cleaned[3:-3].strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"layer_score": 0.0, "feedback": result.text}
