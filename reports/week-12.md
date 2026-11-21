## Week 12 Progress Report

## Completed Work

- Implemented input and tool-argument validation (`validation.py`): required parameters, types, ID formats, allowed values, real calendar dates, numeric ranges, and rejection of unexpected parameters. All problems of a call are reported together.
- Added a validated tool executor (`executor.py`): a proposed tool call is validated first, and a malformed call never reaches the tool. Tool-level failures (item not found) and tool exceptions are returned as results instead of crashing the program. Validated arguments, rejections, results, and errors are written to the trace.
- Extended `get_course_deadlines` with an optional `on_or_after` date, so that date validation is exercised on a real tool parameter.
- Defined a structured study-plan format (`plan.py`) and a validator for generated output: valid JSON (a Markdown fence is tolerated), required fields, task kinds, ID formats, real dates, hours per task, at most 12 hours per day, and chronological order. Invalid output is rejected with a list of problems.
- Added a JSON output mode to the Gemini client (`json_schema`) and a manual check `python -m studypilot.smoke --plan`, which asks the model for a plan and validates it.
- Added `collect_deadlines`, which merges per-course deadlines chronologically; it will be used in later weeks to verify that a plan covers all retrieved deadlines.
- Added 47 new tests (103 in total), including malformed arguments, unknown tools, bad dates, invalid model output, and a test that a rejected call never executes the tool.

## Important Commits

- Commit hash: 6e13e246ed558d97fd682670e07fa8069bb54eb8
- Description: Add schema validation for tool arguments and generated output
- Link: https://github.com/Yoroto-crypto/css4007-ai-agents-final/commit/6e13e246ed558d97fd682670e07fa8069bb54eb8

- Commit hash: 06f362aacf2cf246dda3679ecb360d5d2fd4cfad
- Description: Add validated tool executor and structured plan format
- Link: https://github.com/Yoroto-crypto/css4007-ai-agents-final/commit/06f362aacf2cf246dda3679ecb360d5d2fd4cfad

- Commit hash: 798ec137a40dfbea23b8febbd178ce21bcbf1a16
- Description: Add JSON output mode, plan smoke check, tests, and docs
- Link: https://github.com/Yoroto-crypto/css4007-ai-agents-final/commit/798ec137a40dfbea23b8febbd178ce21bcbf1a16

## Current Functionality

- Tool calls are validated before execution; invalid calls are rejected with specific problems and logged.
- The model can be asked for a study plan as JSON, and its output is validated before it is accepted.
- The three read-only tools work through the executor and trace every call.
- The agent loop is not implemented yet (weeks 13-14): the model does not yet choose tools in a loop, and tool results are not returned to it.

## Problems Encountered

- The Gemini schema format supports fewer JSON-schema keywords than I need for validation (for example `pattern`, `format`, `minimum`, `maximum`).
- A first version of the schema cleaner would also have removed a property that happens to be named like a keyword.
- Deciding whether plan checks belong to validation or to output verification.

## Solutions

- Keep the full constraints in my own schemas and enforce them in application code; send only the simplified schema to Gemini.
- The cleaner now removes only schema keywords and never touches property names (covered by a test).
- Validation here checks structure, ranges, and internal consistency of the plan; comparing the plan with the data actually retrieved (output verification) is planned for weeks 15-16.

## What I Learned

- Model output and model-proposed tool arguments are untrusted input and must be validated in code before anything is executed or accepted.
- Reporting all problems at once makes it possible to ask the model to correct a call or an output in one step.
- Rejecting unexpected parameters is as important as checking the expected ones.
- Constraints enforced in my code are more reliable than constraints that only appear in a prompt or an API schema.

## Next Week

- Register the tools with Gemini through function calling and let the model choose the next tool.
- Return tool results to the model (tool-result messages) and build the first multi-step loop with the execution limits.
- Define the tool permission policy and add tests for correct tool sequencing.
