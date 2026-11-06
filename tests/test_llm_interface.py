import unittest

from studypilot.llm import LLMResponse, MockLLM, ToolCall


class TestMockLLM(unittest.TestCase):
    def test_returns_scripted_responses_in_order_and_records_calls(self):
        llm = MockLLM([
            LLMResponse(tool_calls=[ToolCall("get_student_courses", {"student_id": "S001"})]),
            LLMResponse(text="done"),
        ])
        first = llm.generate([{"role": "user", "content": "hi"}], tools=[])
        second = llm.generate([], tools=[])
        self.assertEqual(first.tool_calls[0].name, "get_student_courses")
        self.assertEqual(second.text, "done")
        self.assertEqual(len(llm.calls), 2)

    def test_raises_when_script_is_exhausted(self):
        with self.assertRaises(RuntimeError):
            MockLLM([]).generate([], tools=[])


if __name__ == "__main__":
    unittest.main()
