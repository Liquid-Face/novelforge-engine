# NovelForge Engine

Provider-agnostic, text-only autonomous novel-writing pipeline engine, built
on LangGraph. Inspired by NousResearch/autonovel, with image/audio generation
removed and all vendor lock-in (Anthropic-only) eliminated in favor of an
OpenAI-compatible LLM layer that works with both local Ollama and the
AITUNNEL API aggregator.

## Design principles

- **Engine/data separation.** This repository contains only code, prompt
  templates, and LangGraph graphs. Every novel lives in its own project
  directory, created via `novelforge init --project-dir <path>` from
  `templates/project/`. The engine never writes into its own repo.
- **Provider-agnostic LLM access.** `novelforge/llm/provider.py` talks to any
  OpenAI-compatible Chat Completions endpoint. Swapping Ollama <-> AITUNNEL
  <-> any other compatible API is a `project.yaml` edit, not a code change.
- **No prompts hardcoded in scripts.** All prompt text lives under
  `novelforge/prompts/templates/*.jinja2`, rendered with lore/config
  variables at call time.
- **Manual-edit protection.** `novelforge/state/manifest.py` hashes every
  generated artifact; re-running a stage never silently overwrites a file a
  human has hand-edited (`--force-regenerate` opts back in).
- **Stage-level resumability.** Every phase is a LangGraph `StateGraph`; the
  CLI can run the full pipeline or any single stage/sub-stage.
- **UI-ready.** `novelforge/api.py` is the single orchestration entry point
  used by the CLI (`novelforge/cli.py`); a future web/GUI can import the same
  functions directly.

## Install

```bash
pip install -e .
```

ИЛИ

Установить как глобальный инструмент через uv
```bash
cd ~/AI/novelforge-engine
uv tool install -e .
```

Ключевое отличие от "uv pip install -e .": uv tool install не кладёт пакет в venv конкретного проекта, а создаёт отдельное изолированное окружение специально для инструмента и линкует его исполняемый файл в ~/.local/bin/novelforge (или ~/.cargo/bin в зависимости от настроек uv), который автоматически попадает в PATH. Далее в терминала novelforge работает как команда.


## Quick start

```bash
novelforge init --project-dir ./my-novel
cd my-novel
# edit project.yaml (genre, chapter count, model routing) and seed.md
novelforge run full --project-dir .
```

## Stage-by-stage

```bash
novelforge run stage foundation --project-dir ./my-novel
novelforge run stage foundation.world --project-dir ./my-novel
novelforge run stage draft --project-dir ./my-novel --from-chapter 1 --to-chapter 5
novelforge run stage revision --project-dir ./my-novel --cycles 3
novelforge run stage review --project-dir ./my-novel
novelforge run stage export --project-dir ./my-novel --formats pdf,epub
novelforge status --project-dir ./my-novel
```

## Pipeline phases

1. **Foundation** — world, characters, outline, canon, voice; loops on the
   weakest layer until `foundation_score > 7.5`.
2. **Draft** — sequential chapter writing; keep if `score > 6.0`, retry
   otherwise (bounded retries).
3. **Revision** — adversarial editing -> cuts -> reader panel -> briefs ->
   rewrite, with plateau detection.
4. **Review** — dual-persona (critic + professor) full-manuscript review via
   any configured LLM, iterating until major items are exhausted.
5. **Export** — LaTeX typesetting (PDF) and a dependency-free EPUB3 build.
   No art or audiobook steps.

See the generated research report for full architectural rationale.
