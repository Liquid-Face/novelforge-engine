"""
Resolves the on-disk layout of a novel project (a directory the engine
receives as a CLI parameter). The engine never assumes a fixed location --
every path is derived from --project-dir + project.yaml paths section.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from novelforge.config import ProjectConfig
from novelforge.state.manifest import Manifest
from novelforge.state.pipeline_state import PipelineState


@dataclass
class ProjectLayout:
    root: Path
    config: ProjectConfig

    @classmethod
    def open(cls, project_dir: str | Path) -> "ProjectLayout":
        root = Path(project_dir).resolve()
        config_path = root / "project.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"project.yaml not found in {root}. Run 'novelforge init' first.")
        return cls(root=root, config=ProjectConfig.load(config_path))

    @property
    def seed_path(self) -> Path:
        return self.root / "seed.md"

    @property
    def lore_dir(self) -> Path:
        return self.root / self.config.paths.lore_dir

    @property
    def world_path(self) -> Path:
        return self.lore_dir / "world.md"

    @property
    def characters_path(self) -> Path:
        return self.lore_dir / "characters.md"

    @property
    def outline_path(self) -> Path:
        return self.lore_dir / "outline.md"

    @property
    def canon_path(self) -> Path:
        return self.lore_dir / "canon.md"

    @property
    def voice_path(self) -> Path:
        return self.lore_dir / "voice.md"

    @property
    def arc_summary_path(self) -> Path:
        return self.lore_dir / "arc_summary.md"

    @property
    def chapters_dir(self) -> Path:
        return self.root / self.config.paths.manuscript_dir

    def chapter_path(self, index: int) -> Path:
        return self.chapters_dir / f"ch_{index:02d}.md"

    @property
    def state_dir(self) -> Path:
        return self.root / self.config.paths.state_dir

    @property
    def briefs_dir(self) -> Path:
        return self.root / self.config.paths.briefs_dir

    @property
    def logs_dir(self) -> Path:
        return self.root / self.config.paths.logs_dir

    @property
    def export_dir(self) -> Path:
        return self.root / self.config.paths.export_dir

    @property
    def manifest_path(self) -> Path:
        return self.state_dir / "manifest.json"

    @property
    def pipeline_state_path(self) -> Path:
        return self.state_dir / "pipeline_state.json"

    @property
    def checkpoint_db_path(self) -> Path:
        return self.state_dir / "checkpoints.db"

    def manifest(self) -> Manifest:
        return Manifest(self.manifest_path)

    def pipeline_state(self) -> PipelineState:
        return PipelineState.load_or_create(self.pipeline_state_path)

    def ensure_dirs(self) -> None:
        for d in [self.lore_dir, self.chapters_dir, self.state_dir, self.briefs_dir,
                  self.logs_dir, self.export_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def read(self, path: Path, default: str = "") -> str:
        return path.read_text(encoding="utf-8") if path.exists() else default

    def write_guarded(self, path: Path, content: str, force: bool = False) -> bool:
        """Writes content unless a human has edited the file since last generation."""
        rel = str(path.relative_to(self.root))
        m = self.manifest()
        if not m.can_overwrite(rel, self.root, force=force):
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        m.record(rel, self.root)
        return True
