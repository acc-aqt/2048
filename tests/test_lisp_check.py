import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import docker_image_available

REPO = Path(__file__).resolve().parent.parent
LISP_CHECK = REPO / "bin" / "lisp-check"
FAKE_DOCKER = REPO / "tests" / "fixtures" / "fake-docker"


class FakeDockerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name).resolve()
        self.args_file = self.run_dir / "docker-args.json"
        self.env = {
            k: v for k, v in os.environ.items() if not k.startswith("LISP_CHECK_")
        }
        self.env.update(
            LISP_CHECK_MODE="docker",
            LISP_CHECK_DOCKER=str(FAKE_DOCKER),
            FAKE_DOCKER_ARGS=str(self.args_file),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_wrapper(self, *args, **fake):
        env = dict(self.env)
        for key, value in fake.items():
            env["FAKE_DOCKER_" + key.upper()] = str(value)
        return subprocess.run(
            [str(LISP_CHECK), *args],
            cwd=self.run_dir,
            env=env,
            capture_output=True,
            text=True,
        )

    def docker_args(self):
        return json.loads(self.args_file.read_text())

    def test_passes_upstream_output_and_exit_code_through(self):
        for out, code in [
            ("OK\n", 0),
            ("a.lisp:1: read: form starting here is never closed\nFAIL\n", 1),
            ("lisp-check: a.lisp: no such file\nFAIL\n", 2),
        ]:
            with self.subTest(code=code):
                result = self.run_wrapper("a.lisp", stdout=out, exit=code)
                self.assertEqual(result.stdout, out)
                self.assertEqual(result.returncode, code)

    def test_docker_failure_becomes_tool_error(self):
        for code in (125, 126, 127):
            with self.subTest(code=code):
                result = self.run_wrapper(
                    "a.lisp",
                    stderr="docker: Cannot connect to the Docker daemon\n",
                    exit=code,
                )
                lines = result.stdout.splitlines()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(lines[-1], "FAIL")
                self.assertTrue(lines[0].startswith("lisp-check: "))
                self.assertIn("Cannot connect to the Docker daemon", result.stdout)

    def test_logs_one_line_per_invocation_in_the_run_folder(self):
        self.run_wrapper("a.lisp", stdout="OK\n", exit=0)
        self.run_wrapper("--test", "a-tests.lisp", stdout="FAIL\n", exit=1)
        self.run_wrapper("a.lisp", exit=125)

        lines = (self.run_dir / ".lisp-check.log").read_text().splitlines()
        self.assertEqual(len(lines), 3)
        fields = [line.split("\t") for line in lines]
        self.assertEqual([f[1] for f in fields], ["0", "1", "2"])
        self.assertEqual(fields[1][2:], ["--test", "a-tests.lisp"])

    def test_log_location_can_be_overridden(self):
        log = self.run_dir / "elsewhere" / "rounds.log"
        log.parent.mkdir()
        self.env["LISP_CHECK_LOG"] = str(log)
        self.run_wrapper("a.lisp", stdout="OK\n")
        self.assertEqual(len(log.read_text().splitlines()), 1)
        self.assertFalse((self.run_dir / ".lisp-check.log").exists())

    def test_docker_is_the_default_mode(self):
        del self.env["LISP_CHECK_MODE"]
        result = self.run_wrapper("a.lisp", stdout="OK\n")
        self.assertEqual(result.stdout, "OK\n")
        self.assertTrue(self.args_file.exists())

    def test_unsupported_mode_is_a_tool_error_without_running_docker(self):
        for mode in ("native", "bogus"):
            with self.subTest(mode=mode):
                self.env["LISP_CHECK_MODE"] = mode
                result = self.run_wrapper("a.lisp", stdout="OK\n")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout.splitlines()[-1], "FAIL")
                self.assertIn(mode, result.stdout)
                self.assertFalse(self.args_file.exists())

    def test_missing_docker_binary_becomes_tool_error(self):
        self.env["LISP_CHECK_DOCKER"] = str(self.run_dir / "no-such-docker")
        result = self.run_wrapper("a.lisp")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.splitlines()[-1], "FAIL")
        self.assertTrue(result.stdout.startswith("lisp-check: "))


@unittest.skipUnless(docker_image_available(), "lisp-skills-allegro image not available")
class RealDockerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name).resolve()
        (self.run_dir / ".git").mkdir()
        self.env = {
            k: v for k, v in os.environ.items() if not k.startswith("LISP_CHECK_")
        }

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.run_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run_wrapper(self, *args, cwd=None):
        return subprocess.run(
            [str(LISP_CHECK), *args],
            cwd=cwd or self.run_dir,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def test_correct_file_prints_ok(self):
        self.write("ok.lisp", "(defun add1 (x) (+ x 1))\n")
        result = self.run_wrapper("ok.lisp")
        self.assertEqual((result.stdout, result.returncode), ("OK\n", 0))

    def test_broken_file_prints_upstream_problem_and_fail(self):
        self.write("broken.lisp", "(defun add1 (x) (+ x 1)\n")
        result = self.run_wrapper("broken.lisp")
        self.assertEqual(
            result.stdout,
            "broken.lisp:1: read: form starting here is never closed"
            " (missing ')', '\"' or '|#')\nFAIL\n",
        )
        self.assertEqual(result.returncode, 1)

    def test_test_mode_runs_tester_assertions(self):
        self.write(
            "t.lisp",
            "(eval-when (:compile-toplevel :load-toplevel :execute)\n"
            "  (require :tester))\n"
            "(defun add1 (x) (+ x 1))\n"
            "(util.test:test 3 (add1 2))\n",
        )
        passing = self.run_wrapper("--test", "t.lisp")
        self.assertEqual((passing.stdout, passing.returncode), ("OK\n", 0))

        self.write(
            "t.lisp",
            "(eval-when (:compile-toplevel :load-toplevel :execute)\n"
            "  (require :tester))\n"
            "(defun add1 (x) (+ x 1))\n"
            "(util.test:test 4 (add1 2))\n",
        )
        failing = self.run_wrapper("--test", "t.lisp")
        self.assertEqual(failing.returncode, 1)
        self.assertIn("t.lisp:?: test: 1 of 1 assertions failed", failing.stdout)
        self.assertEqual(failing.stdout.splitlines()[-1], "FAIL")

    def test_missing_file_keeps_upstream_tool_error(self):
        result = self.run_wrapper("nofile.lisp")
        self.assertEqual(
            (result.stdout, result.returncode),
            ("lisp-check: nofile.lisp: no such file\nFAIL\n", 2),
        )

    def test_works_from_a_subfolder_of_the_run_folder(self):
        self.write("src/ok.lisp", "(defun add1 (x) (+ x 1))\n")
        result = self.run_wrapper("ok.lisp", cwd=self.run_dir / "src")
        self.assertEqual((result.stdout, result.returncode), ("OK\n", 0))

    def test_works_through_a_symlink_on_path(self):
        bin_dir = self.run_dir / "bin"
        bin_dir.mkdir()
        (bin_dir / "lisp-check").symlink_to(LISP_CHECK)
        self.env["PATH"] = f"{bin_dir}{os.pathsep}{self.env['PATH']}"
        self.write("ok.lisp", "(defun add1 (x) (+ x 1))\n")
        result = subprocess.run(
            ["lisp-check", "ok.lisp"],
            cwd=self.run_dir,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual((result.stdout, result.returncode), ("OK\n", 0))


if __name__ == "__main__":
    unittest.main()
