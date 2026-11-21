import json
import os
import re
import time
import unittest
from pathlib import Path

from tests.test_runner import FIXTURES, LISP_RULES, REPO, RunnerTestCase, WRONG

FAKE_CODEX = FIXTURES / "fake-codex"
THREAD_ID = "019a0000-0000-7000-8000-00000000fake"


class CodexTestCase(RunnerTestCase):
    """Runs bin/run-task --backend codex with the fake codex; no request ever reaches a model."""

    def setUp(self):
        super().setUp()
        root = Path(self.tmp.name).resolve()
        self.seen_file = root / "fake-codex-seen.jsonl"
        self.user_codex_home = root / "user-codex-home"
        self.user_codex_home.mkdir()
        (self.user_codex_home / "auth.json").write_text('{"fake": "login"}\n')
        (self.user_codex_home / "config.toml").write_text('model_reasoning_effort = "high"\n')
        for key in [k for k in self.env if k.startswith("CODEX_")]:
            del self.env[key]
        self.env.update(
            CODEX_BIN=str(FAKE_CODEX),
            CODEX_HOME=str(self.user_codex_home),
            FAKE_CODEX_RECORD=str(self.seen_file),
            FAKE_CODEX_SOLUTION=str(WRONG),
            DOCKER_HOST=f"unix://{root / 'docker.sock'}",
        )
        self.use_fake_docker_printing_ok()

    def run_codex(self, *args, **kwargs):
        return self.run_task("--backend", "codex", *args, **kwargs)


class CodexModelTest(CodexTestCase):
    def test_defaults_to_gpt_6_luna_at_low_reasoning_effort(self):
        completed = self.run_codex()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        (seen,) = self.seen()
        argv = seen["argv"]
        self.assertEqual(argv[0], "exec")
        self.assertIn("--json", argv)
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6-luna")
        self.assertIn('model_reasoning_effort="low"', argv)
        result = self.result()
        self.assertEqual(result["backend"], "codex")
        self.assertEqual(result["model"], "gpt-6-luna")
        self.assertEqual(result["reasoning_effort"], "low")

    def test_model_and_effort_can_be_overridden_by_flags(self):
        self.env.update(CODEX_MODEL="from-env", CODEX_REASONING_EFFORT="medium")

        self.run_codex("--model", "gpt-other", "--reasoning-effort", "high")

        argv = self.seen()[0]["argv"]
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-other")
        self.assertIn('model_reasoning_effort="high"', argv)
        result = self.result()
        self.assertEqual((result["model"], result["reasoning_effort"]), ("gpt-other", "high"))

    def test_model_and_effort_can_be_overridden_by_environment(self):
        self.env.update(CODEX_MODEL="from-env", CODEX_REASONING_EFFORT="medium")

        self.run_codex()

        argv = self.seen()[0]["argv"]
        self.assertEqual(argv[argv.index("-m") + 1], "from-env")
        self.assertIn('model_reasoning_effort="medium"', argv)

    def test_opencode_rejects_model_flags(self):
        completed = self.run_task("--model", "gpt-other")

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--backend codex", completed.stderr)


def config_overrides(argv):
    return [argv[i + 1] for i, arg in enumerate(argv) if arg == "-c"]


def sandbox_filesystem(argv):
    """The harness profile's filesystem table, parsed from its inline-TOML -c override."""
    (table,) = [o.split("=", 1)[1] for o in config_overrides(argv) if o.startswith("permissions.harness.filesystem=")]
    return dict(re.findall(r'"([^"]+)"="(\w+)"', table))


class CodexIsolationTest(CodexTestCase):
    def test_runs_hands_off_in_an_empty_git_folder_in_the_run_root(self):
        self.run_codex()

        (seen,) = self.seen()
        self.assertEqual(seen["files"], [])
        self.assertTrue(Path(seen["cwd"]).is_relative_to(self.run_root))
        self.assertTrue(seen["stdin_is_devnull"])
        self.assertIn('approval_policy="never"', config_overrides(seen["argv"]))

    def test_codex_home_is_per_run_and_reuses_only_the_users_login(self):
        self.run_codex()

        (seen,) = self.seen()
        self.assertTrue(Path(seen["env"]["CODEX_HOME"]).is_relative_to(self.run_root))
        self.assertEqual(seen["codex_home"], {"auth.json": str(self.user_codex_home / "auth.json")})
        self.assertIn("--ignore-user-config", seen["argv"])
        self.assertIn("--ignore-rules", seen["argv"])

    def test_plugins_bundled_skills_subagents_and_web_search_are_off(self):
        self.run_codex()

        argv = self.seen()[0]["argv"]
        self.assertEqual(argv[argv.index("--disable") + 1], "multi_agent")
        for override in ("features.plugins=false", "skills.include_instructions=false",
                         'web_search="disabled"'):
            self.assertIn(override, config_overrides(argv))

    def test_sandbox_lets_the_model_write_only_its_folder_and_the_round_log(self):
        self.run_codex()

        (seen,) = self.seen()
        filesystem = sandbox_filesystem(seen["argv"])
        round_log_dir = Path(seen["env"]["LISP_CHECK_LOG"]).parent
        self.assertEqual({path for path, access in filesystem.items() if access == "write"},
                         {":project_roots", str(round_log_dir)})
        self.assertEqual(filesystem[":root"], "read")
        self.assertFalse(round_log_dir.is_relative_to(seen["cwd"]))
        self.assertNotEqual(round_log_dir, Path(seen["cwd"]).parent)

    def test_sandbox_hides_hidden_tests_reference_records_and_other_runs(self):
        self.run_codex()

        (seen,) = self.seen()
        filesystem = sandbox_filesystem(seen["argv"])
        for path in (REPO / "tasks", REPO / "reference", REPO / "runs", REPO / ".git", REPO / "tests",
                     self.records, self.run_root, Path.home()):
            self.assertEqual(filesystem[str(path)], "none", path)
        run_folder = Path(seen["cwd"]).parent
        for path in (REPO, run_folder / "bin", Path.home() / ".docker"):
            self.assertEqual(filesystem[str(path)], "read", path)
        for path in (REPO / "bin", REPO / "harness"):
            self.assertNotIn(str(path), filesystem)

    def test_sandbox_keeps_the_rules_files_read_only(self):
        self.run_codex(setup="with-skills")

        (seen,) = self.seen()
        filesystem = sandbox_filesystem(seen["argv"])
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertEqual(filesystem[str(Path(seen["cwd"]) / name)], "read", name)

    def test_sandbox_lets_lisp_check_reach_the_docker_socket(self):
        socket = Path(self.tmp.name).resolve() / "docker.sock"
        self.env["DOCKER_HOST"] = f"unix://{socket}"

        self.run_codex()

        overrides = config_overrides(self.seen()[0]["argv"])
        self.assertIn(f'permissions.harness.network={{"enabled"=true, "unix_sockets"={{"{socket}"="allow"}}}}',
                      overrides)

    def test_tests_never_touch_the_users_codex_home(self):
        self.run_codex()

        self.assertEqual(sorted(p.name for p in self.user_codex_home.iterdir()), ["auth.json", "config.toml"])

    def test_no_login_means_no_auth_link(self):
        (self.user_codex_home / "auth.json").unlink()

        completed = self.run_codex()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.seen()[0]["codex_home"], {})


class CodexSetupTest(CodexTestCase):
    def test_with_skills_finds_the_pinned_rules_as_agents_md_in_its_folder(self):
        self.run_codex(setup="with-skills")

        (seen,) = self.seen()
        self.assertEqual(seen["files"], ["AGENTS.md"])
        self.assertEqual(seen["agents_md"], LISP_RULES.read_text())

    def test_without_skills_never_sees_the_rules(self):
        self.run_codex(setup="without-skills")

        (seen,) = self.seen()
        self.assertIsNone(seen["agents_md"])
        run_folder = Path(seen["cwd"]).parent
        rules = LISP_RULES.read_text()
        for path in run_folder.rglob("*"):
            if path.is_file() and not path.is_symlink():
                self.assertNotIn(rules, path.read_text(errors="replace"), path)

    def test_prompt_is_the_same_as_opencodes(self):
        self.env["FAKE_OPENCODE_SOLUTION"] = str(WRONG)
        for setup in ("with-skills", "without-skills"):
            with self.subTest(setup=setup):
                self.run_codex(setup=setup, run_number="1")
                self.run_task("--records-dir", str(self.records / "opencode"), setup=setup, run_number="2")

                codex_prompt = self.seen()[-1]["argv"][-1]
                opencode_seen = [json.loads(line) for line in
                                 (Path(self.tmp.name) / "fake-opencode-seen.jsonl").read_text().splitlines()]
                self.assertEqual(codex_prompt, opencode_seen[-1]["argv"][-1])


class CodexContinueTest(CodexTestCase):
    def test_no_continue_when_every_file_prints_ok(self):
        self.run_codex()

        self.assertEqual(len(self.seen()), 1)
        self.assertFalse(self.result()["continue_sent"])

    def test_resumes_the_same_thread_once_with_the_same_settings_when_the_model_stops_early(self):
        self.env["FAKE_CODEX_SCENARIO"] = "stop-early"

        self.run_codex()

        first, second = self.seen()
        self.assertEqual(second["argv"][:2], ["exec", "resume"])
        self.assertEqual(second["argv"][2:-2], first["argv"][1:-1])
        self.assertEqual(second["argv"][-2], THREAD_ID)
        self.assertEqual(second["argv"][-1],
                         "Continue until every file is created and every .lisp file prints OK in lisp-check.")
        self.assertEqual(second["env"]["CODEX_HOME"], first["env"]["CODEX_HOME"])
        result = self.result()
        self.assertTrue(result["continue_sent"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["session_id"], THREAD_ID)

    def test_continue_is_sent_at_most_once(self):
        self.env["FAKE_CODEX_SCENARIO"] = "never-done"

        self.run_codex()

        self.assertEqual(len(self.seen()), 2)
        self.assertFalse(self.result()["passed"])


class CodexLimitTest(CodexTestCase):
    def test_hanging_codex_is_killed_at_the_wall_clock_limit(self):
        self.env["FAKE_CODEX_SCENARIO"] = "hang"
        start = time.monotonic()

        self.run_codex("--timeout", "2")

        self.assertLess(time.monotonic() - start, 60)
        result = self.result()
        self.assertEqual(result["limit_hit"], "wall_clock")
        self.assertFalse(result["passed"])
        self.assertFalse(result["continue_sent"])

    def test_endless_check_fix_rounds_stop_at_the_round_limit(self):
        self.env["FAKE_CODEX_SCENARIO"] = "endless-checks"

        completed = self.run_codex("--max-rounds", "5")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = self.result()
        self.assertEqual(result["limit_hit"], "rounds")
        self.assertLess(result["check_fix_rounds"], 10)
        self.assertFalse(result["passed"])


class CodexRecordTest(CodexTestCase):
    def test_saves_transcript_stderr_round_log_and_sources(self):
        self.env["FAKE_CODEX_SCENARIO"] = "crash"

        self.run_codex()

        record = self.record_dir()
        events = [json.loads(line) for line in (record / "transcript.jsonl").read_text().splitlines()]
        self.assertEqual(events[0], {"type": "thread.started", "thread_id": THREAD_ID})
        self.assertIn("fake-codex: crashed", (record / "codex.stderr.log").read_text())
        self.assertEqual(self.result()["codex_exit_code"], 1)

    def test_token_usage_is_summed_over_both_turns_and_cost_is_null(self):
        self.env["FAKE_CODEX_SCENARIO"] = "stop-early"

        self.run_codex()

        result = self.result()
        self.assertEqual(result["usage"], {"input_tokens": 4000, "cached_input_tokens": 1400,
                                           "output_tokens": 700, "reasoning_output_tokens": 150})
        self.assertEqual(result["total_tokens"], 4700)
        self.assertIsNone(result["cost_usd"])

    def test_one_turn_usage(self):
        self.run_codex()

        result = self.result()
        self.assertEqual(result["usage"], {"input_tokens": 1000, "cached_input_tokens": 400,
                                           "output_tokens": 200, "reasoning_output_tokens": 50})
        self.assertEqual(result["total_tokens"], 1200)

    def test_usage_is_null_when_codex_reports_none(self):
        self.env["FAKE_CODEX_SCENARIO"] = "crash"

        self.run_codex()

        result = self.result()
        self.assertIsNone(result["usage"])
        self.assertIsNone(result["total_tokens"])
        self.assertIsNone(result["cost_usd"])

    def test_opencode_records_have_no_usage(self):
        self.env["FAKE_OPENCODE_SOLUTION"] = str(WRONG)

        self.run_task()

        result = self.result()
        self.assertEqual(result["backend"], "opencode")
        self.assertIsNone(result["usage"])
        self.assertIsNone(result["cost_usd"])

    def test_round_log_is_saved(self):
        self.run_codex()

        self.assertEqual(len((self.record_dir() / "lisp-check.log").read_text().splitlines()), 3)
        self.assertEqual(self.result()["check_fix_rounds"], 3)


class LocatingCodexTest(CodexTestCase):
    def setUp(self):
        super().setUp()
        del self.env["CODEX_BIN"]
        self.env["PATH"] = os.pathsep.join(
            d for d in self.env["PATH"].split(os.pathsep) if not (Path(d) / "codex").exists())

    def test_uses_codex_on_path(self):
        path_dir = Path(self.tmp.name) / "path-bin"
        path_dir.mkdir()
        (path_dir / "codex").symlink_to(FAKE_CODEX)
        self.env["PATH"] = f"{path_dir}{os.pathsep}{self.env['PATH']}"
        self.env["CODEX_BUNDLED_BIN"] = str(Path(self.tmp.name) / "no-such-codex")

        completed = self.run_codex()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(self.seen()), 1)

    def test_falls_back_to_the_codex_bundled_with_the_chatgpt_app(self):
        self.env["CODEX_BUNDLED_BIN"] = str(FAKE_CODEX)

        completed = self.run_codex()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(self.seen()), 1)

    def test_fails_naming_codex_bin_when_no_codex_is_found(self):
        self.env["CODEX_BUNDLED_BIN"] = str(Path(self.tmp.name) / "no-such-codex")

        completed = self.run_codex()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("CODEX_BIN", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(self.record_dir().exists())
        self.assertFalse(self.run_root.exists())


if __name__ == "__main__":
    unittest.main()
