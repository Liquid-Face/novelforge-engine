"""
Foundation-phase tools: world, characters, outline, canon, voice, and the
foundation evaluator. Each function is pure with respect to its inputs
(project layout + llm provider) -- no hidden global state, no novel-specific
text embedded here (all such text lives in prompts/templates/*.jinja2).
"""
from __future__ import annotations
import json
from novelforge.project import ProjectLayout
from novelforge.llm.provider import LLMProvider
from novelforge.prompts.renderer import render


def gen_world(layout: ProjectLayout, llm: LLMProvider, feedback: str = "", force: bool = False) -> str:
    seed = layout.read(layout.seed_path)
    existing = layout.read(layout.world_path)
    prompt = render(
        "gen_world",
        genre=layout.config.project.genre,
        language=layout.config.project.language,
        target_audience=layout.config.project.target_audience,
        seed=seed,
        existing_world=existing,
        feedback=feedback,
    )
    result = llm.complete(system_prompt="You are a fiction world-building co-author.", user_prompt=prompt, role="writer")
    layout.write_guarded(layout.world_path, result.text, force=force)
    return result.text


def gen_characters(layout: ProjectLayout, llm: LLMProvider, feedback: str = "", force: bool = False) -> str:
    prompt = render(
        "gen_characters",
        genre=layout.config.project.genre,
        language=layout.config.project.language,
        world=layout.read(layout.world_path),
        seed=layout.read(layout.seed_path),
        feedback=feedback,
    )
    result = llm.complete(system_prompt="You are a fiction character designer.", user_prompt=prompt, role="writer")
    layout.write_guarded(layout.characters_path, result.text, force=force)
    return result.text


def gen_outline(layout: ProjectLayout, llm: LLMProvider, feedback: str = "", force: bool = False) -> str:
    cfg = layout.config.project
    prompt = render(
        "gen_outline",
        genre=cfg.genre,
        language=cfg.language,
        chapters_total=cfg.chapters_total,
        chapter_length_min=cfg.chapter_length_words[0],
        chapter_length_max=cfg.chapter_length_words[1],
        world=layout.read(layout.world_path),
        characters=layout.read(layout.characters_path),
        feedback=feedback,
    )
    result = llm.complete(system_prompt="You are a narrative structure specialist.", user_prompt=prompt, role="writer")
    layout.write_guarded(layout.outline_path, result.text, force=force)
    return result.text


def gen_canon(layout: ProjectLayout, llm: LLMProvider, force: bool = False) -> str:
    prompt = render(
        "gen_canon",
        world=layout.read(layout.world_path),
        characters=layout.read(layout.characters_path),
        outline=layout.read(layout.outline_path),
        language=layout.config.project.language,
    )
    result = llm.complete(system_prompt="You are a continuity editor.", user_prompt=prompt, role="evaluator")
    layout.write_guarded(layout.canon_path, result.text, force=force)
    return result.text


def voice_fingerprint(layout: ProjectLayout, llm: LLMProvider, force: bool = False) -> str:
    prompt = render(
        "voice_fingerprint",
        genre=layout.config.project.genre,
        language=layout.config.project.language,
        world=layout.read(layout.world_path),
    )
    result = llm.complete(system_prompt="You are a literary voice consultant.", user_prompt=prompt, role="writer")
    layout.write_guarded(layout.voice_path, result.text, force=force)
    return result.text


def evaluate_foundation(layout: ProjectLayout, llm: LLMProvider) -> dict:
    prompt = render(
        "evaluate_foundation",
        world=layout.read(layout.world_path),
        characters=layout.read(layout.characters_path),
        outline=layout.read(layout.outline_path),
        canon=layout.read(layout.canon_path),
        voice=layout.read(layout.voice_path),
    )
    result = llm.complete(system_prompt="You are a strict fiction editor.", user_prompt=prompt, role="evaluator")
    try:
        return json.loads(result.text)
    except json.JSONDecodeError:
        return {"foundation_score": 0.0, "weak_layer": "world", "feedback": result.text}
