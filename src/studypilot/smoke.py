"""Manual check of the real Gemini API: python -m studypilot.smoke [--tools] [--plan]

This is NOT part of the automated tests (it needs a real key and network).
  (default)  one plain request
  --tools    also checks that tool declarations are accepted and a tool call comes back
  --plan     asks the model for a structured study plan for S001 and validates it
             (the data is gathered with a fixed sequence of calls: this is a manual
             check of structured output, not the autonomous agent)
  --role     choose the fast or planner model
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import AgentConfig
from .errors import ConfigError, LLMError, ValidationError
from .executor import execute_tool
from .gemini import GeminiClient
from .plan import PLAN_SCHEMA, parse_plan
from .tools import declarations
from .trace import Trace


def build_plan_prompt(student_id: str) -> str:
    """Prompt with trusted, validated data only (course descriptions are left out)."""
    courses = execute_tool("get_student_courses", {"student_id": student_id}).data or []
    lines = []
    for course_id in courses:
        info = execute_tool("get_course_info", {"course_id": course_id}).data or {}
        deadlines = execute_tool("get_course_deadlines", {"course_id": course_id}).data or []
        lines.append(
            f"- {course_id} {info.get('title', '')}: exam {info.get('exam_date')}, "
            f"{info.get('weekly_hours')} study hours per week, deadlines: "
            + json.dumps(deadlines)
        )
    return (
        f"Create a study plan for student {student_id}.\n"
        "Courses and deadlines:\n" + "\n".join(lines) + "\n\n"
        "Rules: use only these courses and dates; list tasks in chronological order; "
        "at most 12 hours in total per day; every deadline must have at least one task; "
        "kind is one of study, assignment, exam_prep, exam. "
        "Answer with JSON only."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="studypilot.smoke")
    parser.add_argument("--tools", action="store_true", help="also test function calling")
    parser.add_argument("--plan", action="store_true", help="also test structured plan output")
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

        if args.plan:
            reply = client.generate(
                [
                    {"role": "system", "content": "You create study plans. Output only JSON."},
                    {"role": "user", "content": build_plan_prompt("S001")},
                ],
                tools=[],
                json_schema=PLAN_SCHEMA,
            )
            try:
                plan = parse_plan(reply.text)
            except ValidationError as exc:
                print("Model output was REJECTED by validation:")
                for problem in exc.problems:
                    print(f"  - {problem}")
                return 1
            print(f"Plan accepted: {len(plan.tasks)} tasks, {plan.total_hours():g} hours in total")
            for task in plan.tasks:
                print(f"  {task.date}  {task.course_id}  {task.hours:g}h  [{task.kind}] {task.task}")
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
