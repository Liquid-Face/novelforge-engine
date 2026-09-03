"""
Manifest tracks the sha256 hash of every engine-generated artifact at the
moment of generation. If a file's on-disk hash no longer matches the
manifest, a human has edited it -- the engine must not silently overwrite it.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Optional


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Manifest:
    def __init__(self, manifest_path: Path):
        self.path = manifest_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, str] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def is_human_edited(self, rel_path: str, project_root: Path) -> bool:
        target = project_root / rel_path
        if rel_path not in self._data or not target.exists():
            return False
        return _sha256(target) != self._data[rel_path]

    def record(self, rel_path: str, project_root: Path) -> None:
        target = project_root / rel_path
        self._data[rel_path] = _sha256(target)
        self._save()

    def can_overwrite(self, rel_path: str, project_root: Path, force: bool = False) -> bool:
        if force:
            return True
        return not self.is_human_edited(rel_path, project_root)
