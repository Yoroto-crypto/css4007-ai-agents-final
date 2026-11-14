import os
import unittest
from types import SimpleNamespace
from unittest import mock

from studypilot.config import AgentConfig
from studypilot.errors import (
    ConfigError,
    LLMInvalidResponse,
    LLMPermanentError,
    LLMRetriesExhausted,
)
from studypilot.gemini import (
    GeminiClient,
    classify_error,
    to_contents,
    to_function_declarations,
)
from studypilot.tools import declarations
from studypilot.trace import Trace

FAKE_KEY = "AIza" + "B" * 35


class FakeAPIError(Exception):
    """Mimics google.genai.errors.APIError, which carries an integer `code`."""

    def __init__(self, code, message="boom"):
        super().__init__(message)
        self.code = code


def ok_response(text="ready", tokens=12, calls=None):
    return SimpleNamespace(
        text=text,
        function_calls=calls,
        usage_metadata=SimpleNamespace(total_token_count=tokens),
        prompt_feedback=None,
    )


class FakeSDK:
    """Stands in for genai.Client: scripted outcomes (responses or exceptions)."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []
        self.models = self  # client.models.generate_content(...)

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def make_client(outcomes, max_retries=2, trace=None):
    sdk = FakeSDK(outcomes)
    sleeps = []
    cfg = AgentConfig(max_retries=max_retries, model_fast="fast-model", model_planner="planner-model")
    client = GeminiClient(cfg, client=sdk, trace=trace, sleep=sleeps.append)
    return client, sdk, sleeps


USER = [{"role": "user", "content": "hi"}]


class TestGeminiClient(unittest.TestCase):
    def test_text_response_and_request_shape(self):
        client, sdk, _ = make_client([ok_response("ready", 12)])
        reply = client.generate(
            [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}], tools=[]
        )
        self.assertEqual((reply.text, reply.tokens_used, reply.tool_calls), ("ready", 12, []))
        req = sdk.requests[0]
        self.assertEqual(req["model"], "fast-model")
        self.assertEqual(req["config"]["system_instruction"], "be brief")
        self.assertEqual(req["contents"], [{"role": "user", "parts": [{"text": "hi"}]}])
        self.assertNotIn("tools", req["config"])

    def test_function_call_is_parsed(self):
        call = SimpleNamespace(name="get_student_courses", args={"student_id": "S001"})
        client, sdk, _ = make_client([ok_response(text=None, calls=[call])])
        reply = client.generate(USER, tools=declarations())
        self.assertEqual(reply.tool_calls[0].name, "get_student_courses")
        self.assertEqual(reply.tool_calls[0].args, {"student_id": "S001"})
        self.assertEqual(len(sdk.requests[0]["config"]["tools"][0]["function_declarations"]), 3)

    def test_transient_server_error_is_retried_and_traced(self):
        trace = Trace()
        client, sdk, sleeps = make_client([FakeAPIError(503), ok_response()], trace=trace)
        reply = client.generate(USER, tools=[])
        self.assertEqual(reply.text, "ready")
        self.assertEqual(len(sdk.requests), 2)
        self.assertEqual(len(sleeps), 1)
        events = [e["event"] for e in trace.events]
        self.assertEqual(events, ["llm_request", "llm_retry", "llm_response"])

    def test_rate_limit_429_is_retried(self):
        client, sdk, _ = make_client([FakeAPIError(429), FakeAPIError(429), ok_response()])
        self.assertEqual(client.generate(USER, tools=[]).text, "ready")
        self.assertEqual(len(sdk.requests), 3)

    def test_connection_and_timeout_errors_are_retried(self):
        client, sdk, _ = make_client([ConnectionError("reset"), TimeoutError("slow"), ok_response()])
        self.assertEqual(client.generate(USER, tools=[]).text, "ready")
        self.assertEqual(len(sdk.requests), 3)

    def test_retries_exhausted_respects_max_retries(self):
        client, sdk, sleeps = make_client([FakeAPIError(500)] * 5, max_retries=2)
        with self.assertRaises(LLMRetriesExhausted):
            client.generate(USER, tools=[])
        self.assertEqual(len(sdk.requests), 3)
        self.assertEqual(len(sleeps), 2)

    def test_auth_error_is_permanent_and_not_retried(self):
        client, sdk, sleeps = make_client([FakeAPIError(401), ok_response()])
        with self.assertRaises(LLMPermanentError) as ctx:
            client.generate(USER, tools=[])
        self.assertEqual(len(sdk.requests), 1)
        self.assertEqual(sleeps, [])
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    def test_unknown_model_error_has_helpful_hint(self):
        client, _, _ = make_client([FakeAPIError(404)])
        with self.assertRaises(LLMPermanentError) as ctx:
            client.generate(USER, tools=[])
        self.assertIn("GEMINI_MODEL", str(ctx.exception))

    def test_empty_response_is_invalid(self):
        client, _, _ = make_client([ok_response(text="")])
        with self.assertRaises(LLMInvalidResponse):
            client.generate(USER, tools=[])

    def test_response_without_text_attribute_is_invalid(self):
        class NoText:
            function_calls = None
            usage_metadata = None
            prompt_feedback = None

            @property
            def text(self):
                raise ValueError("no text part")

        client, _, _ = make_client([NoText()])
        with self.assertRaises(LLMInvalidResponse):
            client.generate(USER, tools=[])

    def test_blocked_prompt_reports_reason(self):
        blocked = SimpleNamespace(
            text=None, function_calls=None, usage_metadata=None,
            prompt_feedback=SimpleNamespace(block_reason="SAFETY"),
        )
        client, _, _ = make_client([blocked])
        with self.assertRaises(LLMInvalidResponse) as ctx:
            client.generate(USER, tools=[])
        self.assertIn("SAFETY", str(ctx.exception))

    def test_function_call_without_name_is_invalid(self):
        bad = SimpleNamespace(name="", args={})
        client, _, _ = make_client([ok_response(text=None, calls=[bad])])
        with self.assertRaises(LLMInvalidResponse):
            client.generate(USER, tools=[])

    def test_api_key_in_error_message_never_reaches_trace(self):
        trace = Trace()
        client, _, _ = make_client([FakeAPIError(401, f"bad key {FAKE_KEY}")], trace=trace)
        with self.assertRaises(LLMPermanentError) as ctx:
            client.generate(USER, tools=[])
        self.assertNotIn(FAKE_KEY, str(ctx.exception))
        self.assertNotIn(FAKE_KEY, str(trace.events))

    def test_missing_model_raises_config_error(self):
        with self.assertRaises(ConfigError):
            GeminiClient(AgentConfig(), client=FakeSDK([]))

    def test_planner_model_can_be_selected(self):
        sdk = FakeSDK([ok_response()])
        cfg = AgentConfig(model_fast="f", model_planner="p")
        GeminiClient(cfg, model=cfg.model_planner, client=sdk).generate(USER, tools=[])
        self.assertEqual(sdk.requests[0]["model"], "p")

    def test_creating_real_client_without_key_raises_config_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigError):
                GeminiClient(AgentConfig(model_fast="m"))


class TestTextExtraction(unittest.TestCase):
    def response_with_parts(self, parts, calls=None):
        class Resp:
            function_calls = calls
            usage_metadata = SimpleNamespace(total_token_count=5)
            prompt_feedback = None
            candidates = [SimpleNamespace(content=SimpleNamespace(parts=parts))]

            @property
            def text(self):  # must not be touched when parts are available
                raise AssertionError("response.text should not be read")

        return Resp()

    def test_text_and_function_call_parts_without_reading_response_text(self):
        call = SimpleNamespace(name="get_course_info", args={"course_id": "AI101"})
        parts = [SimpleNamespace(text="Checking the course.", thought=False),
                 SimpleNamespace(text=None, function_call=call)]
        client, _, _ = make_client([self.response_with_parts(parts, calls=[call])])
        reply = client.generate(USER, tools=declarations())
        self.assertEqual(reply.text, "Checking the course.")
        self.assertEqual(reply.tool_calls[0].name, "get_course_info")

    def test_thought_parts_are_excluded(self):
        parts = [SimpleNamespace(text="internal reasoning", thought=True),
                 SimpleNamespace(text="Final answer", thought=False)]
        client, _, _ = make_client([self.response_with_parts(parts)])
        self.assertEqual(client.generate(USER, tools=[]).text, "Final answer")

    def test_only_function_call_means_empty_text_but_valid_response(self):
        call = SimpleNamespace(name="get_student_courses", args={"student_id": "S001"})
        parts = [SimpleNamespace(text=None, function_call=call)]
        client, _, _ = make_client([self.response_with_parts(parts, calls=[call])])
        reply = client.generate(USER, tools=declarations())
        self.assertEqual(reply.text, "")
        self.assertEqual(len(reply.tool_calls), 1)


class TestHelpers(unittest.TestCase):
    def test_messages_mapping(self):
        system, contents = to_contents([
            {"role": "system", "content": "A"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a"},
        ])
        self.assertEqual(system, "A")
        self.assertEqual([c["role"] for c in contents], ["user", "model"])

    def test_invalid_messages_rejected(self):
        for bad in ([], [{"role": "system", "content": "only system"}],
                    [{"role": "robot", "content": "x"}], [{"role": "user", "content": 5}]):
            with self.assertRaises(ValueError):
                to_contents(bad)

    def test_declarations_drop_pattern_but_keep_required(self):
        decl = to_function_declarations(declarations())[0]
        self.assertNotIn("pattern", str(decl))
        self.assertIn("required", decl["parameters"])
        # our own copy used for validation still has the pattern
        self.assertIn("pattern", str(declarations()[0]))

    def test_classify_error_categories(self):
        self.assertEqual(type(classify_error(FakeAPIError(503))).__name__, "LLMTransientError")
        self.assertEqual(type(classify_error(FakeAPIError(400))).__name__, "LLMPermanentError")
        self.assertEqual(type(classify_error(ValueError("?"))).__name__, "LLMPermanentError")
        self.assertEqual(type(classify_error(TimeoutError())).__name__, "LLMTransientError")


if __name__ == "__main__":
    unittest.main()
