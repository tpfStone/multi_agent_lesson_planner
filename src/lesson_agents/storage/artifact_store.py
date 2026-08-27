from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ArtifactStore:
    """JSON artifact storage scoped to one run directory."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir.resolve()
        self.run_dir.mkdir(parents=True, exist_ok=False)

    def save_json(self, filename: str, value: Any) -> Path:
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise ValueError("Artifact filename must be a simple .json filename")
        target = self.run_dir / filename
        target.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return target

    def exists(self, filename: str) -> bool:
        return (self.run_dir / filename).is_file()

