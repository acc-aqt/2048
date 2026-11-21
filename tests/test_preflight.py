import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from harness.preflight import check_tool_call
from tests.test_lisp_check import FAKE_DOCKER, docker_image_available

PREFLIGHT = Path(__file__).resolve().parent.parent / "bin" / "preflight"
FAKE_LOGIN_CLI = Path(__file__).resolve().parent / "fixtures" / "fake-login-cli"
FAKE_OPENCODE = Path(__file__).resolve().parent / "fixtures" / "fake-opencode"
CLAUDE_LOGGED_IN = '{"loggedIn": true, "authMethod": "claude.ai"}\n'
CLAUDE_LOGGED_OUT = '{"loggedIn": false, "authMethod": "none"}\n'


def tool_call_reply(name="bash", arguments='{"command": "lisp-check hello.lisp"}'):
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": name, "arguments": arguments},
                        }
                    ],
                },
            }
        ]
    }


class FakeModelServer:
    """OpenAI-compatible stand-in that records requests and returns a canned reply."""

    def __init__(self, status=200, body=None):
        self.status = status
        self.body = body
        self.requests = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                server.requests.append(
                    {
                        "path": self.path,
                        "headers": dict(self.headers),
                        "json": json.loads(self.rfile.read(length)),
                    }
                )
                payload = server.body
                if not isinstance(payload, bytes):
                    payload = json.dumps(payload).encode()
                self.send_response(server.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


class CheckToolCallTest(unittest.TestCase):
    def check(self, server, **kwargs):
        options = dict(base_url=server.base_url, model="m", api_key="k", timeout=5)
        options.update(kwargs)
        return check_tool_call(**options)

    def test_valid_bash_tool_call_passes(self):
        with FakeModelServer(body=tool_call_reply()) as server:
            self.assertIsNone(self.check(server))

    def test_sends_openai_chat_request_with_model_key_and_bash_tool(self):
        with FakeModelServer(body=tool_call_reply()) as server:
            self.check(server, base_url=server.base_url + "/", model="qwen", api_key="sk-1")
        [request] = server.requests
        self.assertEqual(request["path"], "/v1/chat/completions")
        self.assertEqual(request["headers"]["Authorization"], "Bearer sk-1")
        self.assertEqual(request["json"]["model"], "qwen")
        self.assertEqual(request["json"]["tools"][0]["function"]["name"], "bash")

    def test_plain_text_answer_fails_with_the_text_in_the_reason(self):
        reply = {"choices": [{"message": {"role": "assistant", "content": "I would run lisp-check"}}]}
        with FakeModelServer(body=reply) as server:
            reason = self.check(server)
        self.assertIn("no tool call", reason)
        self.assertIn("I would run lisp-check", reason)

    def test_invalid_tool_calls_fail_with_a_reason(self):
        cases = [
            (tool_call_reply(name="shell"), "'shell'"),
            (tool_call_reply(arguments="{not json"), "not valid JSON"),
            (tool_call_reply(arguments='{"cmd": "ls"}'), "command"),
            (tool_call_reply(arguments='{"command": ""}'), "command"),
        ]
        for reply, expected in cases:
            with self.subTest(expected=expected):
                with FakeModelServer(body=reply) as server:
                    reason = self.check(server)
                self.assertIsNotNone(reason)
                self.assertIn(expected, reason)

    def test_http_error_fails_with_status_and_body(self):
        with FakeModelServer(status=404, body={"error": "model 'm' not found"}) as server:
            reason = self.check(server)
        self.assertIn("404", reason)
        self.assertIn("model 'm' not found", reason)

    def test_unexpected_reply_bodies_fail_with_a_reason(self):
        for body, expected in [(b"<html>gateway</html>", "not JSON"), ({"object": "list"}, "choices")]:
            with self.subTest(expected=expected):
                with FakeModelServer(body=body) as server:
                    reason = self.check(server)
                self.assertIn(expected, reason)

    def test_unreachable_endpoint_fails_with_the_url(self):
        with FakeModelServer(body={}) as server:
            url = server.base_url
        reason = check_tool_call(base_url=url, model="m", api_key="k", timeout=5)
        self.assertIn("could not reach", reason)
        self.assertIn(url, reason)


class PreflightCommandTest(unittest.TestCase):
    def setUp(self):
        self.env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("LISP_CHECK_", "LLM_", "FAKE_DOCKER_", "FAKE_CLI_"))
            and k not in ("CLAUDE_BIN", "CODEX_BIN", "OPENCODE_BIN")
        }
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.args_log = self.tmp / "cli-args.jsonl"

    def run_preflight(self, *args):
        return subprocess.run(
            [str(PREFLIGHT), *args], env=self.env, capture_output=True, text=True
        )

    def use_fake_docker(self, stdout="", stderr="", exit=0):
        self.env.update(
            LISP_CHECK_DOCKER=str(FAKE_DOCKER),
            FAKE_DOCKER_STDOUT=stdout,
            FAKE_DOCKER_STDERR=stderr,
            FAKE_DOCKER_EXIT=str(exit),
        )

    def use_fake_cli(self, name, stdout="", stderr="", exit=0):
        self.env.update(
            {name: str(FAKE_LOGIN_CLI)},
            FAKE_CLI_ARGS=str(self.args_log),
            FAKE_CLI_STDOUT=stdout,
            FAKE_CLI_STDERR=stderr,
            FAKE_CLI_EXIT=str(exit),
        )

    def cli_calls(self):
        if not self.args_log.exists():
            return []
        return [json.loads(line)[1:] for line in self.args_log.read_text().splitlines()]

    def test_claude_backend_passes_when_logged_in_without_a_model_call(self):
        self.use_fake_docker(stdout="OK\n", exit=0)
        self.use_fake_cli("CLAUDE_BIN", stdout=CLAUDE_LOGGED_IN)
        result = self.run_preflight("--backend", "claude")
        self.assertRegex(result.stdout, r"(?m)^PASS .*Claude.*logged in")
        self.assertEqual(self.cli_calls(), [["auth", "status", "--json"]])
        self.assertNotIn("tool call", result.stdout)

    def test_claude_backend_fails_when_logged_out(self):
        self.use_fake_docker(stdout="OK\n", exit=0)
        self.use_fake_cli("CLAUDE_BIN", stdout=CLAUDE_LOGGED_OUT, exit=1)
        result = self.run_preflight("--backend", "claude")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"(?m)^FAIL .*Claude.*\"loggedIn\": false")

    def test_claude_backend_fails_when_the_binary_is_missing(self):
        self.use_fake_docker(stdout="OK\n", exit=0)
        self.env["CLAUDE_BIN"] = str(self.tmp / "no-such-claude")
        result = self.run_preflight("--backend", "claude")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"(?m)^FAIL .*Claude.*no-such-claude")

    def test_codex_backend_passes_when_logged_in_without_a_model_call(self):
        self.use_fake_docker(stdout="OK\n", exit=0)
        self.use_fake_cli("CODEX_BIN", stdout="Logged in using ChatGPT\n")
        result = self.run_preflight("--backend", "codex")
        self.assertRegex(result.stdout, r"(?m)^PASS .*Codex.*logged in")
        self.assertEqual(self.cli_calls(), [["login", "status"]])
        self.assertNotIn("tool call", result.stdout)

    def test_codex_backend_fails_when_logged_out(self):
        self.use_fake_docker(stdout="OK\n", exit=0)
        self.use_fake_cli("CODEX_BIN", stderr="Not logged in\n", exit=1)
        result = self.run_preflight("--backend", "codex")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"(?m)^FAIL .*Codex.*Not logged in")

    def test_codex_backend_finds_codex_on_path_without_codex_bin(self):
        self.use_fake_docker(stdout="OK\n", exit=0)
        self.use_fake_cli("CODEX_BIN", stdout="Logged in using ChatGPT\n")
        del self.env["CODEX_BIN"]
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "codex").symlink_to(FAKE_LOGIN_CLI)
        self.env["PATH"] = f"{bin_dir}{os.pathsep}{self.env['PATH']}"
        result = self.run_preflight("--backend", "codex")
        self.assertRegex(result.stdout, rf"(?m)^PASS .*Codex.*{bin_dir / 'codex'}")
        self.assertEqual(self.cli_calls(), [["login", "status"]])

    def test_without_backend_checks_the_claude_and_codex_clis_it_finds(self):
        self.use_fake_docker(stdout="OK\n", exit=0)
        self.use_fake_cli("CLAUDE_BIN", stdout=CLAUDE_LOGGED_IN)
        self.env["CODEX_BIN"] = str(FAKE_LOGIN_CLI)
        self.env["OPENCODE_BIN"] = str(self.tmp / "no-such-opencode")
        result = self.run_preflight()
        self.assertRegex(result.stdout, r"(?m)^PASS .*Claude")
        self.assertRegex(result.stdout, r"(?m)^PASS .*Codex")
        self.assertNotIn("tool call", result.stdout)

    def test_without_backend_checks_opencode_when_only_opencode_is_found(self):
        self.use_fake_docker(stdout="OK\n", exit=0)
        self.env.update(
            CLAUDE_BIN=str(self.tmp / "no-such-claude"),
            CODEX_BIN=str(self.tmp / "no-such-codex"),
            OPENCODE_BIN=str(FAKE_OPENCODE),
        )
        result = self.run_preflight("--skip-model")
        self.assertIn("SKIP model tool call", result.stdout)
        self.assertNotIn("Claude", result.stdout)
        self.assertNotIn("Codex", result.stdout)

    def test_docker_failure_is_reported_with_its_reason(self):
        self.use_fake_docker(stderr="Unable to find image 'nope:latest'\n", exit=125)
        result = self.run_preflight("--backend", "opencode", "--skip-model")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL", result.stdout)
        self.assertIn("Unable to find image 'nope:latest'", result.stdout)

    def test_lisp_check_that_never_fails_is_caught(self):
        self.use_fake_docker(stdout="OK\n", exit=0)
        result = self.run_preflight("--backend", "opencode", "--skip-model")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"FAIL .*broken")

    def test_model_failure_is_reported_with_its_reason(self):
        self.use_fake_docker(stdout="OK\n", exit=0)
        reply = {"choices": [{"message": {"role": "assistant", "content": "no tools today"}}]}
        with FakeModelServer(body=reply) as server:
            self.env["LLM_BASE_URL"] = server.base_url
            result = self.run_preflight("--backend", "opencode")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"FAIL .*tool call.*no tools today")

    @unittest.skipUnless(docker_image_available(), "lisp-skills-allegro image not available")
    def test_passes_with_working_lisp_check_and_model(self):
        with FakeModelServer(body=tool_call_reply()) as server:
            self.env.update(LLM_BASE_URL=server.base_url, LLM_MODEL="qwen", LLM_API_KEY="k")
            result = self.run_preflight("--backend", "opencode")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotRegex(result.stdout, r"(?m)^FAIL ")
        self.assertEqual(server.requests[0]["json"]["model"], "qwen")

    @unittest.skipUnless(docker_image_available(), "lisp-skills-allegro image not available")
    def test_skip_model_sends_no_request(self):
        self.env["LLM_BASE_URL"] = "http://127.0.0.1:9/v1"
        result = self.run_preflight("--backend", "opencode", "--skip-model")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("skipped", result.stdout)


if __name__ == "__main__":
    unittest.main()
