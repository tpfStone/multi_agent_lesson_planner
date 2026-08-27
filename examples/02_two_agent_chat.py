from __future__ import annotations

import argparse

from lesson_agents.models.mock import MockModelProvider
from lesson_agents.models.provider import OpenAIModelProvider
from lesson_agents.prompts import load_prompt


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal professor/student two-agent dialogue")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true")
    mode.add_argument("--real", action="store_true")
    args = parser.parse_args()

    provider = (
        OpenAIModelProvider.from_env()
        if args.real
        else MockModelProvider(
            text_responses=[
                "请先说明移项时为什么要改变符号。",
                "移项等价于在等式两边同时加上或减去同一个式子，因此移到另一边后符号改变。",
            ]
        )
    )
    professor = provider.generate_text(
        system_prompt=load_prompt("professor_v1.txt"),
        user_prompt="主题是一元一次方程，请向学生提问。",
        temperature=0.2,
    ).value
    student = provider.generate_text(
        system_prompt=load_prompt("student_v1.txt"),
        user_prompt=professor,
        temperature=0.2,
    ).value
    print(f"教授：{professor}")
    print(f"学生：{student}")


if __name__ == "__main__":
    main()
