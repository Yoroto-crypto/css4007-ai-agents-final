## Week 11 Progress Report

## Completed Work

- Implemented `GeminiClient` on top of the official `google-genai` SDK. It builds requests from our message format, supports a system instruction, registers tool declarations for function calling, and parses text, tool calls, and token usage from the response.
- Made a first real request to the Gemini API with my own key using `python -m studypilot.smoke`, and checked with `--tools` that the tool declarations are accepted and the model asks to call a tool.
- Added a model-layer exception hierarchy (`errors.py`) so that the agent does not depend on SDK exception types: transient, permanent, retries exhausted, invalid response, and configuration errors.
- Implemented retries with exponential backoff and jitter (`retry.py`), controlled by `MAX_RETRIES`. Only transient errors (429, 408, 5xx, timeouts, connection errors) are retried; wrong key, unknown model, and bad requests fail immediately with a hint.
- Added handling for unusable responses (empty answer, blocked prompt, function call without a name).
- Retries, errors, and responses are written to the trace; API keys are redacted from error messages and logs.
- Added 30 new tests (53 in total) using a fake SDK client: retry success, rate limit, network errors, exhausted retries, permanent errors, empty and blocked responses, key redaction, configuration errors.
- Fixed the installation instructions: with the `src` layout the package must be installed with `pip install -e .`; updated `pyproject.toml` and `docs/SETUP.md` accordingly.

## Important Commits

- Commit hash: 914c2168a5eac791cb2a5c287f5d9551cc95e7e8
- Description: Add Gemini client with error classification and retries
- Link: https://github.com/Yoroto-crypto/css4007-ai-agents-final

- Commit hash: 6572909521c116e09bff8ec98650499e19097f5e
- Description: Add tests for retries and Gemini client failures
- Link: https://github.com/Yoroto-crypto/css4007-ai-agents-final

- Commit hash: 871d7ee3cae835e974c834e6f0a85cc83252fb25
- Description: Add smoke check, update setup docs
- Link: https://github.com/Yoroto-crypto/css4007-ai-agents-final

## Current Functionality

- A real Gemini request works through `GeminiClient`; the model name is taken from environment variables, so the fast and planner models can be swapped without code changes.
- Transient API failures are retried within the configured limit; permanent failures and invalid responses stop with a clear message.
- The CLI validates configuration and reports problems (missing key or model) before doing anything else.
- The agent loop is still not implemented (weeks 13-14); tool results are not yet returned to the model.
- GEMINI_MODEL_PLANNER=gemini-3.5-flash-lite, GEMINI_MODEL_FAST=gemini-3.1-flash-lite

## Problems Encountered

- Deciding which failures deserve a retry: retrying a wrong key or an unknown model would waste the retry budget and delay a clear error.
- Making the Gemini client testable without network access or a key.
- Not being sure that every JSON-schema keyword in my tool declarations (for example `pattern`) is accepted by the Gemini API.

## Solutions

- Classified errors by HTTP status and exception type, and retry only 408, 429, 5xx, timeouts, and connection errors.
- Injected the SDK client and the sleep function, so tests use a fake client and run instantly.
- Strip `pattern` from the declarations sent to Gemini; the pattern remains in my own tool specs and the validation is done in application code (week 12), which is the stronger guarantee anyway.

## What I Learned

- A model API call can fail in several different ways, and each needs different handling: retry, stop with a hint, or report an unusable answer.
- Backoff with jitter avoids hammering a rate-limited API, and the retry limit prevents uncontrolled loops.
- Converting SDK exceptions into my own types keeps the rest of the agent independent of one provider.
- Secrets can leak through error messages and logs, so they have to be redacted in one central place.

## Next Week

- Implement input and output validation: validate tool arguments against the declared schema (types, patterns, required fields) before execution.
- Add structured, validated output for the final plan (dates, tasks, hours).
- Add tests for malformed arguments and invalid output.
