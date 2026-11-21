import json
import unittest
from pathlib import Path

from tests.test_runner import FIXTURES, LISP_RULES, RunnerTestCase, WRONG

FAKE_CODEX = FIXTURES / "fake-codex"


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
        overrides = config_overrides(seen["argv"])
        self.assertIn('default_permissions="harness"', overrides)
        (filesystem,) = [o for o in overrides if o.startswith("permissions.harness.filesystem=")]
        round_log_dir = Path(seen["env"]["LISP_CHECK_LOG"]).parent
        self.assertEqual(filesystem, 'permissions.harness.filesystem='
                                     f'{{":root"="read", ":project_roots"="write", "{round_log_dir}"="write"}}')
        self.assertFalse(round_log_dir.is_relative_to(seen["cwd"]))
        self.assertNotEqual(round_log_dir, Path(seen["cwd"]).parent)

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
                self.run_task(setup=setup, run_number="2")

                codex_prompt = self.seen()[-1]["argv"][-1]
                opencode_seen = [json.loads(line) for line in
                                 (Path(self.tmp.name) / "fake-opencode-seen.jsonl").read_text().splitlines()]
                self.assertEqual(codex_prompt, opencode_seen[-1]["argv"][-1])


if __name__ == "__main__":
    unittest.main()
