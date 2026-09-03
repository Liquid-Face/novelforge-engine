# Agent Instructions

## Repository Scope

- This repository is the Python engine only; novel data belongs in a separate `--project-dir` created from `templates/project/`, not in the engine tree.
- The runtime entrypoints are the `novelforge` console script (`novelforge.cli:app`) and the orchestration functions in `novelforge/api.py`; keep CLI logic thin and put pipeline behavior in the API, graphs, or tools.
- Pipeline phases are Foundation, Draft, Revision, Review, and Export. Graph implementations live in `novelforge/graphs/`; side-effecting stage operations live in `novelforge/tools/`.
- Prompt text must stay in `novelforge/prompts/templates/*.jinja2` and be rendered through `novelforge.prompts.renderer`; do not embed novel-specific prompts in Python.

## Configuration And Data

- `ProjectLayout.open()` requires `<project-dir>/project.yaml`; use `novelforge init --project-dir <path>` before running a project.
- The current LLM schema is role-first: `llm.roles.writer`, `llm.roles.evaluator`, and `llm.roles.reviewer` each require `primary` and may define `fallback`. The old top-level `provider`/`models`/`fallback_*` schema is invalid.
- Each endpoint is OpenAI-compatible and declares its own `provider`, `base_url`, `model`, and optional `api_key_env`; Ollama normally needs no key, while the template uses `AITUNNEL_API_KEY` for AITUNNEL.
- Treat `templates/project/project.yaml` as the canonical project-config example. It also defines thresholds, export formats, paths, and logging; do not hardcode those production parameters.
- A project contains `seed.md`, lore under `manuscript/`, chapters under `manuscript/chapters/`, persistent JSON/token state under `state/`, logs under `logs/`, and exports under `export/`.
- Generated artifacts go through `ProjectLayout.write_guarded()` and `state/manifest.json`; a changed on-disk hash means a human edit and must not be overwritten unless the caller explicitly passes `--force-regenerate` (CLI: `--force`).
- `state/pipeline_state.json` is the human-readable progress summary and `state/token_usage.json` stores cumulative project token totals; `ProjectLayout.checkpoint_db_path` exists, but LangGraph SQLite checkpoint persistence is not currently wired into the API.

## Commands

- Install editable development code with `pip install -e .` or `uv tool install -e .`; Python `>=3.10` is required.
- Initialize a novel project with `novelforge init --project-dir ./my-novel`; edit its `project.yaml` and `seed.md` before generation.
- Run the full pipeline with `novelforge run full --project-dir ./my-novel`.
- Run a complete foundation stage with `novelforge run stage foundation --project-dir ./my-novel`, or one layer with `novelforge run stage foundation.world --project-dir ./my-novel` (valid layers: `world`, `characters`, `outline`, `canon`, `voice`).
- Run selected chapters with `novelforge run stage draft --project-dir ./my-novel --from-chapter 1 --to-chapter 5`; revision accepts `--cycles N`, and export accepts `--formats pdf,epub`.
- Use `--verbosity quiet|normal|verbose` on `run full` and `run stage`; use `--force-regenerate` on `run stage` only when intentionally replacing human-edited artifacts.
- Inspect persisted progress with `novelforge status --project-dir ./my-novel`.
- There is no repository test suite, lint configuration, formatter configuration, or CI workflow. The focused baseline verification is `.venv/bin/python -m compileall -q novelforge`; the CLI smoke check is `.venv/bin/novelforge --help`.

## Implementation Notes

- `LLMProvider.complete(..., role=...)` is the stable boundary used by tools; endpoint selection, client reuse, fallback on OpenAI API/timeout/connection errors, and per-run token accumulation belong inside `novelforge/llm/provider.py`.
- Graph nodes inject `PipelineReporter` and stream through `graph.stream(..., stream_mode="values")`; keep observability in the reporter/API/graph boundary rather than printing from tools.
- Foundation regenerates the evaluator-selected weakest layer until the configured score threshold or iteration limit. Draft retries a chapter until its score passes the threshold or retry limit, then advances and rebuilds the arc summary.
- Revision stops at the configured cycle limit or score plateau. Review stops at the configured actionable-item limit or round limit. These are configuration values, not constants to duplicate in code.
- Export creates `export/novel.tex`, optionally compiles PDF with the configured engine or `pdflatex` fallback, and creates EPUB3 without an external EPUB dependency; there are no image or audiobook stages.
- When documentation conflicts with executable code, follow `pyproject.toml`, the CLI/API, and `templates/project/project.yaml`; use `CHANGES.md` to preserve the role-first configuration and observability behavior.
