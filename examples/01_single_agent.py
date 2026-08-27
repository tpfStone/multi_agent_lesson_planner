from __future__ import annotations

import argparse

from lesson_agents.models.mock import MockModelProvider
from lesson_agents.models.provider import OpenAIModelProvider
from lesson_agents.prompts import load_prompt


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-agent provider demonstration")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", help="Use the deterministic network-free provider")
    mode.add_argument("--real", action="store_true", help="Use OPENAI_API_KEY and LESSON_MODEL_ID")
    args = parser.parse_args()

    provider = (
        OpenAIModelProvider.from_env()
        if args.real
        else MockModelProvider(text_responses=["我是课程助理，可以帮助梳理教学目标。"])
    )
    result = provider.generate_text(
        system_prompt=load_prompt("single_agent_v1.txt"),
        user_prompt="请用一句话介绍你的职责。",
        temperature=0.0,
    )
    print(result.value)
    print(f"provider={result.metadata.provider}, model={result.metadata.model_id}")


if __name__ == "__main__":
    main()
