import json
import os
import time
import unittest
from pathlib import Path

from tests.test_runner import FIXTURES, LISP_RULES, RunnerTestCase, WRONG

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
        self.env.update(CLAUDE_MODEL="from-env", CLAUDE_EFFORT="medium")

        self.run_claude("--model", "sonnet", "--reasoning-effort", "high")

        (seen,) = self.seen()
        self.assertEqual(option(seen["argv"], "--model"), "sonnet")
        self.assertEqual(option(seen["argv"], "--effort"), "high")
        self.assertEqual(seen["env"]["CLAUDE_CODE_EFFORT_LEVEL"], "high")
        result = self.result()
        self.assertEqual((result["model"], result["reasoning_effort"]), ("sonnet", "high"))

    def test_model_and_effort_can_be_overridden_by_environment(self):
        self.env.update(CLAUDE_MODEL="from-env", CLAUDE_EFFORT="medium")

        self.run_claude()

        (seen,) = self.seen()
        self.assertEqual(option(seen["argv"], "--model"), "from-env")
        self.assertEqual(option(seen["argv"], "--effort"), "medium")
        self.assertEqual(seen["env"]["CLAUDE_CODE_EFFORT_LEVEL"], "medium")

    def test_opencode_rejects_model_flags_naming_both_backends(self):
        completed = self.run_task("--reasoning-effort", "low")

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--backend codex or claude", completed.stderr)


if __name__ == "__main__":
    unittest.main()
