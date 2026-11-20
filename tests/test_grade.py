import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from harness.grade import grade

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

    def test_a_required_file_that_does_not_exist_is_missing(self):
        (self.project / "slide-row.lisp").unlink()

        result = grade(self.project, HIDDEN, self.root / "grading",
                       required_files=["slide-row.asd", "slide-row.lisp", "package.lisp"])

        self.assertEqual(result["source_files"]["slide-row.lisp"], "MISSING")
        self.assertEqual(result["source_files"]["package.lisp"], "OK")
        self.assertNotIn("slide-row.asd", result["source_files"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
