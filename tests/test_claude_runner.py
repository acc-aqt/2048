import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from tests.test_runner import FIXTURES, LISP_RULES, REPO, RunnerTestCase, WRONG

FAKE_CLAUDE = FIXTURES / "fake-claude"
SESSION_ID = "6f1c2d3e-0000-4000-8000-00000000fake"


class ClaudeTestCase(RunnerTestCase):
    """Runs bin/run-task --backend claude with the fake claude; no request ever reaches a model."""

    def setUp(self):
        super().setUp()
        root = Path(self.tmp.name).resolve()
        self.seen_file = root / "fake-claude-seen.jsonl"
        for key in [k for k in self.env if k.startswith("CLAUDE_")]:
            del self.env[key]
        self.env.update(
            CLAUDE_BIN=str(FAKE_CLAUDE),
            FAKE_CLAUDE_RECORD=str(self.seen_file),
            FAKE_CLAUDE_SOLUTION=str(WRONG),
            DOCKER_HOST=f"unix://{root / 'docker.sock'}",
        )
        self.use_fake_docker_printing_ok()

    def run_claude(self, *args, **kwargs):
        return self.run_task("--backend", "claude", *args, **kwargs)


def option(argv, name):
    return argv[argv.index(name) + 1]


class ClaudeModelTest(ClaudeTestCase):
    def test_defaults_to_haiku_at_low_effort(self):
        completed = self.run_claude()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        (seen,) = self.seen()
        argv = seen["argv"]
        self.assertEqual(argv[0], "-p")
        self.assertEqual(option(argv, "--output-format"), "stream-json")
        self.assertIn("--verbose", argv)
        self.assertEqual(option(argv, "--model"), "haiku")
        self.assertEqual(option(argv, "--effort"), "low")
        self.assertEqual(seen["env"]["CLAUDE_CODE_EFFORT_LEVEL"], "low")
        result = self.result()
        self.assertEqual(result["backend"], "claude")
        self.assertEqual(result["model"], "haiku")
        self.assertEqual(result["reasoning_effort"], "low")

    def test_model_and_effort_can_be_overridden_by_flags(self):
        self.env.update(CLAUDE_MODEL="from-env", CLAUDE_REASONING_EFFORT="medium")

        self.run_claude("--model", "sonnet", "--reasoning-effort", "high")

        (seen,) = self.seen()
        self.assertEqual(option(seen["argv"], "--model"), "sonnet")
        self.assertEqual(option(seen["argv"], "--effort"), "high")
        self.assertEqual(seen["env"]["CLAUDE_CODE_EFFORT_LEVEL"], "high")
        result = self.result()
        self.assertEqual((result["model"], result["reasoning_effort"]), ("sonnet", "high"))

    def test_model_and_effort_can_be_overridden_by_environment(self):
        self.env.update(CLAUDE_MODEL="from-env", CLAUDE_REASONING_EFFORT="medium")

        self.run_claude()

        (seen,) = self.seen()
        self.assertEqual(option(seen["argv"], "--model"), "from-env")
        self.assertEqual(option(seen["argv"], "--effort"), "medium")
        self.assertEqual(seen["env"]["CLAUDE_CODE_EFFORT_LEVEL"], "medium")

    def test_opencode_rejects_model_flags_naming_both_backends(self):
        completed = self.run_task("--reasoning-effort", "low")

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--backend codex or claude", completed.stderr)

    def test_effort_exported_by_a_parent_claude_code_session_is_ignored(self):
        self.env.update(CLAUDE_EFFORT="medium", CLAUDECODE="1", CLAUDE_CODE_SESSION_ID="parent",
                        CLAUDE_CODE_EFFORT_LEVEL="max", CLAUDE_CONFIG_DIR="/somewhere/claude-config")

        self.run_claude()

        (seen,) = self.seen()
        self.assertEqual(option(seen["argv"], "--effort"), "low")
        self.assertEqual(seen["env"]["CLAUDE_CODE_EFFORT_LEVEL"], "low")
        self.assertEqual(seen["env"]["CLAUDE_CONFIG_DIR"], "/somewhere/claude-config")
        self.assertEqual(seen["parent_session_vars"], [])

    def test_api_key_provider_and_model_variables_are_dropped_so_the_subscription_login_is_used(self):
        self.env.update(ANTHROPIC_API_KEY="sk-ant-test", ANTHROPIC_AUTH_TOKEN="token",
                        ANTHROPIC_BASE_URL="https://proxy.example", ANTHROPIC_MODEL="claude-opus-5-5",
                        ANTHROPIC_DEFAULT_HAIKU_MODEL="claude-opus-5-5", ANTHROPIC_CUSTOM_HEADERS="X-A: b")

        self.run_claude()

        (seen,) = self.seen()
        self.assertEqual(seen["anthropic_vars"], [])
        self.assertEqual(option(seen["argv"], "--model"), "haiku")


class ClaudeIsolationTest(ClaudeTestCase):
    def test_runs_hands_off_in_an_empty_git_folder_in_the_run_root(self):
        self.run_claude()

        (seen,) = self.seen()
        self.assertEqual(seen["files"], [])
        self.assertTrue(Path(seen["cwd"]).is_relative_to(self.run_root))
        self.assertTrue(seen["stdin_is_devnull"])
        self.assertEqual(option(seen["argv"], "--permission-mode"), "dontAsk")
        self.assertEqual(seen["settings"]["permissions"]["defaultMode"], "dontAsk")

    def test_user_settings_instructions_mcp_servers_and_memory_are_left_out(self):
        self.run_claude()

        (seen,) = self.seen()
        argv = seen["argv"]
        self.assertEqual(option(argv, "--setting-sources"), "project")
        self.assertIn("--strict-mcp-config", argv)
        settings_file = Path(option(argv, "--settings"))
        self.assertTrue(settings_file.is_relative_to(Path(seen["cwd"]).parent))
        self.assertFalse(settings_file.is_relative_to(seen["cwd"]))
        settings = seen["settings"]
        self.assertIn(str(Path.home() / ".claude" / "CLAUDE.md"), settings["claudeMdExcludes"])
        self.assertIs(settings["autoMemoryEnabled"], False)
        self.assertIs(settings["disableAllHooks"], True)
        self.assertEqual(seen["env"]["CLAUDE_CODE_DISABLE_AUTO_MEMORY"], "1")

    def test_skills_plugins_subagents_and_web_tools_are_off_in_both_setups(self):
        for number, setup in enumerate(("with-skills", "without-skills"), start=1):
            with self.subTest(setup=setup):
                self.run_claude(setup=setup, run_number=str(number))

                seen = self.seen()[-1]
                argv = seen["argv"]
                self.assertIn("--disable-slash-commands", argv)
                self.assertEqual(option(argv, "--tools"), "Bash,Edit,Read,Write")
                self.assertEqual(option(argv, "--disallowedTools"), "Agent,WebFetch,WebSearch")
                plugins = seen["settings"]["enabledPlugins"]
                self.assertTrue(plugins)
                self.assertFalse(any(plugins.values()))


class ClaudeConfinementTest(ClaudeTestCase):
    def test_file_tools_cannot_read_outside_the_model_folder(self):
        self.run_claude()

        (seen,) = self.seen()
        permissions = seen["settings"]["permissions"]
        self.assertIs(permissions["blockReadsOutsideWorkingDirectories"], True)
        self.assertEqual(permissions["allow"], [f"Edit(/{seen['cwd']}/**)", "Bash"])
        self.assertEqual(permissions["disableBypassPermissionsMode"], "disable")

    def test_shell_runs_in_a_strict_sandbox(self):
        self.run_claude()

        sandbox = self.seen()[0]["settings"]["sandbox"]
        self.assertIs(sandbox["enabled"], True)
        self.assertIs(sandbox["failIfUnavailable"], True)
        self.assertIs(sandbox["allowUnsandboxedCommands"], False)

    def test_shell_cannot_read_hidden_tests_reference_records_or_other_runs(self):
        self.run_claude()

        (seen,) = self.seen()
        filesystem = seen["settings"]["sandbox"]["filesystem"]
        for path in (REPO / "tasks", REPO / "reference", REPO / "runs", REPO / ".git", REPO / "tests",
                     self.records, self.run_root, Path.home(), Path("/tmp").resolve(),
                     Path(tempfile.gettempdir()).resolve()):
            self.assertIn(str(path), filesystem["denyRead"])
        for path in (REPO / "bin", REPO / "harness"):
            self.assertNotIn(str(path), filesystem["denyRead"])

    def test_shell_can_still_run_lisp_check(self):
        self.run_claude()

        (seen,) = self.seen()
        filesystem = seen["settings"]["sandbox"]["filesystem"]
        run_folder = Path(seen["cwd"]).parent
        round_log_dir = Path(seen["env"]["LISP_CHECK_LOG"]).parent
        tmp_dir = str(run_folder / "agent-tmp")
        self.assertEqual(set(filesystem["allowRead"]),
                         {seen["cwd"], str(run_folder / "bin"), str(round_log_dir), str(REPO),
                          str(Path.home() / ".docker"), tmp_dir})
        self.assertEqual(filesystem["allowWrite"], [str(round_log_dir), tmp_dir])
        socket = Path(self.tmp.name).resolve() / "docker.sock"
        self.assertEqual(seen["settings"]["sandbox"]["network"], {"allowUnixSockets": [str(socket)]})

    def test_claude_code_gets_its_own_temp_folder_instead_of_the_one_every_claude_session_shares(self):
        self.env["CLAUDE_CODE_TMPDIR"] = "/tmp"

        self.run_claude()

        (seen,) = self.seen()
        tmp_dir = Path(seen["cwd"]).parent / "agent-tmp"
        self.assertEqual(seen["env"]["CLAUDE_CODE_TMPDIR"], str(tmp_dir))
        self.assertTrue(tmp_dir.is_dir())
        self.assertFalse(tmp_dir.is_relative_to(seen["cwd"]))


class ClaudeSetupTest(ClaudeTestCase):
    def test_with_skills_finds_the_pinned_rules_as_claude_md_in_its_folder(self):
        self.run_claude(setup="with-skills")

        (seen,) = self.seen()
        self.assertEqual(seen["files"], ["CLAUDE.md"])
        self.assertEqual(seen["claude_md"], LISP_RULES.read_text())

    def test_without_skills_never_sees_the_rules(self):
        self.run_claude(setup="without-skills")

        (seen,) = self.seen()
        self.assertIsNone(seen["claude_md"])
        run_folder = Path(seen["cwd"]).parent
        rules = LISP_RULES.read_text()
        for path in run_folder.rglob("*"):
            if path.is_file() and not path.is_symlink():
                self.assertNotIn(rules, path.read_text(errors="replace"), path)

    def test_prompt_is_the_same_as_opencodes(self):
        self.env["FAKE_OPENCODE_SOLUTION"] = str(WRONG)
        for setup in ("with-skills", "without-skills"):
            with self.subTest(setup=setup):
                self.run_claude(setup=setup, run_number="1")
                self.run_task("--records-dir", str(self.records / "opencode"), setup=setup, run_number="2")

                claude_prompt = self.seen()[-1]["argv"][-1]
                opencode_seen = [json.loads(line) for line in
                                 (Path(self.tmp.name) / "fake-opencode-seen.jsonl").read_text().splitlines()]
                self.assertEqual(claude_prompt, opencode_seen[-1]["argv"][-1])


class ClaudeContinueTest(ClaudeTestCase):
    def test_no_continue_when_every_file_prints_ok(self):
        self.run_claude()

        self.assertEqual(len(self.seen()), 1)
        self.assertFalse(self.result()["continue_sent"])

    def test_resumes_the_same_session_once_with_the_same_settings_when_the_model_stops_early(self):
        self.env["FAKE_CLAUDE_SCENARIO"] = "stop-early"

        self.run_claude()

        first, second = self.seen()
        self.assertEqual(second["argv"][-3:], [
            "--resume", SESSION_ID,
            "Continue until every file is created and every .lisp file prints OK in lisp-check."])
        budget = first["argv"].index("--max-budget-usd")
        self.assertEqual(second["argv"][:budget], first["argv"][:budget])
        self.assertEqual(second["settings"], first["settings"])
        result = self.result()
        self.assertTrue(result["continue_sent"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["session_id"], SESSION_ID)

    def test_continue_is_sent_at_most_once(self):
        self.env["FAKE_CLAUDE_SCENARIO"] = "never-done"

        self.run_claude()

        self.assertEqual(len(self.seen()), 2)
        self.assertFalse(self.result()["passed"])


class ClaudeLimitTest(ClaudeTestCase):
    def test_hanging_claude_is_killed_at_the_wall_clock_limit(self):
        self.env["FAKE_CLAUDE_SCENARIO"] = "hang"
        start = time.monotonic()

        self.run_claude("--timeout", "2")

        self.assertLess(time.monotonic() - start, 60)
        result = self.result()
        self.assertEqual(result["limit_hit"], "wall_clock")
        self.assertFalse(result["passed"])
        self.assertFalse(result["continue_sent"])

    def test_endless_check_fix_rounds_stop_at_the_round_limit(self):
        self.env["FAKE_CLAUDE_SCENARIO"] = "endless-checks"

        completed = self.run_claude("--max-rounds", "5")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = self.result()
        self.assertEqual(result["limit_hit"], "rounds")
        self.assertLess(result["check_fix_rounds"], 10)
        self.assertFalse(result["passed"])


class ClaudeBudgetTest(ClaudeTestCase):
    def test_each_run_is_capped_at_5_dollars_by_default(self):
        self.run_claude()

        self.assertEqual(option(self.seen()[0]["argv"], "--max-budget-usd"), "5")
        self.assertEqual(self.result()["budget_usd"], 5)

    def test_budget_can_be_overridden(self):
        self.run_claude("--max-budget-usd", "0.5")

        self.assertEqual(option(self.seen()[0]["argv"], "--max-budget-usd"), "0.5")
        self.assertEqual(self.result()["budget_usd"], 0.5)

    def test_other_backends_reject_the_budget(self):
        completed = self.run_task("--max-budget-usd", "1")

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--max-budget-usd is for --backend claude", completed.stderr)

    def test_the_resumed_turn_gets_what_is_left_of_the_budget(self):
        self.env["FAKE_CLAUDE_SCENARIO"] = "stop-early"

        self.run_claude("--max-budget-usd", "2")

        first, second = self.seen()
        self.assertEqual(option(first["argv"], "--max-budget-usd"), "2")
        self.assertEqual(option(second["argv"], "--max-budget-usd"), "1.75")

    def test_budget_stop_is_its_own_limit_and_fails_the_run(self):
        self.env["FAKE_CLAUDE_SCENARIO"] = "budget"

        self.run_claude()

        self.assertEqual(len(self.seen()), 1)
        result = self.result()
        self.assertEqual(result["limit_hit"], "budget")
        self.assertFalse(result["continue_sent"])
        self.assertFalse(result["passed"])


class ClaudeRecordTest(ClaudeTestCase):
    def test_saves_transcript_stderr_round_log_and_sources(self):
        self.env["FAKE_CLAUDE_SCENARIO"] = "crash"

        self.run_claude()

        record = self.record_dir()
        events = [json.loads(line) for line in (record / "transcript.jsonl").read_text().splitlines()]
        self.assertEqual((events[0]["type"], events[0]["session_id"]), ("system", SESSION_ID))
        self.assertIn("fake-claude: crashed", (record / "claude.stderr.log").read_text())
        result = self.result()
        self.assertEqual(result["claude_exit_code"], 1)
        self.assertEqual(result["session_id"], SESSION_ID)

    def test_round_log_and_sources_are_saved(self):
        self.run_claude()

        record = self.record_dir()
        self.assertEqual(len((record / "lisp-check.log").read_text().splitlines()), 3)
        self.assertTrue((record / "src" / "slide-row.lisp").is_file())

    def test_one_turn_usage_and_cost(self):
        self.run_claude()

        result = self.result()
        self.assertEqual(result["usage"], {"input_tokens": 100, "output_tokens": 300,
                                           "cache_read_input_tokens": 5000, "cache_creation_input_tokens": 2000})
        self.assertEqual(result["total_tokens"], 7400)
        self.assertEqual(result["cost_usd"], 0.25)

    def test_usage_and_cost_cover_both_turns_without_counting_the_first_twice(self):
        self.env["FAKE_CLAUDE_SCENARIO"] = "stop-early"

        self.run_claude()

        result = self.result()
        self.assertEqual(result["usage"], {"input_tokens": 160, "output_tokens": 520,
                                           "cache_read_input_tokens": 13000, "cache_creation_input_tokens": 3000})
        self.assertEqual(result["total_tokens"], 16680)
        self.assertEqual(result["cost_usd"], 0.75)

    def test_usage_survives_a_budget_stop(self):
        self.env["FAKE_CLAUDE_SCENARIO"] = "budget"

        self.run_claude()

        result = self.result()
        self.assertEqual(result["total_tokens"], 7400)
        self.assertEqual(result["cost_usd"], 0.25)

    def test_usage_is_null_when_claude_reports_none(self):
        self.env["FAKE_CLAUDE_SCENARIO"] = "crash"

        self.run_claude()

        result = self.result()
        self.assertIsNone(result["usage"])
        self.assertIsNone(result["total_tokens"])
        self.assertIsNone(result["cost_usd"])


class ClaudeRulesFileTest(ClaudeTestCase):
    def test_neither_tools_nor_shell_can_change_the_rules_files(self):
        self.run_claude(setup="with-skills")

        (seen,) = self.seen()
        work = Path(seen["cwd"])
        rules_files = [work / "CLAUDE.md", work / "AGENTS.md"]
        self.assertEqual(seen["settings"]["sandbox"]["filesystem"]["denyWrite"], [str(p) for p in rules_files])
        self.assertEqual(seen["settings"]["permissions"]["deny"], [f"Edit(/{p})" for p in rules_files])

    def test_the_rules_file_stays_readable(self):
        self.run_claude(setup="with-skills")

        (seen,) = self.seen()
        filesystem = seen["settings"]["sandbox"]["filesystem"]
        self.assertNotIn(str(Path(seen["cwd"]) / "CLAUDE.md"), filesystem["denyRead"])
        self.assertFalse(any(rule.startswith("Read(") for rule in seen["settings"]["permissions"]["deny"]))


class LocatingClaudeTest(ClaudeTestCase):
    def setUp(self):
        super().setUp()
        del self.env["CLAUDE_BIN"]
        self.env["PATH"] = os.pathsep.join(
            d for d in self.env["PATH"].split(os.pathsep) if not (Path(d) / "claude").exists())

    def test_uses_claude_on_path(self):
        path_dir = Path(self.tmp.name) / "path-bin"
        path_dir.mkdir()
        (path_dir / "claude").symlink_to(FAKE_CLAUDE)
        self.env["PATH"] = f"{path_dir}{os.pathsep}{self.env['PATH']}"

        completed = self.run_claude()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(self.seen()), 1)

    def test_fails_naming_claude_bin_when_no_claude_is_found(self):
        completed = self.run_claude()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("CLAUDE_BIN", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(self.record_dir().exists())
        self.assertFalse(self.run_root.exists())


if __name__ == "__main__":
    unittest.main()
