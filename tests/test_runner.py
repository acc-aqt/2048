import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from harness import runner
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

    def run_task(self, *args, setup="without-skills", run_number="1", task="dummy-slide-row", timeout=600):
        return subprocess.run(
            [str(RUN_TASK), task, setup, run_number,
             "--run-root", str(self.run_root), "--records-dir", str(self.records), *args],
            env=self.env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
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
        self.env["FAKE_OPENCODE_SOLUTION"] = str(WRONG)

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
        self.env["FAKE_OPENCODE_SOLUTION"] = str(WRONG)

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

    def test_prompt_names_the_files_and_how_to_check_each_lisp_file(self):
        self.run_task(task="game-2048", setup="with-skills")

        prompt = self.seen()[0]["argv"][-1]
        for name in ("game-2048.asd", "package.lisp", "game-2048.lisp", "game-2048-tests.lisp"):
            self.assertIn(f"`{name}`", prompt.split("\n\n")[1])
        for check in ("lisp-check package.lisp", "lisp-check game-2048.lisp",
                      "lisp-check --test game-2048-tests.lisp"):
            self.assertIn(f"`{check}`", prompt)
        self.assertNotIn("lisp-check game-2048.asd", prompt)
        self.assertNotIn("lisp-check game-2048-tests.lisp", prompt)

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
        self.assertIsNone(result["limit_hit"])
        self.assertGreaterEqual(result["duration_seconds"], 0)
        for key in ("hidden_tests_passed", "hidden_tests_total", "passed", "session_id"):
            self.assertIn(key, result)
        self.assertEqual(result["session_id"], "ses_fake0001")

    def test_run_zero_is_the_uncounted_practice_run(self):
        self.run_task(run_number="0")
        self.run_task(run_number="1")

        self.assertFalse(self.result(run_number="0")["counted"])
        self.assertTrue(self.result(run_number="1")["counted"])

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

    def test_symlinks_and_special_files_in_the_model_folder_are_skipped_and_listed(self):
        self.env["FAKE_OPENCODE_SPECIAL_FILES"] = "1"

        completed = self.run_task(timeout=120)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = self.result()
        self.assertEqual(result["skipped_files"], {"dangling.lisp": "symlink", "pipe": "special file"})
        sources = sorted(p.name for p in (self.record_dir() / "src").iterdir())
        self.assertEqual(sources, sorted(p.name for p in WRONG.iterdir()))

    def test_a_record_folder_without_result_json_counts_as_missing(self):
        leftover = self.record_dir()
        leftover.mkdir(parents=True)
        (leftover / "transcript.jsonl").write_text("half a record\n")

        completed = self.run_task()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.result()["run_number"], 1)
        self.assertNotIn("half a record", (self.record_dir() / "transcript.jsonl").read_text())

    def test_no_partial_record_folders_are_left_next_to_the_record(self):
        self.run_task()

        self.assertEqual([p.name for p in self.record_dir().parent.iterdir()], ["1"])

    def test_refuses_to_overwrite_an_existing_record(self):
        self.run_task()
        before = (self.record_dir() / "result.json").read_text()

        again = self.run_task()

        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already exists", again.stderr)
        self.assertEqual((self.record_dir() / "result.json").read_text(), before)
        self.assertEqual(len(self.seen()), 1)


class RecordsBackendGuardTest(RunnerTestCase):
    def setUp(self):
        super().setUp()
        self.use_fake_docker_printing_ok()
        self.env.update(FAKE_OPENCODE_SOLUTION=str(WRONG), CODEX_BIN=str(FIXTURES / "fake-codex"),
                        FAKE_CODEX_SOLUTION=str(WRONG), DOCKER_HOST="unix:///nonexistent/docker.sock")

    def make_record(self, result, setup="with-skills", run_number="1"):
        record = self.record_dir(setup=setup, run_number=run_number)
        record.mkdir(parents=True)
        (record / "result.json").write_text(json.dumps(result) + "\n")

    def test_refuses_a_records_dir_holding_another_backends_records_for_the_task(self):
        self.make_record({"backend": "claude"})

        completed = self.run_task()

        self.assertEqual(completed.returncode, 1)
        self.assertIn("claude", completed.stderr)
        self.assertIn("--records-dir", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(self.seen_file.exists())
        self.assertFalse(self.run_root.exists())

    def test_records_without_a_backend_field_count_as_opencode(self):
        self.make_record({})

        refused = self.run_task("--backend", "codex")
        allowed = self.run_task()

        self.assertEqual(refused.returncode, 1)
        self.assertIn("opencode", refused.stderr)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_records_of_the_same_backend_or_another_task_are_fine(self):
        self.make_record({"backend": "codex"})
        other_task = self.records / "game-2048" / "with-skills" / "1"
        other_task.mkdir(parents=True)
        (other_task / "result.json").write_text(json.dumps({"backend": "claude"}) + "\n")

        completed = self.run_task("--backend", "codex")

        self.assertEqual(completed.returncode, 0, completed.stderr)


class ContinueTest(RunnerTestCase):
    def setUp(self):
        super().setUp()
        self.use_fake_docker_printing_ok()
        self.env["FAKE_OPENCODE_SOLUTION"] = str(WRONG)

    def test_no_continue_when_every_file_prints_ok(self):
        self.run_task()

        self.assertEqual(len(self.seen()), 1)
        self.assertFalse(self.result()["continue_sent"])

    def test_continues_the_same_session_once_when_the_model_stops_early(self):
        self.env["FAKE_OPENCODE_SCENARIO"] = "stop-early"

        self.run_task()

        first, second = self.seen()
        self.assertEqual(second["argv"][:-1],
                         ["run", "--format", "json", "--thinking", "-s", "ses_fake0001"])
        self.assertNotEqual(second["argv"][-1], first["argv"][-1])
        result = self.result()
        self.assertTrue(result["continue_sent"])
        self.assertEqual(result["check_fix_rounds"], 3)
        events = (self.record_dir() / "transcript.jsonl").read_text()
        self.assertIn("I stop here.", events)
        self.assertIn("Done.", events)

    def test_continue_is_sent_at_most_once(self):
        self.env["FAKE_OPENCODE_SCENARIO"] = "never-done"

        self.run_task()

        self.assertEqual(len(self.seen()), 2)
        self.assertTrue(self.result()["continue_sent"])
        self.assertFalse(self.result()["passed"])

    def test_continues_when_only_the_asd_is_missing(self):
        self.env["FAKE_OPENCODE_SCENARIO"] = "no-asd-first"

        self.run_task()

        self.assertEqual(len(self.seen()), 2)
        self.assertTrue(self.result()["continue_sent"])
        self.assertTrue(self.result()["passed"])

    def test_the_status_check_between_turns_is_not_charged_to_the_wall_clock_limit(self):
        # Each lisp-check takes 2 s: the status check (3 files) and the continue turn (3 files)
        # each take about 6.5 s, more than the 9 s limit together but less than it alone.
        self.env.update(FAKE_OPENCODE_SCENARIO="no-asd-first", FAKE_DOCKER_SLEEP="2")

        self.run_task("--timeout", "9")

        result = self.result()
        self.assertTrue(result["continue_sent"])
        self.assertIsNone(result["limit_hit"])
        self.assertTrue(result["passed"])
        self.assertLess(result["duration_seconds"], 10)

    def test_continues_when_a_file_does_not_print_ok(self):
        self.env.update(FAKE_DOCKER_STDOUT="FAIL\n", FAKE_DOCKER_EXIT="1")

        self.run_task()

        self.assertEqual(len(self.seen()), 2)
        self.assertEqual(self.result()["check_fix_rounds"], 6)


class LimitTest(RunnerTestCase):
    def setUp(self):
        super().setUp()
        self.use_fake_docker_printing_ok()

    def test_hanging_opencode_is_killed_at_the_wall_clock_limit_and_the_run_still_recorded(self):
        self.env["FAKE_OPENCODE_SCENARIO"] = "hang"
        start = time.monotonic()

        self.run_task("--timeout", "2")

        self.assertLess(time.monotonic() - start, 60)
        result = self.result()
        self.assertEqual(result["limit_hit"], "wall_clock")
        self.assertFalse(result["passed"])
        self.assertFalse(result["continue_sent"])
        self.assertTrue((self.record_dir() / "transcript.jsonl").is_file())

    def test_a_check_running_at_the_limit_gets_its_container_killed(self):
        kills = Path(self.tmp.name) / "kills.jsonl"
        self.env.update(FAKE_OPENCODE_SCENARIO="check-then-hang", FAKE_DOCKER_SLEEP="60",
                        FAKE_DOCKER_KILL_SLEEP="1", FAKE_DOCKER_KILLS=str(kills))

        self.run_task("--timeout", "3", "--check-timeout", "1")

        self.assertEqual(self.result()["limit_hit"], "wall_clock")
        model_kills = [json.loads(line) for line in kills.read_text().splitlines()]
        self.assertGreaterEqual(len(model_kills), 2, "the model's check container was not killed")

    def test_endless_check_fix_rounds_stop_at_40_rounds(self):
        self.env["FAKE_OPENCODE_SCENARIO"] = "endless-checks"
        start = time.monotonic()

        completed = self.run_task()

        self.assertLess(time.monotonic() - start, 120)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = self.result()
        self.assertEqual(result["limit_hit"], "rounds")
        self.assertGreaterEqual(result["check_fix_rounds"], 40)
        self.assertLess(result["check_fix_rounds"], 45)
        self.assertFalse(result["passed"])
        self.assertFalse(result["continue_sent"])
        self.assertEqual(result["limits"],
                         {"max_rounds": 40, "timeout_seconds": 7200, "check_timeout_seconds": 120})

    def test_round_limit_can_be_set(self):
        self.env["FAKE_OPENCODE_SCENARIO"] = "endless-checks"

        completed = self.run_task("--max-rounds", "5")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = self.result()
        self.assertEqual(result["limit_hit"], "rounds")
        self.assertEqual(result["limits"]["max_rounds"], 5)
        self.assertLess(result["check_fix_rounds"], 10)

    def test_no_limit_hit_on_a_normal_run(self):
        self.env["FAKE_OPENCODE_SOLUTION"] = str(WRONG)

        self.run_task()

        self.assertIsNone(self.result()["limit_hit"])


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


class StopGroupTest(unittest.TestCase):
    def test_a_group_whose_members_already_exited_is_stopped_without_error(self):
        process = subprocess.Popen(["true"], start_new_session=True, stdin=subprocess.DEVNULL)
        os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)

        runner.stop_group(process)

        self.assertEqual(process.returncode, 0)


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
