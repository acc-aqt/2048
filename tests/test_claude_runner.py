import json
import os
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
                     self.records, self.run_root, Path.home()):
            self.assertIn(str(path), filesystem["denyRead"])
        for path in (REPO / "bin", REPO / "harness"):
            self.assertNotIn(str(path), filesystem["denyRead"])

    def test_shell_can_still_run_lisp_check(self):
        self.run_claude()

        (seen,) = self.seen()
        filesystem = seen["settings"]["sandbox"]["filesystem"]
        run_folder = Path(seen["cwd"]).parent
        round_log_dir = Path(seen["env"]["LISP_CHECK_LOG"]).parent
        self.assertEqual(set(filesystem["allowRead"]),
                         {seen["cwd"], str(run_folder / "bin"), str(round_log_dir), str(REPO),
                          str(Path.home() / ".docker")})
        self.assertEqual(filesystem["allowWrite"], [str(round_log_dir)])
        socket = Path(self.tmp.name).resolve() / "docker.sock"
        self.assertEqual(seen["settings"]["sandbox"]["network"], {"allowUnixSockets": [str(socket)]})


if __name__ == "__main__":
    unittest.main()
