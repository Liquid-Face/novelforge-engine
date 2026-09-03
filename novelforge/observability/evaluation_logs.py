from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_attempt_snapshot(directory: Path, iteration: int, *, request: str | None = None,
                           content: str | None = None, metadata: dict[str, Any] | None = None) -> None:
    """Write an evaluation snapshot outside the guarded artifact manifest."""
    directory.mkdir(parents=True, exist_ok=True)
    stem = directory / f"iter-{iteration:02d}"
    if request is not None:
        stem.with_name(f"{stem.name}-request.md").write_text(request, encoding="utf-8")
    if content is not None:
        stem.with_suffix(".md").write_text(content, encoding="utf-8")
    if metadata is not None:
        stem.with_suffix(".json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
