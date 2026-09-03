from __future__ import annotations
import json
from pathlib import Path
from pydantic import BaseModel


class ProjectTokenUsage(BaseModel):
    """Persistent token counters stored per novel project. Keeps cumulative
    totals across all runs, separate from per-process counters inside
    LLMProvider. This state is intentionally tiny and independent from the
    rest of pipeline_state to avoid coupling token accounting to story logic."""
    prompt_tokens_total: int = 0
    completion_tokens_total: int = 0
    runs_total: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens_total + self.completion_tokens_total

    @classmethod
    def load_or_create(cls, path: Path) -> "ProjectTokenUsage":
        if path.exists():
            return cls.model_validate(json.loads(path.read_text(encoding='utf-8')))
        return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding='utf-8')

    def merge_run(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens_total += prompt_tokens
        self.completion_tokens_total += completion_tokens
        self.runs_total += 1
