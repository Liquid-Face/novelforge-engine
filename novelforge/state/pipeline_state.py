"""
Persistent pipeline state, distinct from LangGraph checkpoints: a
human-readable summary of pipeline progress (phase, scores, retries,
propagation debts) stored at state/pipeline_state.json.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class ChapterRecord(BaseModel):
    index: int
    status: str = "pending"  # pending | drafted | evaluated | revised | final
    score: Optional[float] = None
    retries: int = 0


class PropagationDebt(BaseModel):
    source: str
    affected: str
    reason: str
    resolved: bool = False


class PipelineState(BaseModel):
    phase: str = "foundation"
    foundation_score: Optional[float] = None
    chapters: dict[int, ChapterRecord] = Field(default_factory=dict)
    revision_cycle: int = 0
    revision_score_history: list[float] = Field(default_factory=list)
    review_round: int = 0
    propagation_debts: list[PropagationDebt] = Field(default_factory=list)

    @classmethod
    def load_or_create(cls, path: Path) -> "PipelineState":
        if path.exists():
            return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
        return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    def plateaued(self, delta_threshold: float, window: int = 2) -> bool:
        h = self.revision_score_history
        if len(h) < window + 1:
            return False
        recent = h[-(window + 1):]
        diffs = [abs(recent[i + 1] - recent[i]) for i in range(len(recent) - 1)]
        return all(d < delta_threshold for d in diffs)
