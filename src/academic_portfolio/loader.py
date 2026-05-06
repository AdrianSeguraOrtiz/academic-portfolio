from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class LoadedData:
    """YAML documents loaded from the portfolio data directory."""

    root: Path
    documents: dict[str, Any]

    @property
    def file_count(self) -> int:
        return len(self.documents)

    @property
    def top_level_groups(self) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for path, document in self.documents.items():
            if isinstance(document, dict):
                groups[path] = list(document.keys())
            else:
                groups[path] = []
        return groups


def load_data(data_dir: Path | str = "data") -> LoadedData:
    """Load every YAML file under `data_dir`, keyed by path relative to that directory."""

    root = Path(data_dir)
    if not root.exists():
        raise FileNotFoundError(f"Data directory not found: {root}")

    documents: dict[str, Any] = {}
    for path in sorted(root.rglob("*.yaml")):
        relative_path = path.relative_to(root).as_posix()
        with path.open("r", encoding="utf-8") as handle:
            documents[relative_path] = yaml.safe_load(handle)

    return LoadedData(root=root, documents=documents)
