import unittest

from studypilot.executor import execute_tool
from studypilot.tools import ToolSpec
from studypilot.trace import Trace

FAKE_KEY = "AIza" + "C" * 35


def spy_registry(behaviour="ok"):
    calls = []

    def func(student_id):
        calls.append(student_id)
        if behaviour == "raise":
            raise RuntimeError("database offline")
        if behaviour == "error":
            return {"error": "not available"}
        return ["X1"]

    spec = ToolSpec(
        name="spy",
        func=func,
        description="spy",
        parameters={
            "type": "object",
            "properties": {"student_id": {"type": "string", "pattern": r"^S\d{3}$"}},
            "required": ["student_id"],
        },
    )
    return {"spy": spec}, calls


class TestExecutor(unittest.TestCase):
    def test_valid_call_returns_data_and_logs_validated_args(self):
        trace = Trace()
        result = execute_tool("get_student_courses", {"student_id": "S001"}, trace=trace)
        self.assertTrue(result.ok)
        self.assertEqual(result.data, ["AI101", "ML201"])
        events = [e["event"] for e in trace.events]
        self.assertEqual(events, ["tool_call", "tool_result"])
        self.assertEqual(trace.events[0]["args"], {"student_id": "S001"})

    def test_malformed_arguments_never_reach_the_tool(self):
        registry, calls = spy_registry()
        for bad in [{"student_id": "bad"}, {}, {"student_id": "S001", "extra": 1}, None]:
            result = execute_tool("spy", bad, registry=registry)
            self.assertTrue(result.rejected)
            self.assertFalse(result.ok)
        self.assertEqual(calls, [])

    def test_valid_call_does_reach_the_tool(self):
        registry, calls = spy_registry()
        self.assertTrue(execute_tool("spy", {"student_id": "S001"}, registry=registry).ok)
        self.assertEqual(calls, ["S001"])

    def test_unknown_tool_is_rejected(self):
        result = execute_tool("rm_rf", {"path": "/"})
        self.assertTrue(result.rejected)
        self.assertIn("unknown tool", result.error)

    def test_rejection_is_traced_with_problems(self):
        trace = Trace()
        execute_tool("get_course_info", {"course_id": "nope"}, trace=trace)
        self.assertEqual(trace.events[0]["event"], "tool_rejected")
        self.assertTrue(trace.events[0]["problems"])

    def test_tool_level_error_is_not_a_rejection(self):
        result = execute_tool("get_student_courses", {"student_id": "S999"})
        self.assertFalse(result.ok)
        self.assertFalse(result.rejected)
        self.assertIn("not found", result.error.lower())

    def test_tool_returning_error_dict_is_a_failed_result(self):
        registry, _ = spy_registry("error")
        result = execute_tool("spy", {"student_id": "S001"}, registry=registry)
        self.assertEqual((result.ok, result.error), (False, "not available"))

    def test_tool_exception_is_contained(self):
        trace = Trace()
        registry, _ = spy_registry("raise")
        result = execute_tool("spy", {"student_id": "S001"}, registry=registry, trace=trace)
        self.assertFalse(result.ok)
        self.assertIn("database offline", result.error)
        self.assertEqual(trace.events[-1]["event"], "tool_error")

    def test_date_filter_through_executor(self):
        result = execute_tool("get_course_deadlines", {"course_id": "AI101", "on_or_after": "2026-12-12"})
        self.assertEqual([d["date"] for d in result.data], ["2026-12-15"])
        everything = execute_tool("get_course_deadlines", {"course_id": "AI101"})
        self.assertEqual(len(everything.data), 2)

    def test_secrets_in_rejected_arguments_are_redacted_in_trace(self):
        trace = Trace()
        execute_tool("get_course_info", {"course_id": FAKE_KEY}, trace=trace)
        self.assertNotIn(FAKE_KEY, str(trace.events))


if __name__ == "__main__":
    unittest.main()
