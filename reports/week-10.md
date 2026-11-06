## Week 10 Progress Report

## Completed Work

- Forked the instructor repository and chose the A level.
- Defined the project: StudyPilot, an autonomous academic planning agent that collects a student's courses and deadlines through tools and produces a chronological study plan.
- Wrote `reports/proposal.md`: problem, users, functions, four agent tools (three read-only, one approval-gated write), Gemini model setup, architecture diagram, example requests, evaluation plan with 15 planned tests, and weekly milestones.
- Created the Python project skeleton: configuration with execution limits, explicit agent state, three read-only tools with input validation, an LLM client interface with a mock, a JSONL trace with API-key redaction, and a CLI entry point.
- Created mock data (students, courses, deadlines), including one course description that contains a prompt-injection test string for the week 15 guardrail tests.
- Added 23 unit tests for the existing modules; all pass.
- Added `.env.example` and `docs/SETUP.md`; `.env` is in `.gitignore`.

## Important Commits

- Commit hash: b029c54840378a3912317d2190ba5a63d6696b09
- Description: Add project proposal for StudyPilot
- Link: https://github.com/Yoroto-crypto/css4007-ai-agents-final/commit/b029c54840378a3912317d2190ba5a63d6696b09

- Commit hash: cf412843e0aa014138911a21ac50f70bfca29e8f
- Description: Add project skeleton, mock data, read-only tools, and tests
- Link: https://github.com/Yoroto-crypto/css4007-ai-agents-final/commit/cf412843e0aa014138911a21ac50f70bfca29e8f

## Current Functionality

- The three read-only tools work on mock data and reject malformed IDs.
- Configuration reads limits and model names from environment variables; the API key is never stored in the repository.
- The trace writes JSON Lines and removes API keys from logged values.
- `MockLLM` allows deterministic tests without an API key.
- The agent loop and the Gemini client are not implemented yet; the CLI reports this and exits.

## Problems Encountered

- Deciding how much to build in week 10 versus later weeks, so that the work is spread across the schedule instead of being done at once.
- Choosing where to place the permission and approval checks so that they do not depend on the model's behavior.

## Solutions

- Limited week 10 to planning, data, tools, state, and tracing; the Gemini integration, loop, and guardrails are scheduled for weeks 11-15.
- Decided that the guardrail layer sits between the model's proposed tool call and the tool execution, so the checks run in application code regardless of what the model says or what injected text appears in tool output.

## What I Learned

- An agent is a loop of choosing an action, running a tool, observing the result, and updating state, with explicit limits and stop conditions.
- Tool output is untrusted data and can contain instructions; safety must be enforced in code, not only in the prompt.
- Keeping the LLM behind an interface and using a mock makes agent behavior testable without network access or an API key.
- Logs must record observable actions and never secrets.

## Next Week

- Implement `GeminiClient` with the official SDK and a first working request.
- Add retry and error handling for API failures (rate limits, timeouts, invalid responses).
- Write the first integration test with a mocked API failure and update the README with setup instructions.
