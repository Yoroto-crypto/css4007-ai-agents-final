"""Command-line entry point: python -m studypilot "<goal>"."""

from __future__ import annotations

import argparse
import sys

from .agent import run_agent
from .config import AgentConfig
from .errors import ConfigError, LLMError
from .gemini import GeminiClient
from .trace import Trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="studypilot", description="Academic planning agent")
    parser.add_argument("goal", help="what you want the agent to do")
    args = parser.parse_args(argv)

    config = AgentConfig.from_env()
    trace = Trace("logs/trace.jsonl")
    try:
        llm = GeminiClient(config, trace=trace)
        result = run_agent(args.goal, config, llm, trace)
    except ConfigError as exc:
        print(f"Configuration problem: {exc}")
        return 1
    except LLMError as exc:
        print(f"The model could not be reached or gave an unusable answer: {exc}")
        return 1
    except NotImplementedError as exc:
        print(f"Not available yet: {exc}")
        return 2
    print(result.answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
