import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import docker_image_available

REPO = Path(__file__).resolve().parent.parent
REGRADE = REPO / "bin" / "regrade"
FIXTURES = REPO / "tests" / "fixtures"
WRONG = FIXTURES / "dummy-wrong-solution"
REFERENCE = REPO / "reference" / "dummy-slide-row"
DUMMY_HIDDEN_ASSERTIONS = 11


class RegradeTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("LISP_CHECK_", "FAKE_"))}

    def tearDown(self):
        self.tmp.cleanup()

    def make_record(self, solution, **recorded):
        record = self.root / "runs" / "dummy-slide-row" / "with-skills" / "3"
        shutil.copytree(solution, record / "src")
        result = {"task": "dummy-slide-row", "setup": "with-skills", "run_number": 3,
                  "hidden_tests_passed": 0, "hidden_tests_total": DUMMY_HIDDEN_ASSERTIONS,
                  "source_files": {}, "passed": False, **recorded}
        (record / "result.json").write_text(json.dumps(result))
        return record

    def regrade(self, record, *args):
        return subprocess.run([str(REGRADE), str(record), *args], env=self.env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)


class RegradeWithFakeDockerTest(RegradeTestCase):
    def setUp(self):
        super().setUp()
        self.env.update(LISP_CHECK_DOCKER=str(FIXTURES / "fake-docker"), FAKE_DOCKER_STDOUT="OK\n")
        self.ok_files = {"package.lisp": "OK", "slide-row-tests.lisp": "OK", "slide-row.lisp": "OK"}

    def test_prints_the_hidden_test_score_and_file_statuses(self):
        record = self.make_record(WRONG, hidden_tests_passed=11, source_files=self.ok_files, passed=True)

        completed = self.regrade(record)

        self.assertIn("hidden tests 11/11", completed.stdout)
        self.assertIn("slide-row.lisp OK", completed.stdout)
        self.assertIn("PASS", completed.stdout)

    def test_exits_0_when_the_regrade_matches_the_record(self):
        record = self.make_record(WRONG, hidden_tests_passed=11, source_files=self.ok_files, passed=True)

        completed = self.regrade(record)

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("matches the record", completed.stdout)

    def test_exits_1_when_the_regrade_differs_from_the_record(self):
        record = self.make_record(WRONG, hidden_tests_passed=4, source_files=self.ok_files)

        completed = self.regrade(record)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("differs from the record", completed.stdout)
        self.assertIn("4/11", completed.stdout)

    def test_says_when_the_run_failed_on_a_limit_although_the_code_passes(self):
        record = self.make_record(WRONG, hidden_tests_passed=11, source_files=self.ok_files,
                                  limit_hit="wall_clock")

        completed = self.regrade(record)

        self.assertIn("run failed anyway: limit hit (wall_clock)", completed.stdout)

    def test_never_changes_the_saved_sources(self):
        record = self.make_record(WRONG)
        before = sorted(p.name for p in (record / "src").rglob("*"))

        self.regrade(record)

        self.assertEqual(sorted(p.name for p in (record / "src").rglob("*")), before)

    def test_grading_timeout_can_be_set(self):
        self.env["FAKE_DOCKER_SLEEP"] = "30"
        record = self.make_record(WRONG)

        completed = self.regrade(record, "--check-timeout", "1")

        self.assertIn("slide-row.lisp TIMEOUT", completed.stdout)

    def test_rejects_a_folder_without_a_result_record(self):
        completed = self.regrade(self.root)

        self.assertEqual(completed.returncode, 2)
        self.assertIn("result.json", completed.stderr)


@unittest.skipUnless(docker_image_available(), "lisp-skills-allegro image not available")
class RegradeWithRealLispCheckTest(RegradeTestCase):
    def test_reference_passes_every_hidden_test(self):
        completed = self.regrade(self.make_record(REFERENCE))

        self.assertIn(f"hidden tests {DUMMY_HIDDEN_ASSERTIONS}/{DUMMY_HIDDEN_ASSERTIONS}", completed.stdout)

    def test_wrong_solution_fails_some_hidden_tests(self):
        completed = self.regrade(self.make_record(WRONG))

        self.assertNotIn(f"hidden tests {DUMMY_HIDDEN_ASSERTIONS}/", completed.stdout)
        self.assertIn("FAIL", completed.stdout)


if __name__ == "__main__":
    unittest.main()
