# StudyPilot: setup and run

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1         # Windows PowerShell
# source .venv/bin/activate        # Mac / Linux

pip install -r requirements.txt
pip install -e .                   # makes `studypilot` importable (src layout)
cp .env.example .env               # Windows: copy .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=<your key from Google AI Studio>
GEMINI_MODEL_FAST=<a fast Gemini model name>
GEMINI_MODEL_PLANNER=<a stronger Gemini model name>
```

Model names are not hard-coded. Take current names from the Gemini API documentation or
Google AI Studio. Never commit `.env`; it is listed in `.gitignore`.

## Check that the real API works

```bash
python -m studypilot.smoke            # one plain request
python -m studypilot.smoke --tools    # also checks that tool declarations are accepted
python -m studypilot.smoke --role planner
```

Expected end of output: `OK`. If something is wrong, the message says what to fix
(missing key, unknown model, rejected key, rate limit, network).

## Run the tests

```bash
python -m pytest
```

All tests use a fake SDK client or a mock LLM, so they need no API key and no network.

## Run the agent

```bash
python -m studypilot "Find all deadlines for student S001 and generate a chronological study plan"
```

The agent loop is added in weeks 13-14; until then this reports "Not available yet"
after the configuration is validated.

## Failure handling in the model layer (week 11)

Every failure of a Gemini call is converted into one of our own exceptions
(`src/studypilot/errors.py`), so the agent never depends on SDK internals.

| Situation | Examples | Behaviour |
|---|---|---|
| Transient | HTTP 429 (rate limit), 408, 5xx, timeout, connection error | Retried with exponential backoff and jitter, up to `MAX_RETRIES` retries (total attempts = 1 + `MAX_RETRIES`); then `LLMRetriesExhausted` |
| Permanent | 400 bad request, 401/403 key rejected, 404 unknown model | Not retried; `LLMPermanentError` with a hint about what to fix |
| Invalid response | empty answer, prompt blocked by the API, function call without a name | `LLMInvalidResponse` |
| Configuration | no key, no model name, SDK not installed | `ConfigError` before any request is sent |

Retries and errors are written to the trace (`logs/trace.jsonl`) without API keys.

## Project layout

| Path | Purpose |
|---|---|
| `src/studypilot/config.py` | execution limits, model names, API key from the environment |
| `src/studypilot/errors.py` | exception hierarchy for model failures |
| `src/studypilot/retry.py` | retry with exponential backoff and jitter |
| `src/studypilot/gemini.py` | Gemini client (official `google-genai` SDK) |
| `src/studypilot/llm.py` | LLM client interface and `MockLLM` |
| `src/studypilot/state.py` | explicit agent state, statuses, stop reasons |
| `src/studypilot/tools.py` | read-only tools over mock data, registry, declarations |
| `src/studypilot/agent.py` | agent loop (weeks 13-14) |
| `src/studypilot/trace.py` | JSONL execution trace with secret redaction |
| `src/studypilot/smoke.py` | manual check of the real API |
| `data/` | mock students, courses, deadlines (one course has a prompt-injection test fixture) |
| `tests/` | unit tests (no API key needed) |

Guardrails (permissions, approval gate, limits, injection defense) are added in week 15.
