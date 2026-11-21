import copy
import json
import unittest

from studypilot.errors import ValidationError
from studypilot.plan import MAX_HOURS_PER_DAY, PLAN_SCHEMA, collect_deadlines, parse_plan

VALID = {
    "student_id": "S001",
    "tasks": [
        {"date": "2026-12-08", "course_id": "AI101", "task": "Prepare agents lab report", "hours": 3, "kind": "assignment"},
        {"date": "2026-12-10", "course_id": "AI101", "task": "Submit agents lab report", "hours": 1.5, "kind": "assignment"},
        {"date": "2026-12-14", "course_id": "AI101", "task": "Final exam revision", "hours": 4, "kind": "exam_prep"},
    ],
    "notes": "Start with the earliest deadline.",
}


def variant(**changes):
    data = copy.deepcopy(VALID)
    data.update(changes)
    return data


def task_variant(index=0, **changes):
    data = copy.deepcopy(VALID)
    data["tasks"][index].update(changes)
    return data


class TestParsePlan(unittest.TestCase):
    def rejected(self, output):
        with self.assertRaises(ValidationError) as ctx:
            parse_plan(output)
        return ctx.exception.problems

    def test_valid_plan_from_dict_json_and_fenced_json(self):
        for source in (VALID, json.dumps(VALID), "```json\n" + json.dumps(VALID) + "\n```"):
            plan = parse_plan(source)
            self.assertEqual(plan.student_id, "S001")
            self.assertEqual(len(plan.tasks), 3)
        self.assertEqual(plan.total_hours(), 8.5)
        self.assertEqual(plan.to_dict()["tasks"][0]["course_id"], "AI101")

    def test_invalid_json_is_rejected(self):
        self.assertIn("not valid JSON", self.rejected("Sure! Here is your plan: ...")[0])
        self.assertIn("not valid JSON", self.rejected('{"student_id": "S001",')[0])

    def test_wrong_top_level_type(self):
        self.assertTrue(self.rejected("[1, 2, 3]"))

    def test_missing_required_fields(self):
        data = copy.deepcopy(VALID)
        del data["student_id"]
        del data["tasks"][0]["hours"]
        problems = self.rejected(data)
        self.assertEqual(len(problems), 2)

    def test_bad_student_and_course_ids(self):
        self.assertTrue(self.rejected(variant(student_id="student-1")))
        self.assertTrue(self.rejected(task_variant(course_id="ai101")))

    def test_bad_dates(self):
        for bad in ["2026-13-01", "2026-02-30", "next Friday", "12/10/2026"]:
            self.assertTrue(self.rejected(task_variant(date=bad)), bad)

    def test_hours_must_be_number_in_range(self):
        for bad in [0, 0.1, 13, -2, "3", True, None]:
            self.assertTrue(self.rejected(task_variant(hours=bad)), repr(bad))

    def test_kind_must_be_allowed_value(self):
        self.assertTrue(self.rejected(task_variant(kind="party")))

    def test_empty_task_list_and_short_task_text(self):
        self.assertTrue(self.rejected(variant(tasks=[])))
        self.assertTrue(self.rejected(task_variant(task="x")))

    def test_unexpected_properties_rejected(self):
        self.assertTrue(self.rejected(variant(admin=True)))
        self.assertTrue(self.rejected(task_variant(command="rm -rf")))

    def test_chronological_order_required(self):
        data = copy.deepcopy(VALID)
        data["tasks"].reverse()
        problems = self.rejected(data)
        self.assertTrue(any("chronological" in p for p in problems))

    def test_daily_hour_limit(self):
        data = copy.deepcopy(VALID)
        data["tasks"] = [dict(data["tasks"][0], hours=MAX_HOURS_PER_DAY), dict(data["tasks"][0], hours=2)]
        problems = self.rejected(data)
        self.assertTrue(any("daily limit" in p for p in problems))

    def test_schema_is_the_single_source_of_truth_for_kinds(self):
        kinds = PLAN_SCHEMA["properties"]["tasks"]["items"]["properties"]["kind"]["enum"]
        self.assertIn("exam_prep", kinds)


class TestCollectDeadlines(unittest.TestCase):
    def test_merged_and_sorted_by_date(self):
        merged = collect_deadlines({
            "ML201": [{"date": "2026-12-12", "title": "Assignment", "weight": 0.25}],
            "AI101": [{"date": "2026-12-10", "title": "Lab", "weight": 0.2},
                      {"date": "2026-12-15", "title": "Exam", "weight": 0.5}],
        })
        self.assertEqual([(d["date"], d["course_id"]) for d in merged],
                         [("2026-12-10", "AI101"), ("2026-12-12", "ML201"), ("2026-12-15", "AI101")])

    def test_empty_and_invalid_entries_are_skipped(self):
        merged = collect_deadlines({"NET401": [], "AI101": [{"date": "soon"}, "junk", {"date": "2026-12-10"}]})
        self.assertEqual(len(merged), 1)


if __name__ == "__main__":
    unittest.main()
