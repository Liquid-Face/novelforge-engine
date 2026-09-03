"""
Project configuration schema. This is the ONLY place non-lore, production
parameters live (chapter count, genre, thresholds, model routing). Nothing
about the actual story world/characters is defined here.
"""
from __future__ import annotations
from pathlib import Path
from typing import Literal, Optional
import yaml
from pydantic import BaseModel, Field


class LLMRoleModels(BaseModel):
    writer: str
    evaluator: str
    reviewer: str


class LLMConfig(BaseModel):
    provider: Literal["aitunnel", "ollama", "openai_compatible"] = "ollama"
    base_url: str = "http://localhost:11434/v1"
    api_key_env: Optional[str] = None
    models: LLMRoleModels
    fallback_provider: Optional[Literal["aitunnel", "ollama", "openai_compatible"]] = None
    fallback_base_url: Optional[str] = None
    fallback_api_key_env: Optional[str] = None
    fallback_models: Optional[LLMRoleModels] = None
    temperature: float = 0.9
    max_tokens: int = 4096
    request_timeout_s: int = 180


class ThresholdsConfig(BaseModel):
    foundation_score: float = 7.5
    lore_score: float = 7.0
    chapter_score: float = 6.0
    max_draft_retries: int = 5
    revision_plateau_delta: float = 0.5
    revision_max_cycles: int = 6
    review_max_rounds: int = 4
    review_stop_max_items: int = 2


class ExportConfig(BaseModel):
    typeset_engine: Literal["tectonic", "pdflatex"] = "tectonic"
    formats: list[Literal["pdf", "epub"]] = Field(default_factory=lambda: ["pdf", "epub"])
    trim_size: str = "5.5x8.5in"
    font: str = "EB Garamond"


class PathsConfig(BaseModel):
    manuscript_dir: str = "manuscript/chapters"
    lore_dir: str = "manuscript"
    state_dir: str = "state"
    logs_dir: str = "logs"
    briefs_dir: str = "state/briefs"
    export_dir: str = "export"


class ProjectMeta(BaseModel):
    title: str = "Untitled Novel"
    language: str = "ru"
    genre: str = "literary fiction"
    target_audience: str = "adult"
    chapters_total: int = 20
    chapter_length_words: tuple[int, int] = (2200, 3200)
    total_length_words_target: int = 80000


class ProjectConfig(BaseModel):
    project: ProjectMeta
    llm: LLMConfig
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    @classmethod
    def load(cls, path: str | Path) -> "ProjectConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            yaml.safe_dump(self.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
