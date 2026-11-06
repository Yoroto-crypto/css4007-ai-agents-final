# StudyPilot: setup and run

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then add your GEMINI_API_KEY and model names
```

Never commit `.env`. It must stay in `.gitignore`.

## Run the tests

```bash
python -m pytest            # or: PYTHONPATH=src python -m unittest discover -s tests
```

Tests use a mock LLM and local mock data, so they need no API key.

## Run the agent

```bash
python -m studypilot "Find all deadlines for student S001 and generate a chronological study plan"
```

Until week 14 this prints "Not available yet".

## Project layout

| Path | Purpose |
|---|---|
| `src/studypilot/config.py` | execution limits, model names, API key from environment |
| `src/studypilot/state.py` | explicit agent state, statuses, stop reasons |
| `src/studypilot/tools.py` | read-only tools over mock data and tool registry |
| `src/studypilot/llm.py` | LLM client interface, `MockLLM`, `GeminiClient` (week 11) |
| `src/studypilot/agent.py` | agent loop (weeks 13-14) |
| `src/studypilot/trace.py` | JSONL execution trace with secret redaction |
| `data/` | mock students, courses, deadlines (one course contains a prompt-injection test fixture) |
| `tests/` | unit tests (mock LLM, no API key needed) |

Guardrails (permissions, approval gate, limits, injection defense) are added in week 15.
