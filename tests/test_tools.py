import unittest

from studypilot.tools import (
    TOOLS,
    get_course_deadlines,
    get_course_info,
    get_student_courses,
)


class TestTools(unittest.TestCase):
    def test_student_courses_valid(self):
        self.assertEqual(get_student_courses("S001"), ["AI101", "ML201"])

    def test_student_courses_invalid_format_rejected(self):
        for bad in ["", "s001", "S1", "S0011", "AI101", None, 5]:
            self.assertIn("error", get_student_courses(bad))

    def test_unknown_student_returns_error(self):
        self.assertIn("error", get_student_courses("S999"))

    def test_student_without_courses_is_empty_list(self):
        self.assertEqual(get_student_courses("S003"), [])

    def test_course_info_valid(self):
        info = get_course_info("ML201")
        self.assertEqual(info["title"], "Machine Learning")
        self.assertEqual(info["exam_date"], "2026-12-18")

    def test_unknown_course_returns_error(self):
        self.assertEqual(get_course_info("CS999"), {"error": "Course not found"})
        self.assertIn("error", get_course_deadlines("CS999"))

    def test_invalid_course_id_rejected(self):
        self.assertIn("error", get_course_info("ai101"))
        self.assertIn("error", get_course_deadlines("../etc/passwd"))

    def test_deadlines_valid(self):
        deadlines = get_course_deadlines("AI101")
        self.assertEqual([d["date"] for d in deadlines], ["2026-12-10", "2026-12-15"])

    def test_course_without_deadlines_is_empty_list(self):
        self.assertEqual(get_course_deadlines("NET401"), [])

    def test_registry_has_three_read_only_tools(self):
        self.assertEqual(len(TOOLS), 3)
        self.assertTrue(all(spec.read_only for spec in TOOLS.values()))
        for spec in TOOLS.values():
            self.assertIn("required", spec.parameters)

    def test_injection_fixture_is_present_as_data(self):
        # The agent must later treat this text as untrusted data (week 15 guardrail test).
        self.assertIn("Ignore all previous instructions", get_course_info("DB301")["description"])


if __name__ == "__main__":
    unittest.main()
