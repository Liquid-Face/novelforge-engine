"""
Foundation-layer tools: build world, characters, outline, canon and voice
from a seed concept, then evaluate the whole foundation.

Each tool renders its own Jinja2 template (see novelforge/prompts/templates)
with the exact context that template needs. Templates own the wording;
this module owns only which pieces of already-generated lore are fed into
which template -- it never hardcodes prompt text itself.
"""
from __future__ import annotations
import json
from pathlib import Path
from novelforge.prompts.renderer import render


def _write_artifact(layout, path: Path, content: str, force: bool) -> dict:
    written = layout.write_guarded(path, content, force=force)
    return {"content": content, "path": str(path.relative_to(layout.root)), "written": written}


def gen_world(layout, llm, feedback: str = "", force: bool = False) -> dict:
    prompt = render(
        "gen_world",
        genre=layout.config.project.genre,
        language=layout.config.project.language,
        seed=layout.read(layout.seed_path),
        feedback=feedback,
    )
    result = llm.complete(system_prompt="sys", user_prompt=prompt, role="writer")
    return _write_artifact(layout, layout.world_path, result.text, force)


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
    return _write_artifact(layout, layout.characters_path, result.text, force)


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
    return _write_artifact(layout, layout.outline_path, result.text, force)


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
    return _write_artifact(layout, layout.canon_path, result.text, force)


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
    return _write_artifact(layout, layout.voice_path, result.text, force)


def evaluate_foundation(layout, llm) -> dict:
    prompt = render(
        "evaluate_foundation",
        language=layout.config.project.language,
        world=layout.read(layout.world_path),
        characters=layout.read(layout.characters_path),
        outline=layout.read(layout.outline_path),
        canon=layout.read(layout.canon_path),
        voice=layout.read(layout.voice_path),
    )
    result = llm.complete(system_prompt="sys", user_prompt=prompt, role="evaluator")
    try:
        return json.loads(result.text)
    except json.JSONDecodeError:
        return {"foundation_score": 0.0, "weak_layer": "world", "feedback": result.text}
