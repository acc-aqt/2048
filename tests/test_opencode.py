import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness.opencode import PINNED_VERSION, isolated_env


def pinned_opencode_installed():
    if not shutil.which("opencode"):
        return False
    result = subprocess.run(["opencode", "--version"], capture_output=True, text=True)
    return result.stdout.strip() == PINNED_VERSION


class IsolatedEnvTest(unittest.TestCase):
    def test_disables_claude_code_prompt_and_moves_every_opencode_dir(self):
        env = isolated_env(Path("/runs/r1/opencode"), base_env={"PATH": "/bin", "HOME": "/Users/me"})
        self.assertEqual(env["OPENCODE_DISABLE_CLAUDE_CODE_PROMPT"], "1")
        self.assertEqual(env["PATH"], "/bin")
        for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME",
                    "OPENCODE_CONFIG_DIR", "OPENCODE_TEST_HOME"):
            with self.subTest(key=key):
                self.assertTrue(env[key].startswith("/runs/r1/opencode/"), env[key])


@unittest.skipUnless(pinned_opencode_installed(), f"opencode {PINNED_VERSION} not installed")
class ResolvedConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.project = self.root / "project"
        (self.project / ".git").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def resolved_config(self, base_env):
        env = isolated_env(self.root / "opencode", base_env=base_env)
        result = subprocess.run(
            ["opencode", "debug", "config"],
            cwd=self.project,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_uses_repo_config_with_explicit_context_limit_and_ignores_global_config(self):
        global_dir = self.root / "user-config" / "opencode"
        global_dir.mkdir(parents=True)
        (global_dir / "opencode.json").write_text(json.dumps({"model": "global/should-not-load"}))
        base_env = dict(os.environ, XDG_CONFIG_HOME=str(self.root / "user-config"))

        config = self.resolved_config(base_env)

        self.assertEqual(config["model"], "local/qwen3")
        model = config["provider"]["local"]["models"]["qwen3"]
        self.assertEqual(model["limit"]["context"], 32768)

    def test_allows_tools_but_denies_subagents_web_questions_and_outside_folders(self):
        permission = self.resolved_config(dict(os.environ))["permission"]

        self.assertEqual(permission["*"], "allow")
        for tool in ("task", "webfetch", "websearch", "question", "skill", "external_directory"):
            with self.subTest(tool=tool):
                self.assertEqual(permission[tool], "deny")


if __name__ == "__main__":
    unittest.main()
