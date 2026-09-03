# NovelForge Engine

Provider-agnostic, text-only autonomous novel-writing pipeline engine, built
on LangGraph. The current release is `0.2.0`. It is inspired by
[NousResearch/autonovel](https://github.com/NousResearch/autonovel), but keeps
the engine separate from each novel project and uses OpenAI-compatible LLM
endpoints for local Ollama or AITUNNEL deployments.

Repository: <https://github.com/Liquid-Face/novelforge-engine>

## Requirements

- Python 3.10 or newer.
- For AITUNNEL, an `AITUNNEL_API_KEY` environment variable.
- For local inference, Ollama available at `http://localhost:11434/v1`.
- For PDF output, optionally install `tectonic` or `pdflatex`. EPUB output
  does not require an external EPUB package.

## Install

All of the following install the `novelforge` console script. PyPI does not
currently publish a NovelForge package.

### A. Install from GitHub with pipx or uv

```bash
pipx install git+https://github.com/Liquid-Face/novelforge-engine.git
# or
uv tool install git+https://github.com/Liquid-Face/novelforge-engine.git
```

These commands are convenient for the CLI. The repository's `init` command
copies the project template from the source tree, so use the clone + editable
installation below when the installed package does not include
`templates/project/`.

### B. Clone and install editable

This is the recommended path for development and for reliable project
initialization.

```bash
git clone https://github.com/Liquid-Face/novelforge-engine.git
cd novelforge-engine
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Use `novelforge` while the virtual environment is active, or use
`.venv/bin/novelforge` directly.

### C. Install from Git into the current environment

```bash
pip install git+https://github.com/Liquid-Face/novelforge-engine.git
```

Verify the command:

```bash
novelforge --help
```

If the command is not found, update your shell PATH with `pipx ensurepath` or
`uv tool update-shell`, or activate the virtual environment.

## First novel

Create a project outside the engine repository. The project contains the
novel data; the engine repository contains code and prompt templates.

```bash
novelforge init --project-dir ./my-novel
```

Edit `./my-novel/project.yaml` and `./my-novel/seed.md`. Configure the
role-first LLM endpoints in `llm.roles`; when using AITUNNEL, set the key:

```bash
export AITUNNEL_API_KEY=your-key
novelforge run full --project-dir ./my-novel
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

`run stage foundation` accepts `world`, `characters`, `outline`, `canon`, and
`voice`; a single layer is selected as `foundation.<layer>`. Both `run full`
and `run stage` accept `--verbosity quiet|normal|verbose`. Only `run stage`
accepts `--force-regenerate`, which intentionally permits replacing
human-edited artifacts.

## Pipeline phases

1. **Foundation** generates and evaluates `world`, `characters`, `outline`,
   `canon`, and `voice` sequentially. Each layer retries until it reaches the
   configured `foundation_score` or `foundation_max_iterations` limit.
2. **Draft** writes chapters sequentially, retrying below `chapter_score` up to
   the configured retry limit. If the budget is exhausted, it restores the
   best-scoring attempt and rebuilds `arc_summary.md` after advancing.
3. **Revision** runs adversarial editing, cuts, reader-panel feedback, a brief,
   and a rewrite for each chapter. It stops at the configured cycle limit or a
   score plateau.
4. **Review** performs manuscript review and fixes actionable items until
   `review_stop_max_items` or `review_max_rounds` is reached.
5. **Export** builds LaTeX and optionally compiles a PDF, and builds a
   dependency-free EPUB3. There are no image or audiobook stages.

## Configuration and state

Each role (`writer`, `evaluator`, and `reviewer`) has a required `primary`
endpoint and an optional per-role `fallback` endpoint. Generated artifacts are
protected by `state/manifest.json`; manual edits are not silently overwritten.
Run observability is controlled by `logging` and `--verbosity`; set
`logging.show_token_counts` to `false` to hide token counts from the console
while retaining them in state and file logs. Foundation
attempts are logged under `logs/foundation/<layer>/`, draft attempts under
`logs/draft/ch_NN/`, and cumulative project token totals are stored in
`state/token_usage.json`.

For the current architecture, see
`Architecture-of-an-autonomous-pipeline-for-novel-generation.md`.
