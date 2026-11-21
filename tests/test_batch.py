import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUN_BATCH = REPO / "bin" / "run-batch"
FIXTURES = REPO / "tests" / "fixtures"
WRONG = FIXTURES / "dummy-wrong-solution"
TASK = "dummy-slide-row"


class BatchTest(unittest.TestCase):
    """Runs bin/run-batch with the fake opencode and fake docker; no request ever reaches a model."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.run_root = root / "run-root"
        self.records = root / "records"
        self.seen_file = root / "fake-opencode-seen.jsonl"
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("LISP_CHECK_", "FAKE_", "RUN_"))}
        self.env.update(
            OPENCODE_BIN=str(FIXTURES / "fake-opencode"),
            FAKE_OPENCODE_RECORD=str(self.seen_file),
            FAKE_OPENCODE_SOLUTION=str(WRONG),
            LISP_CHECK_DOCKER=str(FIXTURES / "fake-docker"),
            FAKE_DOCKER_STDOUT="OK\n",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_batch(self, *args):
        return subprocess.run(
            [str(RUN_BATCH), TASK, "--run-root", str(self.run_root),
             "--records-dir", str(self.records), *args],
            env=self.env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600,
        )

    def runs_started(self):
        """(setup, run number) of every opencode start, in order."""
        if not self.seen_file.exists():
            return []
        started = []
        for line in self.seen_file.read_text().splitlines():
            run_folder = Path(json.loads(line)["cwd"]).parent
            started.append((run_folder.parent.name, int(run_folder.name.split("-")[0])))
        return started

    def records_present(self):
        return sorted((p.parent.parent.name, int(p.parent.name))
                      for p in self.records.glob(f"{TASK}/*/*/result.json"))

    def test_runs_five_counted_runs_per_setup_alternating_which_setup_goes_first(self):
        completed = self.run_batch()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.runs_started(), [
            ("with-skills", 1), ("without-skills", 1),
            ("without-skills", 2), ("with-skills", 2),
            ("with-skills", 3), ("without-skills", 3),
            ("without-skills", 4), ("with-skills", 4),
            ("with-skills", 5), ("without-skills", 5),
        ])
        self.assertEqual(len(self.records_present()), 10)

    def test_every_run_gets_the_same_limits(self):
        self.run_batch("--max-rounds", "7", "--timeout", "300", "--check-timeout", "30")

        for result_file in self.records.glob(f"{TASK}/*/*/result.json"):
            self.assertEqual(json.loads(result_file.read_text())["limits"],
                             {"max_rounds": 7, "timeout_seconds": 300, "check_timeout_seconds": 30})

    def make_record(self, setup, number, result_json=True):
        record = self.records / TASK / setup / str(number)
        record.mkdir(parents=True)
        if result_json:
            (record / "result.json").write_text("{}\n")

    def test_resumes_by_skipping_runs_that_already_have_a_record(self):
        for setup in ("with-skills", "without-skills"):
            self.make_record(setup, 1)
        self.make_record("without-skills", 2)

        completed = self.run_batch()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        started = self.runs_started()
        self.assertEqual(len(started), 7)
        self.assertEqual(started[0], ("with-skills", 2))
        self.assertNotIn(("without-skills", 2), started)
        self.assertIn("skip", completed.stdout)

    def test_reruns_a_record_folder_without_result_json(self):
        self.make_record("with-skills", 1, result_json=False)

        completed = self.run_batch()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.runs_started()[0], ("with-skills", 1))
        self.assertTrue((self.records / TASK / "with-skills" / "1" / "result.json").is_file())

    def test_keeps_going_after_a_failed_run_and_reports_it(self):
        self.env["OPENCODE_BIN"] = str(Path(self.tmp.name) / "no-such-opencode")

        completed = self.run_batch()

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.count("run-task failed"), 10)
        self.assertEqual(self.records_present(), [])

    def test_rejects_an_unknown_task_before_starting_any_run(self):
        completed = subprocess.run(
            [str(RUN_BATCH), "no-such-task", "--run-root", str(self.run_root),
             "--records-dir", str(self.records)],
            env=self.env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("unknown task", completed.stderr)
        self.assertEqual(self.runs_started(), [])

    def test_never_runs_the_practice_run(self):
        self.run_batch()

        self.assertNotIn(0, [number for _, number in self.runs_started()])

    def test_codex_backend_model_and_effort_reach_every_run(self):
        codex_seen = Path(self.tmp.name) / "fake-codex-seen.jsonl"
        self.env.update(CODEX_BIN=str(FIXTURES / "fake-codex"), FAKE_CODEX_RECORD=str(codex_seen),
                        FAKE_CODEX_SOLUTION=str(WRONG), DOCKER_HOST="unix:///nonexistent/docker.sock")

        completed = self.run_batch("--backend", "codex", "--model", "gpt-other", "--reasoning-effort", "medium")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(codex_seen.read_text().splitlines()), 10)
        self.assertEqual(self.runs_started(), [])
        results = [json.loads(p.read_text()) for p in self.records.glob(f"{TASK}/*/*/result.json")]
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertEqual((result["backend"], result["model"], result["reasoning_effort"]),
                             ("codex", "gpt-other", "medium"))


if __name__ == "__main__":
    unittest.main()
