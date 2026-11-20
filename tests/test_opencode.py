import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness.opencode import CONFIG_FILE, PINNED_VERSION, isolated_env, write_run_config
from harness.setups import LISP_RULES


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

    def resolved_config(self, base_env, config_file=CONFIG_FILE):
        env = isolated_env(self.root / "opencode", base_env=base_env, config_file=config_file)
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

    def test_run_config_with_rules_loads_them_as_instructions(self):
        config_file = write_run_config(self.root / "opencode", rules_file=LISP_RULES)

        config = self.resolved_config(dict(os.environ), config_file=config_file)

        (instruction,) = config["instructions"]
        self.assertEqual(Path(instruction).read_text(), LISP_RULES.read_text())
        self.assertEqual(config["model"], "local/qwen3")

    def test_litellm_endpoint_and_model_alias_come_from_env_only(self):
        # `opencode debug config` masks apiKey as "***" whether set or not, so it can't be checked here.
        base_env = dict(
            os.environ,
            LLM_BASE_URL="https://litellm.example.internal/v1",
            LLM_API_KEY="sk-litellm-test",
            LLM_MODEL="qwen3-8b-fp8",
        )

        config = self.resolved_config(base_env)

        provider = config["provider"]["local"]
        self.assertEqual(provider["options"]["baseURL"], "https://litellm.example.internal/v1")
        self.assertEqual(provider["models"]["qwen3"]["id"], "qwen3-8b-fp8")


if __name__ == "__main__":
    unittest.main()
