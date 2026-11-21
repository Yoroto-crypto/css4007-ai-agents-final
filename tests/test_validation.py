import unittest

from studypilot.dates import is_iso_date
from studypilot.errors import ValidationError
from studypilot.validation import validate_against_schema, validate_tool_args


class TestDates(unittest.TestCase):
    def test_valid_and_invalid_dates(self):
        self.assertTrue(is_iso_date("2026-12-10"))
        for bad in ["2026-02-30", "2026-13-01", "10.12.2026", "20261210", "2026-1-5", "", None, 20261210]:
            self.assertFalse(is_iso_date(bad), bad)


class TestToolArgs(unittest.TestCase):
    def problems(self, tool, args):
        with self.assertRaises(ValidationError) as ctx:
            validate_tool_args(tool, args)
        return ctx.exception.problems

    def test_valid_args_return_copy(self):
        args = {"student_id": "S001"}
        clean = validate_tool_args("get_student_courses", args)
        self.assertEqual(clean, args)
        self.assertIsNot(clean, args)

    def test_optional_parameter_accepted(self):
        validate_tool_args("get_course_deadlines", {"course_id": "AI101", "on_or_after": "2026-12-01"})

    def test_missing_required_parameter(self):
        self.assertIn("args.student_id: required property is missing",
                      self.problems("get_student_courses", {}))

    def test_wrong_type_rejected(self):
        self.assertIn("expected string, got int", self.problems("get_student_courses", {"student_id": 1})[0])

    def test_bad_format_rejected(self):
        self.assertTrue(self.problems("get_course_info", {"course_id": "ai101"}))
        self.assertTrue(self.problems("get_course_info", {"course_id": "AI101; DROP TABLE"}))

    def test_unexpected_property_rejected(self):
        problems = self.problems("get_course_info", {"course_id": "AI101", "path": "/etc/passwd"})
        self.assertTrue(any("unexpected property 'path'" in p for p in problems))

    def test_impossible_and_wrongly_formatted_dates_rejected(self):
        for bad in ["2026-02-30", "10.12.2026", "20261210"]:
            problems = self.problems("get_course_deadlines", {"course_id": "AI101", "on_or_after": bad})
            self.assertTrue(any("YYYY-MM-DD" in p for p in problems), bad)

    def test_args_must_be_an_object(self):
        for bad in [None, [], "S001", 5]:
            self.assertTrue(self.problems("get_student_courses", bad))

    def test_unknown_tool_rejected(self):
        self.assertIn("unknown tool", self.problems("delete_everything", {})[0])
        self.assertIn("unknown tool", self.problems(["x"], {})[0])

    def test_all_problems_are_reported_together(self):
        problems = self.problems("get_course_deadlines", {"course_id": 5, "on_or_after": "nope", "x": 1})
        self.assertEqual(len(problems), 3)


class TestSchemaKeywords(unittest.TestCase):
    def test_numbers_ranges_and_booleans(self):
        schema = {"type": "number", "minimum": 1, "maximum": 5}
        self.assertEqual(validate_against_schema(3, schema), [])
        self.assertTrue(validate_against_schema(0, schema))
        self.assertTrue(validate_against_schema(6, schema))
        self.assertTrue(validate_against_schema(True, schema))  # bool is not a number
        self.assertTrue(validate_against_schema(float("nan"), schema))
        self.assertTrue(validate_against_schema(float("inf"), schema))

    def test_integer_rejects_float(self):
        self.assertTrue(validate_against_schema(1.5, {"type": "integer"}))

    def test_enum_and_string_lengths(self):
        self.assertTrue(validate_against_schema("x", {"type": "string", "enum": ["a", "b"]}))
        self.assertTrue(validate_against_schema("a", {"type": "string", "minLength": 2}))
        self.assertTrue(validate_against_schema("abc", {"type": "string", "maxLength": 2}))

    def test_arrays_and_nested_paths(self):
        schema = {"type": "array", "minItems": 1, "items": {"type": "object",
                  "properties": {"n": {"type": "integer"}}, "required": ["n"]}}
        self.assertTrue(validate_against_schema([], schema))
        problems = validate_against_schema([{"n": 1}, {"n": "x"}], schema, "data")
        self.assertEqual(len(problems), 1)
        self.assertIn("data[1].n", problems[0])


if __name__ == "__main__":
    unittest.main()
