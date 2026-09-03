from __future__ import annotations
import shutil
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
from novelforge import api

app = typer.Typer(help="Provider-agnostic autonomous novel-writing pipeline (text-only).")
run_app = typer.Typer(help="Run the full pipeline or an individual stage.")
app.add_typer(run_app, name="run")
console = Console()
_TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "project"

@app.command()
def init(project_dir: str = typer.Option(..., "--project-dir"), config: str = typer.Option(None, "--config", help="Path to a project.yaml to copy in")):
    root = Path(project_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for item in _TEMPLATE_DIR.iterdir():
        dest = root / item.name
        if dest.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy(item, dest)
    if config:
        shutil.copy(config, root / "project.yaml")
    console.print(f"[green]Initialized project at {root}[/green]")

@run_app.command("full")
def run_full(project_dir: str = typer.Option(..., "--project-dir"), verbosity: str = typer.Option(None, "--verbosity", help="quiet | normal | verbose (overrides project.yaml)")):
    api.run_full_pipeline(project_dir, verbosity_override=verbosity)

@run_app.command("stage")
def run_stage(stage: str = typer.Argument(...), project_dir: str = typer.Option(..., "--project-dir"), from_chapter: int = typer.Option(1, "--from-chapter"), to_chapter: int = typer.Option(None, "--to-chapter"), cycles: int = typer.Option(None, "--cycles"), formats: str = typer.Option(None, "--formats", help="comma-separated: pdf,epub"), force: bool = typer.Option(False, "--force-regenerate"), verbosity: str = typer.Option(None, "--verbosity", help="quiet | normal | verbose (overrides project.yaml)")):
    api.run_stage(stage=stage, project_dir=project_dir, from_chapter=from_chapter, to_chapter=to_chapter, cycles=cycles, formats=formats.split(",") if formats else None, force=force, verbosity_override=verbosity)

@app.command()
def status(project_dir: str = typer.Option(..., "--project-dir")):
    ps, cfg = api.get_status(project_dir)
    table = Table(title=f"NovelForge status: {cfg.project.title}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Phase", ps.phase)
    table.add_row("Foundation score", str(ps.foundation_score))
    table.add_row("Chapters drafted", str(len(ps.chapters)))
    table.add_row("Revision cycle", str(ps.revision_cycle))
    table.add_row("Review round", str(ps.review_round))
    console.print(table)

if __name__ == "__main__":
    app()
