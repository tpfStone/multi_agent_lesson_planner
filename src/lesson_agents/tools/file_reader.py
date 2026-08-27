from __future__ import annotations

from pathlib import Path

from lesson_agents.core.exceptions import ToolExecutionError


class FileReaderTool:
    """Read UTF-8 text only from a configured material directory."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()

    def invoke(self, relative_path: str) -> str:
        requested = (self.base_dir / relative_path).resolve()
        if requested == self.base_dir or self.base_dir not in requested.parents:
            raise ToolExecutionError("FileReader path escapes the configured material directory")
        if not requested.is_file():
            raise ToolExecutionError(f"Material file does not exist: {relative_path}")
        try:
            return requested.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolExecutionError("FileReader supports UTF-8 text files only") from exc

