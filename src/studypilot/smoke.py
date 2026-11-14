"""Manual check of the real Gemini API: python -m studypilot.smoke [--tools] [--role planner]

This is NOT part of the automated tests (it needs a real key and network).
It sends one request, prints the answer, and shows the retry trace.
  --tools   also checks that tool declarations are accepted and a tool call comes back
"""

from __future__ import annotations

import argparse
import sys

from .config import AgentConfig
from .errors import ConfigError, LLMError
from .gemini import GeminiClient
from .tools import declarations
from .trace import Trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="studypilot.smoke")
    parser.add_argument("--tools", action="store_true", help="also test function calling")
    parser.add_argument("--role", choices=["fast", "planner"], default="fast")
    args = parser.parse_args(argv)

    config = AgentConfig.from_env()
    model = config.model_fast if args.role == "fast" else config.model_planner
    trace = Trace()
    try:
        client = GeminiClient(config, model=model, trace=trace)
        print(f"Model: {client.model}")
        reply = client.generate(
            [
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": "Reply with exactly one word: ready"},
            ],
            tools=[],
        )
        print(f"Answer: {reply.text.strip()!r}  (tokens: {reply.tokens_used})")

        if args.tools:
            reply = client.generate(
                [{"role": "user", "content": "Which courses is student S001 enrolled in?"}],
                tools=declarations(),
            )
            calls = [(c.name, c.args) for c in reply.tool_calls]
            print(f"Tool calls requested: {calls}")
            if not calls:
                print("Warning: the model answered without calling a tool.")
    except ConfigError as exc:
        print(f"Configuration problem: {exc}")
        return 1
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return 1
    finally:
        for event in trace.events:
            if event["event"] in ("llm_retry", "llm_error"):
                print(f"  trace: {event['event']} {event.get('error', '')}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
