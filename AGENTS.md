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

## Git workflow and versioning

### Repository model

- This is a single-developer repository.
- `origin` on GitHub is the canonical remote and is used for synchronization between devices.
- `main` is the primary integration branch.
- `main` must remain buildable and runnable. Do not leave knowingly broken, incomplete, or destructive experiments on `main`.
- Prefer a linear history. Avoid merge commits unless they preserve meaningful history.
- Never rewrite, force-push, reset, or delete remote history without explicit user approval.

### Branch policy

- Small, safe, self-contained changes may be committed directly to `main`.
- Use short-lived branches for work that spans multiple commits, introduces risk, changes architecture, or may temporarily break the build.
- Branch naming:
  - `feat/<short-kebab-case-name>` for a feature
  - `fix/<short-kebab-case-name>` for a bug fix
  - `refactor/<short-kebab-case-name>` for a refactor
  - `chore/<short-kebab-case-name>` for maintenance, tooling, dependencies, or documentation
- Examples:
  - `feat/local-rag-import`
  - `fix/audio-export-crash`
  - `refactor/storage-layer`
  - `chore/update-dependencies`
- Before beginning work, synchronize safely:
  ```bash
  git switch main
  git pull --ff-only origin main
  ```
- Integrate a completed branch using fast-forward only when possible:
  ```bash
  git switch main
  git merge --ff-only <branch-name>
  ```
- Delete merged local feature branches after successful integration. Delete remote feature branches only after confirmation that they are no longer needed.

### Commit policy

- Make small, coherent, reversible commits.
- Do not mix unrelated changes in one commit.
- Do not commit generated build output, secrets, tokens, local databases, private user data, or machine-specific files unless the repository explicitly requires them.
- Use Conventional Commit-style messages:
  ```text
  <type>(<optional-scope>): <imperative summary>
  ```
- Allowed types:
  - `feat`: new user-visible functionality
  - `fix`: bug fix
  - `refactor`: internal restructuring without changing intended behavior
  - `perf`: performance improvement
  - `test`: tests
  - `docs`: documentation
  - `build`: build system, packages, or project configuration
  - `ci`: continuous integration configuration
  - `chore`: maintenance work
- Examples:
  ```text
  feat(import): add PDF ingestion pipeline
  fix(storage): prevent duplicate document records
  refactor(chat): isolate prompt construction
  docs: add local development setup
  ```
- Inspect the intended changes before committing:
  ```bash
  git status
  git diff
  git diff --staged
  ```

### Tags and releases

- Git tags represent immutable, reproducible, validated project states.
- Use annotated tags only:
  ```bash
  git tag -a v<version> -m "Release v<version>"
  ```
- Create release tags only from a validated commit on `main`.
- Never move, overwrite, delete, or force-push an existing release tag.
- Tag format:
  ```text
  vMAJOR.MINOR.PATCH
  ```
- Pre-release tag format, only when needed:
  ```text
  vMAJOR.MINOR.PATCH-alpha.N
  vMAJOR.MINOR.PATCH-beta.N
  vMAJOR.MINOR.PATCH-rc.N
  ```
- Examples:
  ```text
  v0.1.0
  v0.4.2
  v0.5.0-beta.1
  v1.0.0
  ```
- Push a release tag explicitly:
  ```bash
  git push origin v<version>
  ```
- Do not create a GitHub Release, upload release artifacts, publish a package, or push tags unless the user explicitly asks for that action.

### Versioning policy

- Use Semantic Versioning: `MAJOR.MINOR.PATCH`.
- Before the first public stable release, use `0.MINOR.PATCH`.
- Increase `MINOR` for a meaningful feature set, data model change, notable UX change, or other significant project milestone:
  ```text
  0.4.0 -> 0.5.0
  ```
- Increase `PATCH` for backwards-compatible bug fixes and small safe improvements:
  ```text
  0.5.0 -> 0.5.1
  ```
- Use `alpha`, `beta`, and `rc` only for deliberately identified pre-release checkpoints.
- Do not bump the product version for every code commit.
- For Apple apps:
  - `CFBundleShortVersionString` is the user-facing semantic version, for example `0.5.0`.
  - `CFBundleVersion` is a monotonically increasing build number.
  - A Git release tag must identify the exact commit used for the corresponding distributable build.

### Release checklist

Before proposing a release tag:

1. Confirm the working tree is clean.
2. Confirm `main` is up to date with `origin/main`.
3. Build and run the project successfully.
4. Run applicable tests, linting, and validation.
5. Update the user-facing version where the project stores it.
6. Update `CHANGELOG.md`, moving completed entries from `Unreleased` to the new version section.
7. Create one release-preparation commit.
8. Show the proposed version, changelog summary, commit SHA, and exact tag command to the user.
9. Wait for explicit user approval before creating or pushing a tag, GitHub Release, or distributable artifact.

### Safety rules for agents

- Never use `git push --force`, `git reset --hard`, `git clean -fd`, `git rebase`, tag deletion, branch deletion, or history rewriting without explicit user approval.
- Never commit or push automatically after making changes unless the user explicitly requested a commit or push.
- Before any commit, tag, push, release, or remote deletion, present:
  - the target branch or tag;
  - the exact files or commits involved;
  - the proposed commit message or tag name;
  - the exact Git command to be executed.
- If the repository state is unclear, stop and ask before performing destructive or history-altering Git operations.