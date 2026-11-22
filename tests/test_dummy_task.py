import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness.grade import grade
from tests.support import docker_image_available

REPO = Path(__file__).resolve().parent.parent
TASK = REPO / "tasks" / "dummy-slide-row"
REFERENCE = REPO / "reference" / "dummy-slide-row"
WRONG = REPO / "tests" / "fixtures" / "dummy-wrong-solution"


class TaskLayoutTest(unittest.TestCase):
    def test_task_has_spec_and_hidden_tests(self):
        self.assertTrue((TASK / "spec.md").is_file())
        hidden = list((TASK / "hidden-tests").glob("*.lisp"))
        self.assertEqual(len(hidden), 1)


@unittest.skipUnless(docker_image_available(), "lisp-skills-allegro image not available")
class HiddenTestsAgainstSolutionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def grade_copy_of(self, solution):
        source = self.root / "source"
        shutil.copytree(solution, source)
        return grade(source, TASK / "hidden-tests", self.root / "grading")

    def test_reference_passes_every_hidden_test_and_every_file_prints_ok(self):
        result = self.grade_copy_of(REFERENCE)
        self.assertGreater(result["hidden_tests_total"], 0)
        self.assertEqual(result["hidden_tests_passed"], result["hidden_tests_total"])
        self.assertEqual(set(result["source_files"].values()), {"OK"})
        self.assertIn("slide-row-tests.lisp", result["source_files"])
        self.assertTrue(result["passed"])

    def test_solution_without_merging_fails_some_hidden_tests(self):
        result = self.grade_copy_of(WRONG)
        self.assertGreater(result["hidden_tests_passed"], 0)
        self.assertLess(result["hidden_tests_passed"], result["hidden_tests_total"])
        self.assertFalse(result["passed"])

    def test_empty_solution_passes_nothing(self):
        empty = self.root / "empty"
        empty.mkdir()
        result = grade(empty, TASK / "hidden-tests", self.root / "grading")
        self.assertEqual(result["hidden_tests_passed"], 0)
        self.assertGreater(result["hidden_tests_total"], 0)
        self.assertEqual(result["source_files"], {})
        self.assertFalse(result["passed"])

    def test_grading_does_not_touch_the_graded_folder(self):
        source = self.root / "source"
        shutil.copytree(REFERENCE, source)
        before = sorted(p.relative_to(source) for p in source.rglob("*"))
        grade(source, TASK / "hidden-tests", self.root / "grading")
        after = sorted(p.relative_to(source) for p in source.rglob("*"))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
