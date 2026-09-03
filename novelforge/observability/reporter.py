"""
Single-responsibility observability layer: renders run banners, graph node /
router transitions, role/model activation, artifact writes, and token usage
to the console and (optionally) to a log file.
"""
from __future__ import annotations
import logging
import re
from pathlib import Path
from typing import Any, Optional
from rich.console import Console
from rich.table import Table

from novelforge.llm.provider import LLMProvider
from novelforge.state.token_usage import ProjectTokenUsage


_TAG_RE = re.compile(r"\[/?[a-zA-Z0-9 _=#.-]+\]")


def _strip_rich_markup(text: str) -> str:
    return _TAG_RE.sub("", text)


class PipelineReporter:
    def __init__(self, console_verbosity: str = "normal", log_to_file: bool = False,
                 log_file_path: Optional[Path] = None):
        self._verbosity = console_verbosity
        self._console = Console()
        self._file_logger: Optional[logging.Logger] = None
        if log_to_file and log_file_path:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            file_logger = logging.getLogger(f"novelforge.run.{id(self)}")
            file_logger.setLevel(logging.INFO)
            file_logger.propagate = False
            handler = logging.FileHandler(log_file_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            file_logger.addHandler(handler)
            self._file_logger = file_logger

    def _emit(self, text: str, style: Optional[str] = None) -> None:
        if self._verbosity != "quiet":
            self._console.print(text, style=style)
        if self._file_logger:
            self._file_logger.info(_strip_rich_markup(text))

    def _emit_verbose(self, text: str, style: Optional[str] = None) -> None:
        if self._verbosity == "verbose":
            self._console.print(text, style=style)
        if self._file_logger:
            self._file_logger.info(_strip_rich_markup(text))

    def run_banner(self, run_kind: str, project_dir: str, params: dict[str, Any],
                   project_tokens: ProjectTokenUsage | None = None) -> None:
        self._console.print(f"\n[bold cyan]NovelForge run[/bold cyan] — [bold]{run_kind}[/bold]")
        self._console.print(f"[dim]project-dir:[/dim] {project_dir}")
        table = Table(title="Run parameters", show_lines=False)
        table.add_column("Parameter")
        table.add_column("Value")
        for key, value in params.items():
            table.add_row(str(key), str(value))
        if project_tokens:
            table.add_row("project.tokens.prompt_total", str(project_tokens.prompt_tokens_total))
            table.add_row("project.tokens.completion_total", str(project_tokens.completion_tokens_total))
            table.add_row("project.tokens.total", str(project_tokens.total_tokens))
            table.add_row("project.tokens.runs_total", str(project_tokens.runs_total))
        self._console.print(table)
        if self._file_logger:
            self._file_logger.info(f"RUN START kind={run_kind} project_dir={project_dir} params={params}")

    def stage_start(self, stage: str, graph_name: str | None = None) -> None:
        suffix = f" [dim]graph={graph_name}[/dim]" if graph_name else ""
        self._emit(f"\n[bold green]▶ Stage:[/bold green] {stage}{suffix}")

    def stage_end(self, stage: str, llm: LLMProvider | None = None) -> None:
        self._emit(f"[bold green]■ Stage finished:[/bold green] {stage}")
        if llm:
            self.token_usage(llm)

    def cycle(self, label: str, current: int, maximum: int) -> None:
        self._emit(f"  [yellow]↻ {label}:[/yellow] cycle {current}/{maximum}")

    def node(self, node_name: str) -> None:
        self._emit(f"    [magenta]● node:[/magenta] {node_name}")

    def router(self, router_name: str, decision: str, reason: str = "") -> None:
        suffix = f" ({reason})" if reason else ""
        self._emit(f"    [blue]↪ router {router_name} → {decision}[/blue]{suffix}")

    def score(self, label: str, value: float, threshold: Optional[float] = None) -> None:
        if threshold is not None:
            passed = value >= threshold
            marker = "[green]OK[/green]" if passed else "[red]retry[/red]"
            self._emit(f"    [white]score {label}:[/white] {value:.2f} (threshold {threshold:.2f}) {marker}")
        else:
            self._emit(f"    [white]score {label}:[/white] {value:.2f}")

    def feedback(self, text: str, log_evaluate: bool = False) -> None:
        short = " ".join(text.split())[:240]
        if log_evaluate:
            self._emit(f"    [dim]feedback:[/dim] {short}")
        else:
            self._emit_verbose(f"      [dim]feedback:[/dim] {short}")

    def role_call(self, role: str, provider: str, model: str, fallback: bool = False) -> None:
        prefix = "fallback" if fallback else "role"
        self._emit(f"    [cyan]{prefix}:[/cyan] {role} -> {provider} / {model}")

    def llm_request_waiting(self, role: str, provider: str, model: str) -> None:
        self._emit_verbose(f"      [dim]request sent: role={role}, provider={provider}, model={model}; waiting for response...[/dim]")

    def llm_response_received(self, role: str, provider: str, model: str,
                              prompt_tokens: int, completion_tokens: int) -> None:
        self._emit_verbose(
            f"      [dim]response received: role={role}, provider={provider}, model={model}, "
            f"prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}[/dim]"
        )

    def artifact(self, path: str, action: str) -> None:
        self._emit(f"    [white]artifact:[/white] {action} -> {path}")

    def stream_state(self, node_name: str, state_snapshot: dict[str, Any]) -> None:
        safe = {k: v for k, v in state_snapshot.items() if k not in ("layout", "llm", "reporter")}
        self._emit_verbose(f"      [dim]stream state after '{node_name}':[/dim] {safe}")

    def token_usage(self, llm: LLMProvider) -> None:
        totals = llm.usage_totals
        if not totals.has_usage_data:
            self._emit("    [dim]token usage (run total): not reported by provider[/dim]")
            return
        self._emit(
            f"    [dim]tokens (run total) — prompt: {totals.prompt_tokens}, "
            f"completion: {totals.completion_tokens}, total: {totals.total_tokens}[/dim]"
        )

    def project_token_usage(self, project_tokens: ProjectTokenUsage) -> None:
        self._emit(
            f"    [dim]tokens (project total) — prompt: {project_tokens.prompt_tokens_total}, "
            f"completion: {project_tokens.completion_tokens_total}, total: {project_tokens.total_tokens}, "
            f"runs: {project_tokens.runs_total}[/dim]"
        )

    def warning(self, text: str) -> None:
        self._emit(f"[bold red]⚠ {text}[/bold red]")


def build_reporter_from_config(logging_config, project_root: Path) -> PipelineReporter:
    log_path = project_root / logging_config.log_file_path if logging_config.log_to_file else None
    return PipelineReporter(
        console_verbosity=logging_config.console_verbosity,
        log_to_file=logging_config.log_to_file,
        log_file_path=log_path,
    )
