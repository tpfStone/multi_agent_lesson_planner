from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from lesson_agents.app import run_lesson_pipeline
from lesson_agents.models.provider import DeepSeekModelProvider, OpenAIModelProvider


def load_real_provider() -> OpenAIModelProvider:
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("Install real dependencies with: pip install -e '.[real]'") from exc

    tracked_keys = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "LESSON_MODEL_ID")
    configured_before = {key for key in tracked_keys if os.getenv(key)}
    env_path = Path(__file__).resolve().parents[1] / ".env"
    dotenv_loaded = load_dotenv(dotenv_path=env_path, override=False)
    provider_name = os.getenv("LESSON_PROVIDER", "").strip().lower()
    configured_after = {key for key in tracked_keys if os.getenv(key)}

    if configured_before == configured_after and configured_after:
        source = "environment"
    elif dotenv_loaded:
        source = "dotenv" if not configured_before else "environment_and_dotenv"
    else:
        source = "environment"

    if provider_name == "deepseek":
        return DeepSeekModelProvider.from_env(configuration_source=source)
    if provider_name == "openai":
        return OpenAIModelProvider.from_env(configuration_source=source)
    raise RuntimeError(
        "LESSON_PROVIDER must be 'openai' or 'deepseek' when --real is used"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 1 lesson-plan pipeline")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", help="Use deterministic network-free responses")
    mode.add_argument("--real", action="store_true", help="Use OPENAI_API_KEY and LESSON_MODEL_ID")
    args = parser.parse_args()

    raw_task = json.loads(args.input.read_text(encoding="utf-8"))
    provider = load_real_provider() if args.real else None
    result = run_lesson_pipeline(raw_task, provider=provider, runs_dir=args.runs_dir)

    print(f"run_id: {result.run_id}")
    print(f"status: {result.status}")
    print(f"validation_valid: {result.validation_valid}")
    print(f"run_dir: {result.run_dir}")
    print(f"final_artifact: {result.final_artifact_path}")


if __name__ == "__main__":
    main()
