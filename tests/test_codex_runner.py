import json
import unittest
from pathlib import Path

from tests.test_runner import FIXTURES, RunnerTestCase, WRONG

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


if __name__ == "__main__":
    unittest.main()
