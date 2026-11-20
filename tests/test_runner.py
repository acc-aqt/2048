import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests.support import docker_image_available

REPO = Path(__file__).resolve().parent.parent
RUN_TASK = REPO / "bin" / "run-task"
FIXTURES = REPO / "tests" / "fixtures"
FAKE_OPENCODE = FIXTURES / "fake-opencode"
FAKE_DOCKER = FIXTURES / "fake-docker"
REFERENCE = REPO / "reference" / "dummy-slide-row"
WRONG = FIXTURES / "dummy-wrong-solution"
HIDDEN_TEST = REPO / "tasks" / "dummy-slide-row" / "hidden-tests" / "slide-row-hidden-tests.lisp"
SPEC = REPO / "tasks" / "dummy-slide-row" / "spec.md"
LISP_RULES = REPO / "vendor" / "lisp-skills" / "dist" / "lisp-rules.md"


class RunnerTestCase(unittest.TestCase):
    """Runs bin/run-task with the fake opencode; no request ever reaches a model."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.run_root = root / "run-root"
        self.records = root / "records"
        self.seen_file = root / "fake-opencode-seen.jsonl"
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("LISP_CHECK_", "FAKE_", "RUN_"))}
        self.env.update(
            OPENCODE_BIN=str(FAKE_OPENCODE),
            FAKE_OPENCODE_RECORD=str(self.seen_file),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def use_fake_docker_printing_ok(self):
        self.env.update(LISP_CHECK_DOCKER=str(FAKE_DOCKER), FAKE_DOCKER_STDOUT="OK\n")

    def run_task(self, *args, setup="without-skills", run_number="1", task="dummy-slide-row"):
        return subprocess.run(
            [str(RUN_TASK), task, setup, run_number,
             "--run-root", str(self.run_root), "--records-dir", str(self.records), *args],
            env=self.env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600,
        )

    def record_dir(self, setup="without-skills", run_number="1"):
        return self.records / "dummy-slide-row" / setup / run_number

    def result(self, **kwargs):
        return json.loads((self.record_dir(**kwargs) / "result.json").read_text())

    def seen(self):
        return [json.loads(line) for line in self.seen_file.read_text().splitlines()]


class RunFolderTest(RunnerTestCase):
    def setUp(self):
        super().setUp()
        self.use_fake_docker_printing_ok()

    def test_opencode_starts_in_an_empty_git_folder_without_hidden_tests(self):
        result = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)

        (seen,) = self.seen()
        self.assertEqual(seen["files"], [])
        self.assertTrue(seen["has_git"])
        self.assertTrue(Path(seen["cwd"]).is_relative_to(self.run_root))
        self.assertNotIn(HIDDEN_TEST.read_text(), json.dumps(seen))

    def test_opencode_runs_hands_off_and_isolated(self):
        self.run_task()

        (seen,) = self.seen()
        self.assertTrue(seen["stdin_is_devnull"])
        self.assertEqual(seen["argv"][:3], ["run", "--format", "json"])
        self.assertIn(SPEC.read_text(), seen["argv"][-1])
        self.assertTrue(Path(seen["env"]["OPENCODE_CONFIG"]).is_relative_to(self.run_root))
        self.assertEqual(seen["env"]["OPENCODE_DISABLE_CLAUDE_CODE_PROMPT"], "1")
        self.assertTrue(Path(seen["env"]["XDG_CONFIG_HOME"]).is_relative_to(self.run_root))

    def test_round_log_lives_outside_the_model_folder(self):
        self.run_task()

        (seen,) = self.seen()
        log = Path(seen["env"]["LISP_CHECK_LOG"])
        self.assertFalse(log.is_relative_to(seen["cwd"]))
        self.assertTrue(log.is_relative_to(self.run_root))

    def test_lisp_check_on_path_is_the_repo_wrapper(self):
        self.run_task()

        (seen,) = self.seen()
        first_dir = Path(seen["env"]["PATH"].split(os.pathsep)[0])
        self.assertEqual((first_dir / "lisp-check").resolve(), (REPO / "bin" / "lisp-check").resolve())

    def test_every_run_gets_a_fresh_folder(self):
        self.run_task(run_number="1")
        self.run_task(run_number="2")

        first, second = self.seen()
        self.assertNotEqual(first["cwd"], second["cwd"])
        self.assertEqual(second["files"], [])


class SetupTest(RunnerTestCase):
    def setUp(self):
        super().setUp()
        self.use_fake_docker_printing_ok()

    def run_both_setups(self):
        self.run_task(setup="with-skills")
        self.run_task(setup="without-skills")
        return self.seen()

    def test_with_skills_loads_the_pinned_rules_as_instructions_from_outside_the_model_folder(self):
        with_skills, _ = self.run_both_setups()

        (instruction,) = with_skills["config"]["instructions"]
        self.assertTrue(Path(instruction).is_absolute())
        self.assertEqual(Path(instruction).read_text(), LISP_RULES.read_text())
        self.assertTrue(Path(instruction).is_relative_to(self.run_root))
        self.assertFalse(Path(instruction).is_relative_to(with_skills["cwd"]))

    def test_without_skills_never_sees_the_rules(self):
        _, without_skills = self.run_both_setups()

        self.assertNotIn("instructions", without_skills["config"])
        run_folder = Path(without_skills["cwd"]).parent
        rules = LISP_RULES.read_text()
        for path in run_folder.rglob("*"):
            if path.is_file() and not path.is_symlink():
                self.assertNotIn(rules, path.read_text(errors="replace"), path)

    def test_setups_differ_only_in_the_rules_text(self):
        with_skills, without_skills = self.run_both_setups()

        note = "Run lisp-check FILE until it prints OK."
        self.assertEqual(with_skills["argv"][:-1], without_skills["argv"][:-1])
        self.assertNotIn(note, with_skills["argv"][-1])
        self.assertEqual(without_skills["argv"][-1].count(note), 1)
        self.assertEqual(with_skills["argv"][-1].strip(),
                         without_skills["argv"][-1].replace(note, "").strip())
        with_config = dict(with_skills["config"])
        del with_config["instructions"]
        self.assertEqual(with_config, without_skills["config"])
        self.assertEqual(without_skills["config"],
                         json.loads((REPO / "harness" / "opencode.json").read_text()))


class RecordTest(RunnerTestCase):
    def setUp(self):
        super().setUp()
        self.use_fake_docker_printing_ok()
        self.env["FAKE_OPENCODE_SOLUTION"] = str(WRONG)

    def test_writes_result_record(self):
        self.run_task()

        result = self.result()
        self.assertEqual(result["task"], "dummy-slide-row")
        self.assertEqual(result["setup"], "without-skills")
        self.assertEqual(result["run_number"], 1)
        self.assertEqual(result["check_fix_rounds"], 3)
        self.assertEqual(result["opencode_exit_code"], 0)
        self.assertFalse(result["timed_out"])
        self.assertGreaterEqual(result["duration_seconds"], 0)
        for key in ("hidden_tests_passed", "hidden_tests_total", "passed", "session_id"):
            self.assertIn(key, result)
        self.assertEqual(result["session_id"], "ses_fake0001")

    def test_saves_transcript_session_round_log_and_final_sources(self):
        self.run_task()

        record = self.record_dir()
        events = [json.loads(line) for line in (record / "transcript.jsonl").read_text().splitlines()]
        self.assertEqual(events[-1]["type"], "text")
        self.assertEqual(json.loads((record / "session.json").read_text())["info"]["id"], "ses_fake0001")
        self.assertEqual(len((record / "lisp-check.log").read_text().splitlines()), 3)
        self.assertTrue((record / "grading.log").is_file())
        sources = sorted(p.name for p in (record / "src").iterdir())
        self.assertEqual(sources, sorted(p.name for p in WRONG.iterdir()))

    def test_grading_checks_do_not_count_as_rounds(self):
        self.run_task()

        self.assertEqual(self.result()["check_fix_rounds"], 3)

    def test_refuses_to_overwrite_an_existing_record(self):
        self.run_task()
        before = (self.record_dir() / "result.json").read_text()

        again = self.run_task()

        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already exists", again.stderr)
        self.assertEqual((self.record_dir() / "result.json").read_text(), before)
        self.assertEqual(len(self.seen()), 1)


class TimeoutTest(RunnerTestCase):
    def test_hanging_opencode_is_killed_and_the_run_still_recorded(self):
        self.use_fake_docker_printing_ok()
        self.env["FAKE_OPENCODE_SCENARIO"] = "hang"
        start = time.monotonic()

        self.run_task("--timeout", "2")

        self.assertLess(time.monotonic() - start, 60)
        result = self.result()
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["passed"])
        self.assertTrue((self.record_dir() / "transcript.jsonl").is_file())


class ArgumentTest(RunnerTestCase):
    def test_rejects_unknown_setup_task_and_bad_run_number(self):
        for kwargs in ({"setup": "bogus"}, {"task": "no-such-task"}, {"run_number": "x"}):
            with self.subTest(**kwargs):
                result = self.run_task(**kwargs)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.seen_file.exists())

    def test_rejects_run_root_inside_the_repo_or_home(self):
        for root in (REPO / "runs-tmp", Path.home() / "2048-runs"):
            with self.subTest(root=root):
                result = subprocess.run(
                    [str(RUN_TASK), "dummy-slide-row", "without-skills", "1",
                     "--run-root", str(root), "--records-dir", str(self.records)],
                    env=self.env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("run root", result.stderr)
                self.assertFalse(root.exists())


@unittest.skipUnless(docker_image_available(), "lisp-skills-allegro image not available")
class EndToEndWithRealLispCheckTest(RunnerTestCase):
    def test_correct_solution_passes_all_hidden_tests(self):
        self.env["FAKE_OPENCODE_SOLUTION"] = str(REFERENCE)

        completed = self.run_task()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = self.result()
        self.assertEqual(result["check_fix_rounds"], 3)
        self.assertGreater(result["hidden_tests_total"], 0)
        self.assertEqual(result["hidden_tests_passed"], result["hidden_tests_total"])
        self.assertTrue(result["passed"])
        log = (self.record_dir() / "lisp-check.log").read_text().splitlines()
        self.assertEqual([line.split("\t")[1] for line in log], ["0", "0", "0"])

    def test_wrong_solution_fails_some_hidden_tests(self):
        self.env["FAKE_OPENCODE_SOLUTION"] = str(WRONG)

        self.run_task(setup="with-skills")

        result = self.result(setup="with-skills")
        self.assertLess(result["hidden_tests_passed"], result["hidden_tests_total"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
