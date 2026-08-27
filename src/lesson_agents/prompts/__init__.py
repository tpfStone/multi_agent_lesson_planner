from __future__ import annotations

from importlib.resources import files


def load_prompt(filename: str) -> str:
    if not filename.endswith(".txt") or "/" in filename or "\\" in filename:
        raise ValueError("Prompt filename must be a simple .txt filename")
    return files(__package__).joinpath(filename).read_text(encoding="utf-8").strip()

