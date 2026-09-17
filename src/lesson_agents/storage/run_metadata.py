from __future__ import annotations

from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import subprocess


def json_hash(value: object) -> str:
    """Hash decoded JSON, not source bytes: sorted keys, compact UTF-8, no ASCII escapes."""
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def code_provenance() -> dict:
    """Inspect this source checkout, never an unrelated caller's working directory."""
    root = Path(__file__).resolve().parents[3]
    result = {"git_commit": None, "git_dirty": None, "git_notes": []}
    try:
        def git(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git", "-C", str(root), *args], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=5, check=True,
            )

        checkout = git("rev-parse", "--show-toplevel")
        if Path(checkout.stdout.strip()).resolve() != root:
            result["git_notes"].append("source_is_not_repository_root")
            return result
        result["git_commit"] = git("rev-parse", "HEAD").stdout.strip()
        status = git("status", "--porcelain", "--untracked-files=all")
        # A warning can hide files, so do not claim clean without a complete read.
        result["git_dirty"] = True if status.stdout.strip() else (None if status.stderr else False)
        if status.stderr:
            result["git_notes"].append("git_status_reported_warnings")
    except (OSError, subprocess.SubprocessError):
        result["git_notes"].append("git_information_unavailable")
    return result


def environment_versions() -> dict:
    packages = {}
    for name in ("langgraph", "pydantic", "PyYAML", "openai"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "packages": packages}
