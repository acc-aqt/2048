import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "bin" / "results"
PINNED_LISP_SKILLS = "07effc058c7d0c89347318f000d16ad5f13612a6"


def table_row(markdown, *cells):
    """The first table row that starts with CELLS, as a list of cell texts."""
    for line in markdown.splitlines():
        row = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and row[:len(cells)] == list(cells):
            return row
    raise AssertionError(f"no table row starting with {cells}")


def section(markdown, heading):
    """The text under the ## HEADING, up to the next ## heading."""
    start = markdown.index(f"## {heading}\n")
    end = markdown.find("\n## ", start + 1)
    return markdown[start:end if end != -1 else None]


class ResultsTest(unittest.TestCase):
    """Builds RESULTS.md from synthetic result records; nothing is run."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.root = root
        self.records = root / "runs"
        self.output = root / "RESULTS.md"

    def tearDown(self):
        self.tmp.cleanup()

    def add_record(self, setup, number, passed=False, hidden=(30, 66), rounds=12, duration=1800.0,
                   limit_hit=None, continue_sent=False, model="qwen3-8b-32k", task="game-2048",
                   records=None, **extra):
        record = (records or self.records) / task / setup / str(number)
        (record / "src").mkdir(parents=True)
        (record / "result.json").write_text(json.dumps(extra | {
            "task": task, "setup": setup, "run_number": number, "counted": number != 0,
            "model": model, "started_at": "2026-11-21T01:00:00+00:00",
            "duration_seconds": duration,
            "limits": {"max_rounds": 40, "timeout_seconds": 7200, "check_timeout_seconds": 120},
            "limit_hit": limit_hit, "opencode_exit_code": 0, "continue_sent": continue_sent,
            "check_fix_rounds": rounds,
            "hidden_tests_passed": hidden[0], "hidden_tests_total": hidden[1],
            "source_files": {"game-2048.lisp": "OK" if passed else "FAIL"},
            "passed": passed, "session_id": "ses_x", "run_folder": "/tmp/x",
        } | extra))

    def add_full_batch(self, passing=None):
        """Five failing runs per setup; PASSING maps (setup, run) to the rounds of a passing run."""
        passing = passing or {}
        for number in range(1, 6):
            for setup in ("without-skills", "with-skills"):
                if (setup, number) in passing:
                    self.add_record(setup, number, passed=True, hidden=(66, 66),
                                    rounds=passing[setup, number])
                elif setup == "without-skills":
                    self.add_record(setup, number, hidden=(10 * number, 66), rounds=number,
                                    duration=600.0 * number)
                else:
                    self.add_record(setup, number, rounds=40 if number == 5 else 20,
                                    limit_hit="rounds" if number == 5 else None)

    def results(self, task="game-2048"):
        completed = subprocess.run(
            [str(RESULTS), task, "--records-dir", str(self.records), "--output", str(self.output)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return self.output.read_text()

    def overview(self, *records_dirs, task="game-2048", expect_exit=0):
        completed = subprocess.run(
            [str(RESULTS), task, "--overview", *map(str, records_dirs), "--output", str(self.output)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(completed.returncode, expect_exit, completed.stderr)
        return self.output.read_text() if expect_exit == 0 else completed.stderr

    def add_backend_batch(self, records, backend, model, cost):
        """Runs 1-3 per setup for BACKEND under RECORDS; with-skills passes, tokens and cost grow by run."""
        for number in (1, 2, 3):
            for setup in ("with-skills", "without-skills"):
                passed = setup == "with-skills"
                self.add_record(setup, number, records=records, model=model, backend=backend,
                                reasoning_effort="low", passed=passed, hidden=(66 if passed else 10 * number, 66),
                                rounds=number * 2, duration=60.0 * number, total_tokens=1000 * number,
                                cost_usd=cost * number if cost is not None else None)

    def test_overview_has_one_row_per_backend_and_setup(self):
        claude, codex = self.root / "runs" / "claude", self.root / "runs" / "codex"
        self.add_backend_batch(claude, "claude", "haiku", cost=0.5)
        self.add_backend_batch(codex, "codex", "gpt-6-luna", cost=None)

        markdown = section(self.overview(claude, codex), "Overview")

        self.assertEqual(table_row(markdown, "claude", "haiku", "low", "with-skills"),
                         ["claude", "haiku", "low", "with-skills", "3", "3/3", "66/66", "4", "2 min",
                          "2,000", "$1.00", "runs/claude"])
        self.assertEqual(table_row(markdown, "claude", "haiku", "low", "without-skills")[5:7], ["0/3", "20/66"])
        self.assertEqual(table_row(markdown, "codex", "gpt-6-luna", "low", "with-skills")[9:],
                         ["2,000", "n/a", "runs/codex"])
        self.assertEqual(table_row(markdown, "codex", "gpt-6-luna", "low", "without-skills")[5], "0/3")

    def test_one_table_row_per_counted_run(self):
        self.add_full_batch()

        markdown = section(self.results(), "Counted runs")

        self.assertEqual(table_row(markdown, "without-skills", "2"),
                         ["without-skills", "2", "2", "20/66", "20 min", "-", "no", "FAIL"])
        self.assertEqual(table_row(markdown, "with-skills", "5")[5], "rounds")

    def test_continue_and_pass_are_shown(self):
        self.add_record("with-skills", 1, passed=True, hidden=(66, 66), rounds=7, duration=95.0,
                        continue_sent=True)

        markdown = section(self.results(), "Counted runs")

        self.assertEqual(table_row(markdown, "with-skills", "1"),
                         ["with-skills", "1", "7", "66/66", "1.6 min", "-", "yes", "PASS"])

    def test_summary_per_setup(self):
        self.add_full_batch(passing={("with-skills", 2): 8})

        markdown = section(self.results(), "Summary per setup")

        self.assertEqual(table_row(markdown, "without-skills"),
                         ["without-skills", "5", "0/5", "30/66", "3", "30 min"])
        self.assertEqual(table_row(markdown, "with-skills")[2], "1/5")

    def test_practice_run_is_listed_separately_and_not_counted(self):
        self.add_full_batch()
        self.add_record("with-skills", 0, passed=True, hidden=(66, 66), rounds=99)

        output = self.results()

        self.assertNotIn("| 99 |", section(output, "Counted runs"))
        self.assertEqual(table_row(section(output, "Summary per setup"), "with-skills")[2], "0/5")
        self.assertIn("| 99 |", section(output, "Practice run (not counted)"))

    def test_says_how_many_counted_records_are_missing(self):
        self.add_record("with-skills", 1)

        output = self.results()

        self.assertIn("1 of 10 counted runs", output)

    def test_method_names_the_model_and_the_pinned_lisp_skills_commit(self):
        self.add_record("with-skills", 1, model="qwen3-8b-fp8")

        method = section(self.results(), "Method")

        self.assertIn("qwen3-8b-fp8", method)
        self.assertIn(PINNED_LISP_SKILLS, method)
        self.assertIn("40", method)

    def test_threats_to_validity(self):
        self.add_record("with-skills", 1)

        threats = section(self.results(), "Threats to validity")

        for phrase in ("Q4_K_M", "FP8", "v0.1", "5 runs per setup", "Docker", "human"):
            self.assertIn(phrase, threats)

    def test_explains_how_to_regrade_any_run(self):
        self.add_record("with-skills", 1)

        regrade = section(self.results(), "Rerun the hidden tests yourself")

        self.assertIn("bin/regrade runs/game-2048/with-skills/1", regrade)

    def test_record_paths_follow_the_records_dir(self):
        self.records = self.root / "night-2"
        self.add_record("with-skills", 1, passed=True, hidden=(66, 66))

        output = self.results()

        self.assertIn("bin/regrade night-2/game-2048/with-skills/1", output)
        self.assertIn("night-2/game-2048/with-skills/1/src", section(output, "Play the best game"))
        self.assertNotIn("runs/", output)

    def test_record_paths_outside_the_output_folder_are_absolute(self):
        self.records = self.root / "elsewhere" / "records"
        self.output = self.root / "report" / "RESULTS.md"
        self.output.parent.mkdir()
        self.add_record("with-skills", 1)

        output = self.results()

        self.assertIn(f"bin/regrade {self.records}/game-2048/with-skills/1", output)

    def test_states_plainly_when_no_run_passed(self):
        self.add_full_batch()

        play = section(self.results(), "Play the best game")

        self.assertIn("No counted run passed", play)
        self.assertNotIn("play)", play)

    def test_tells_how_to_play_the_best_passing_run(self):
        self.add_full_batch(passing={("without-skills", 3): 9, ("with-skills", 4): 4})

        play = section(self.results(), "Play the best game")

        self.assertIn("runs/game-2048/with-skills/4/src", play)
        self.assertNotIn("without-skills/3", play)
        self.assertIn("(game-2048:play)", play)
        self.assertIn("lisp-skills-allegro", play)

    def test_play_instructions_work_on_a_temporary_copy_of_src(self):
        self.add_record("with-skills", 1, passed=True, hidden=(66, 66))

        play = section(self.results(), "Play the best game")

        self.assertIn('cp -R runs/game-2048/with-skills/1/src/. "$play_dir"', play)
        self.assertIn('cd "$play_dir"', play)
        self.assertNotIn("cd runs/", play)

    def test_no_play_section_for_a_task_without_play(self):
        self.add_record("with-skills", 1, passed=True, hidden=(11, 11), task="dummy-slide-row")

        output = self.results(task="dummy-slide-row")

        self.assertNotIn("## Play the best game", output)
        self.assertNotIn(":play)", output)

    def test_method_describes_a_claude_only_report(self):
        self.add_record("with-skills", 1, model="haiku", backend="claude", reasoning_effort="low",
                        budget_usd=5)

        method = section(self.results(), "Method")

        self.assertIn("Claude Code", method)
        self.assertIn("`haiku`", method)
        self.assertIn("`low` effort", method)
        self.assertIn("CLAUDE.md", method)
        self.assertNotIn("OpenCode", method)

    def test_method_describes_a_codex_only_report(self):
        self.add_record("with-skills", 1, model="gpt-6-luna", backend="codex", reasoning_effort="low")

        method = section(self.results(), "Method")

        self.assertIn("Codex CLI", method)
        self.assertIn("`gpt-6-luna`", method)
        self.assertIn("AGENTS.md", method)
        self.assertNotIn("OpenCode", method)

    def test_claude_only_report_does_not_mention_opencode_or_local_quantisation(self):
        self.add_record("with-skills", 1, model="haiku", backend="claude", reasoning_effort="low")

        output = self.results()

        self.assertNotIn("OpenCode", output)
        self.assertNotIn("Q4_K_M", output)
        self.assertIn("Claude Code turns", section(output, "Summary per setup"))
        self.assertIn("agent harness", section(output, "Threats to validity"))

    def test_summary_shows_median_tokens_and_cost_when_records_have_them(self):
        for number, tokens, cost in ((1, 100_000, 0.5), (2, 300_000, 1.25), (3, 200_000, 2.0)):
            self.add_record("with-skills", number, model="haiku", backend="claude", reasoning_effort="low",
                            total_tokens=tokens, cost_usd=cost)
        self.add_record("without-skills", 1, model="haiku", backend="claude", reasoning_effort="low",
                        total_tokens=None, cost_usd=None)

        markdown = section(self.results(), "Summary per setup")

        self.assertIn("| Median tokens | Median cost |", markdown)
        self.assertEqual(table_row(markdown, "with-skills")[-2:], ["200,000", "$1.25"])
        self.assertEqual(table_row(markdown, "without-skills")[-2:], ["n/a", "n/a"])

    def test_codex_summary_shows_tokens_but_no_cost(self):
        self.add_record("with-skills", 1, model="gpt-6-luna", backend="codex", reasoning_effort="low",
                        total_tokens=1234, cost_usd=None)

        markdown = section(self.results(), "Summary per setup")

        self.assertEqual(table_row(markdown, "with-skills")[-1], "1,234")
        self.assertNotIn("Median cost", markdown)

    def test_counted_runs_are_sorted_by_run_then_setup(self):
        self.add_record("without-skills", 2)
        self.add_record("with-skills", 1)
        self.add_record("without-skills", 1)

        markdown = section(self.results(), "Counted runs")
        rows = [line.split("|")[1:3] for line in markdown.splitlines() if line.startswith("| with")]

        self.assertEqual([[c.strip() for c in row] for row in rows],
                         [["with-skills", "1"], ["without-skills", "1"], ["without-skills", "2"]])


if __name__ == "__main__":
    unittest.main()
