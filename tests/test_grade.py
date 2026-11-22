import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from harness.grade import all_files_ok, count_assertions, grade

REPO = Path(__file__).resolve().parent.parent
FAKE_DOCKER = REPO / "tests" / "fixtures" / "fake-docker"
WRONG = REPO / "tests" / "fixtures" / "dummy-wrong-solution"
HIDDEN = REPO / "tasks" / "dummy-slide-row" / "hidden-tests"


class GradeWithFakeDockerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.project = self.root / "project"
        shutil.copytree(WRONG, self.project)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LISP_CHECK_", "FAKE_"))}
        env.update(LISP_CHECK_MODE="docker", LISP_CHECK_DOCKER=str(FAKE_DOCKER), FAKE_DOCKER_STDOUT="OK\n")
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_check_that_never_ends_is_a_timeout_failure(self):
        os.environ["FAKE_DOCKER_SLEEP"] = "60"
        start = time.monotonic()

        result = grade(self.project, HIDDEN, self.root / "grading", check_timeout=1)

        self.assertLess(time.monotonic() - start, 40)
        self.assertEqual(set(result["source_files"].values()), {"TIMEOUT"})
        self.assertEqual(result["hidden_tests_passed"], 0)
        self.assertFalse(result["passed"])
        self.assertIn("timed out after 1 s", result["log"])

    def test_docker_warnings_on_stderr_do_not_turn_ok_into_fail(self):
        os.environ["FAKE_DOCKER_STDERR"] = ("WARNING: The requested image's platform (linux/amd64) does not match"
                                            " the detected host platform (linux/arm64/v8)\n")

        result = grade(self.project, HIDDEN, self.root / "grading")

        self.assertEqual(set(result["source_files"].values()), {"OK"})
        self.assertEqual(result["hidden_tests_passed"], result["hidden_tests_total"])
        self.assertTrue(result["passed"])

    def test_ok_with_a_failing_exit_code_is_a_failure(self):
        os.environ["FAKE_DOCKER_EXIT"] = "1"

        result = grade(self.project, HIDDEN, self.root / "grading")

        self.assertEqual(set(result["source_files"].values()), {"FAIL"})
        self.assertEqual(result["hidden_tests_passed"], 0)
        self.assertFalse(result["passed"])

    def test_a_model_file_named_like_a_hidden_test_does_not_replace_or_block_it(self):
        (self.project / "slide-row-hidden-tests.lisp").write_text("(in-package :slide-row)\n")

        result = grade(self.project, HIDDEN, self.root / "grading")

        hidden_total = count_assertions(HIDDEN / "slide-row-hidden-tests.lisp")
        self.assertEqual((result["hidden_tests_passed"], result["hidden_tests_total"]),
                         (hidden_total, hidden_total))
        self.assertEqual(result["source_files"]["slide-row-hidden-tests.lisp"], "OK")
        self.assertEqual((self.project / "slide-row-hidden-tests.lisp").read_text(), "(in-package :slide-row)\n")

    def test_a_required_file_that_does_not_exist_is_missing(self):
        (self.project / "slide-row.lisp").unlink()

        result = grade(self.project, HIDDEN, self.root / "grading",
                       required_files=["slide-row.asd", "slide-row.lisp", "package.lisp"])

        self.assertEqual(result["source_files"]["slide-row.lisp"], "MISSING")
        self.assertEqual(result["source_files"]["package.lisp"], "OK")
        self.assertNotIn("slide-row.asd", result["source_files"])
        self.assertFalse(result["passed"])

    def test_a_missing_required_system_definition_is_missing(self):
        (self.project / "slide-row.asd").unlink()
        required = ["slide-row.asd", "slide-row.lisp", "package.lisp"]

        result = grade(self.project, HIDDEN, self.root / "grading", required_files=required)

        self.assertEqual(result["source_files"]["slide-row.asd"], "MISSING")
        self.assertFalse(result["passed"])
        self.assertFalse(all_files_ok(self.project, self.root / "status-check", required))


if __name__ == "__main__":
    unittest.main()
