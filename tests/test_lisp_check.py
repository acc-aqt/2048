import contextlib
import io
import json
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from harness import lisp_check

REPO = Path(__file__).resolve().parent.parent
LISP_CHECK = REPO / "bin" / "lisp-check"
FAKE_DOCKER = REPO / "tests" / "fixtures" / "fake-docker"
FAKE_ALISP = REPO / "tests" / "fixtures" / "fake-alisp"


def wait_for(condition, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.2)
    return False


def process_gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def terminate_like_the_runner(command, cwd, env, started, sig=signal.SIGTERM):
    """Start the wrapper in its own process group, wait for STARTED(), then signal that group."""
    wrapper = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    try:
        if not wait_for(started, 60):
            raise AssertionError("the check never started")
        os.killpg(wrapper.pid, sig)
        return wrapper.wait(timeout=60)
    finally:
        if wrapper.poll() is None:
            wrapper.kill()
            wrapper.wait()


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

    def test_timeout_kills_the_container_and_is_a_tool_error(self):
        kills = self.run_dir / "kills.jsonl"
        self.env["LISP_CHECK_TIMEOUT"] = "1"
        start = time.monotonic()

        result = self.run_wrapper("a.lisp", stdout="OK\n", sleep=60, kills=kills)

        self.assertLess(time.monotonic() - start, 30)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "lisp-check: timed out after 1 s\nFAIL\n")
        args = self.docker_args()
        name = args[args.index("--name") + 1]
        (kill,) = [json.loads(line) for line in kills.read_text().splitlines()]
        self.assertEqual(kill, ["kill", name])

    def test_killed_wrapper_kills_its_docker_client_and_container(self):
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            with self.subTest(sig=sig):
                kills, pid_file = self.run_dir / f"kills-{sig}.jsonl", self.run_dir / f"pid-{sig}"
                env = dict(self.env, FAKE_DOCKER_SLEEP="60", FAKE_DOCKER_KILLS=str(kills),
                           FAKE_DOCKER_PID=str(pid_file))

                terminate_like_the_runner([str(LISP_CHECK), "a.lisp"], self.run_dir, env,
                                          pid_file.exists, sig)

                self.assertTrue(wait_for(lambda: process_gone(int(pid_file.read_text())), 10))
                args = self.docker_args()
                name = args[args.index("--name") + 1]
                self.assertIn(["kill", name], [json.loads(line) for line in kills.read_text().splitlines()])

    def test_no_timeout_unless_set(self):
        result = self.run_wrapper("a.lisp", stdout="OK\n", sleep=2)
        self.assertEqual(result.stdout, "OK\n")

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
        for mode in ("bogus",):
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


class FakeNativeLispTest(unittest.TestCase):
    """Native mode runs the real upstream lisp-check script with a fake Lisp binary."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name).resolve()
        (self.run_dir / "a.lisp").write_text("(defun add1 (x) (+ x 1))\n")
        self.args_file = self.run_dir / "alisp-args.json"
        self.env = {
            k: v for k, v in os.environ.items() if not k.startswith("LISP_CHECK_")
        }
        self.env.update(
            LISP_CHECK_MODE="native",
            LISP_BIN=str(FAKE_ALISP),
            LISP_CHECK_DOCKER=str(self.run_dir / "no-such-docker"),
            FAKE_ALISP_ARGS=str(self.args_file),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_wrapper(self, *args, stdin_text=None, **fake):
        env = dict(self.env)
        for key, value in fake.items():
            env["FAKE_ALISP_" + key.upper()] = str(value)
        return subprocess.run(
            [str(LISP_CHECK), *args],
            cwd=self.run_dir,
            env=env,
            input=stdin_text,
            capture_output=True,
            text=True,
        )

    def alisp_call(self):
        return json.loads(self.args_file.read_text())

    def test_passes_lisp_output_and_exit_code_through(self):
        for out, code in [
            ("OK\n", 0),
            ("a.lisp:1: compile: style-warning: Variable X is never used.\nFAIL\n", 1),
        ]:
            with self.subTest(code=code):
                result = self.run_wrapper("a.lisp", stdout=out, exit=code)
                self.assertEqual((result.stdout, result.returncode), (out, code))

    def test_passes_test_flag_and_file_to_lisp_without_running_docker(self):
        result = self.run_wrapper("--test", "a.lisp", stdout="OK\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        args = self.alisp_call()["args"]
        self.assertEqual(args[-3:], ["--", "a.lisp", "--test"])

    def test_timeout_kills_lisp_and_is_a_tool_error(self):
        self.env["LISP_CHECK_TIMEOUT"] = "1"
        start = time.monotonic()

        result = self.run_wrapper("a.lisp", stdout="OK\n", sleep=60)

        self.assertLess(time.monotonic() - start, 30)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "lisp-check: timed out after 1 s\nFAIL\n")
        with self.assertRaises(ProcessLookupError):
            os.kill(self.alisp_call()["pid"], 0)

    def test_killed_wrapper_kills_lisp(self):
        terminate_like_the_runner([str(LISP_CHECK), "a.lisp"], self.run_dir,
                                  dict(self.env, FAKE_ALISP_SLEEP="60"), self.args_file.exists)

        self.assertTrue(wait_for(lambda: process_gone(self.alisp_call()["pid"]), 10))

    def test_lisp_gets_no_stdin_so_a_reading_program_cannot_hang(self):
        self.run_wrapper("a.lisp", stdin_text="agent input\n", stdout="OK\n")
        self.assertEqual(self.alisp_call()["stdin"], "")

    def test_upstream_tool_errors_pass_through(self):
        self.env["LISP_BIN"] = "/no/such/alisp"
        missing_lisp = self.run_wrapper("a.lisp")
        self.assertEqual(missing_lisp.returncode, 2)
        self.assertEqual(
            missing_lisp.stdout,
            "lisp-check: Lisp binary '/no/such/alisp' not found."
            " Install Allegro CL or set LISP_BIN to its path.\nFAIL\n",
        )

        self.env["LISP_BIN"] = str(FAKE_ALISP)
        crash = self.run_wrapper("a.lisp", exit=3)
        self.assertEqual(crash.returncode, 2)
        self.assertEqual(crash.stdout.splitlines()[-1], "FAIL")
        self.assertIn("exit status 3", crash.stdout)

    def test_logs_one_line_per_invocation(self):
        self.run_wrapper("a.lisp", stdout="OK\n", exit=0)
        self.run_wrapper("--test", "a.lisp", stdout="FAIL\n", exit=1)
        lines = (self.run_dir / ".lisp-check.log").read_text().splitlines()
        fields = [line.split("\t") for line in lines]
        self.assertEqual([f[1:] for f in fields], [["0", "a.lisp"], ["1", "--test", "a.lisp"]])


class TimeoutCleanupFailureTest(unittest.TestCase):
    """The timeout path still prints its FAIL lines and logs when cleaning up goes wrong."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name).resolve()
        (self.run_dir / "a.lisp").write_text("(defun add1 (x) (+ x 1))\n")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LISP_CHECK_", "FAKE_"))}
        env.update(LISP_CHECK_TIMEOUT="1", LISP_CHECK_LOG=str(self.run_dir / "rounds.log"))
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        cwd = os.getcwd()
        os.chdir(self.run_dir)
        self.addCleanup(os.chdir, cwd)

    def run_main(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = lisp_check.main(["a.lisp"])
        return code, out.getvalue()

    def assert_timed_out_and_logged(self, code, stdout):
        self.assertEqual((stdout, code), ("lisp-check: timed out after 1 s\nFAIL\n", 2))
        lines = (self.run_dir / "rounds.log").read_text().splitlines()
        self.assertEqual([line.split("\t")[1:] for line in lines], [["2", "a.lisp"]])

    def test_child_that_exits_just_before_the_kill(self):
        os.environ.update(LISP_CHECK_MODE="native", LISP_BIN=str(FAKE_ALISP), FAKE_ALISP_SLEEP="60")
        real_killpg = os.killpg

        def kill_then_report_gone(pid, sig):
            real_killpg(pid, sig)
            raise ProcessLookupError

        with mock.patch.object(lisp_check.os, "killpg", side_effect=kill_then_report_gone):
            code, stdout = self.run_main()

        self.assert_timed_out_and_logged(code, stdout)

    def test_docker_kill_that_hangs(self):
        os.environ.update(LISP_CHECK_MODE="docker", LISP_CHECK_DOCKER=str(FAKE_DOCKER),
                          FAKE_DOCKER_SLEEP="60", FAKE_DOCKER_KILL_SLEEP="30")

        with mock.patch.object(lisp_check, "DOCKER_KILL_TIMEOUT", 1):
            code, stdout = self.run_main()

        self.assert_timed_out_and_logged(code, stdout)


def docker_image_available():
    image = os.environ.get("LISP_CHECK_IMAGE", "lisp-skills-allegro:latest")
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image], capture_output=True
        )
    except OSError:
        return False
    return result.returncode == 0


class RealAllegroChecks:
    """lisp-check behaviour against real Allegro CL, shared by docker and native mode."""

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

    def test_logs_the_invocation_in_the_run_folder(self):
        self.write("ok.lisp", "(defun add1 (x) (+ x 1))\n")
        self.run_wrapper("ok.lisp")
        lines = (self.run_dir / ".lisp-check.log").read_text().splitlines()
        self.assertEqual([line.split("\t")[1:] for line in lines], [["0", "ok.lisp"]])


@unittest.skipUnless(docker_image_available(), "lisp-skills-allegro image not available")
class RealDockerTest(RealAllegroChecks, unittest.TestCase):
    def run_wrapper(self, *args, cwd=None):
        return subprocess.run(
            [str(LISP_CHECK), *args],
            cwd=cwd or self.run_dir,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def test_endless_file_times_out_and_leaves_no_container_running(self):
        self.write("endless.lisp", "(eval-when (:compile-toplevel :load-toplevel :execute) (loop))\n")
        self.env["LISP_CHECK_TIMEOUT"] = "30"
        start = time.monotonic()

        result = self.run_wrapper("endless.lisp")

        self.assertLess(time.monotonic() - start, 90)
        self.assertEqual((result.stdout, result.returncode),
                         ("lisp-check: timed out after 30 s\nFAIL\n", 2))
        containers = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"volume={self.run_dir}"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(containers.stdout, "")

    def running_containers(self):
        return subprocess.run(
            ["docker", "ps", "-q", "--filter", f"volume={self.run_dir}"],
            capture_output=True, text=True, check=True,
        ).stdout

    def test_killed_wrapper_leaves_no_container_running(self):
        self.write("endless.lisp", "(eval-when (:compile-toplevel :load-toplevel :execute) (loop))\n")

        terminate_like_the_runner([str(LISP_CHECK), "endless.lisp"], self.run_dir, self.env,
                                  lambda: self.running_containers() != "")

        self.assertTrue(wait_for(lambda: self.running_containers() == "", 30),
                        "a lisp-check container outlived the killed wrapper")

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


NATIVE_TEST_IMAGE = "lisp-check-native-test:local"
CONTAINER_ALISP = "/opt/acl11.0express.64/alisp"


def build_native_test_image():
    """Throwaway image: the Allegro image plus python3, so the wrapper can run inside it."""
    base = os.environ.get("LISP_CHECK_IMAGE", "lisp-skills-allegro:latest")
    dockerfile = (
        f"FROM {base}\n"
        "RUN apt-get update"
        " && apt-get install -y --no-install-recommends python3"
        " && rm -rf /var/lib/apt/lists/*\n"
    )
    subprocess.run(
        ["docker", "build", "--platform", "linux/amd64", "-q", "-t", NATIVE_TEST_IMAGE, "-"],
        input=dockerfile, capture_output=True, text=True, check=True,
    )


@unittest.skipUnless(docker_image_available(), "lisp-skills-allegro image not available")
class NativeInContainerTest(RealAllegroChecks, unittest.TestCase):
    """Native mode, run inside the Allegro image the way it runs on the openSUSE server."""

    @classmethod
    def setUpClass(cls):
        build_native_test_image()

    def run_wrapper(self, *args, cwd=None, extra_env=()):
        env_flags = ["-e", "LISP_CHECK_MODE=native"]
        for item in extra_env:
            env_flags += ["-e", item]
        return subprocess.run(
            [
                "docker", "run", "--rm", "--platform", "linux/amd64",
                "-v", f"{REPO}:{REPO}:ro",
                "-v", f"{self.run_dir}:{self.run_dir}",
                "-w", str(cwd or self.run_dir),
                *env_flags,
                NATIVE_TEST_IMAGE,
                str(LISP_CHECK), *args,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )

    def test_lisp_bin_names_alisp_when_it_is_not_on_path(self):
        self.write("ok.lisp", "(defun add1 (x) (+ x 1))\n")
        result = self.run_wrapper(
            "ok.lisp", extra_env=["PATH=/usr/bin:/bin", f"LISP_BIN={CONTAINER_ALISP}"]
        )
        self.assertEqual((result.stdout, result.returncode), ("OK\n", 0))


if __name__ == "__main__":
    unittest.main()
