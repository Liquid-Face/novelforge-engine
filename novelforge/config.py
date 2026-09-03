"""
Project configuration schema. This is the ONLY place non-lore, production
parameters live (chapter count, genre, thresholds, model routing, logging).
Nothing about the actual story world/characters is defined here.

LLM configuration is role-first: each role (writer/evaluator/reviewer) owns
its own primary endpoint and an optional fallback endpoint.
"""
from __future__ import annotations
from pathlib import Path
from typing import Literal, Optional
import yaml
from pydantic import BaseModel, Field, model_validator

ProviderKind = Literal["ollama", "aitunnel", "openai_compatible"]
RoleName = Literal["writer", "evaluator", "reviewer"]

REQUIRED_ROLES: tuple[RoleName, ...] = ("writer", "evaluator", "reviewer")


class EndpointConfig(BaseModel):
    provider: ProviderKind
    base_url: str
    model: str
    api_key_env: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    request_timeout_s: Optional[int] = None


class RoleConfig(BaseModel):
    primary: EndpointConfig
    fallback: Optional[EndpointConfig] = None


class LLMConfig(BaseModel):
    roles: dict[RoleName, RoleConfig]
    temperature: float = 0.9
    max_tokens: int = 4096
    request_timeout_s: int = 180

    @model_validator(mode="after")
    def _check_required_roles(self) -> "LLMConfig":
        missing = [r for r in REQUIRED_ROLES if r not in self.roles]
        if missing:
            raise ValueError(f"llm.roles is missing required role(s): {missing}")
        return self

    def resolved_defaults_for(self, endpoint: EndpointConfig) -> tuple[float, int, int]:
        return (
            endpoint.temperature if endpoint.temperature is not None else self.temperature,
            endpoint.max_tokens if endpoint.max_tokens is not None else self.max_tokens,
            endpoint.request_timeout_s if endpoint.request_timeout_s is not None else self.request_timeout_s,
        )


class ThresholdsConfig(BaseModel):
    foundation_score: float = 7.5
    foundation_max_iterations: int = 8
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


class LoggingConfig(BaseModel):
    """Console/file observability settings. All non-lore, production
    parameters -- kept here so logging behavior is configured per project,
    not hardcoded in the engine."""
    console_verbosity: Literal["quiet", "normal", "verbose"] = "normal"
    log_to_file: bool = False
    log_file_path: str = "logs/run.log"
    log_evaluate: bool = True
    show_token_counts: bool = True


class ProjectConfig(BaseModel):
    project: ProjectMeta
    llm: LLMConfig
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def load(cls, path: str | Path) -> "ProjectConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            yaml.safe_dump(self.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
