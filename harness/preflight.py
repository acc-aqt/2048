"""Preflight: prove lisp-check and the model work before a long run."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

LISP_CHECK = Path(__file__).resolve().parent.parent / "bin" / "lisp-check"

DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_MODEL = "qwen3-8b-32k"
DEFAULT_API_KEY = "ollama"
DEFAULT_TIMEOUT = "300"

BACKENDS = ("claude", "codex", "opencode")
CHATGPT_BUNDLED_CODEX = (
    "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
)
CODEX_NOT_FOUND = (
    "no Codex CLI found: not on PATH and not bundled in ChatGPT.app; "
    "set CODEX_BIN to the codex binary"
)

CORRECT_LISP = "(defun add1 (x)\n  (+ x 1))\n"
BROKEN_LISP = "(defun add1 (x)\n  (+ x 1)\n"

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command and return its output",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to run"}
            },
            "required": ["command"],
        },
    },
}


def check_tool_call(base_url, model, api_key, timeout):
    """Return None if the model answers with a valid bash tool call, else a reason."""
    url = base_url.rstrip("/") + "/chat/completions"
    request = urllib.request.Request(
        url,
        data=json.dumps(
            {
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "user", "content": "Run the shell command: lisp-check hello.lisp"}
                ],
                "tools": [BASH_TOOL],
                "tool_choice": "auto",
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        with error:
            detail = error.read().decode(errors="replace")
        return f"{url} returned HTTP {error.code}: {snippet(detail)}"
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        return f"could not reach {url}: {reason}"
    try:
        reply = json.loads(body)
    except json.JSONDecodeError:
        return f"{url} reply is not JSON: {snippet(body.decode(errors='replace'))}"
    return tool_call_problem(reply)


def tool_call_problem(reply):
    try:
        message = reply["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return f"reply has no choices[0].message: {snippet(reply)}"
    calls = message.get("tool_calls") or []
    if not calls:
        return f"model answered with no tool call; content: {snippet(message.get('content'))}"
    function = calls[0].get("function") or {}
    name = function.get("name")
    if name != "bash":
        return f"model called tool {name!r} instead of 'bash'"
    try:
        arguments = json.loads(function.get("arguments") or "")
    except json.JSONDecodeError:
        return f"tool call arguments are not valid JSON: {snippet(function.get('arguments'))}"
    command = arguments.get("command") if isinstance(arguments, dict) else None
    if not isinstance(command, str) or not command.strip():
        return f"tool call has no non-empty 'command' argument: {snippet(arguments)}"
    return None


def snippet(value, limit=500):
    text = value if isinstance(value, str) else json.dumps(value)
    return text if len(text) <= limit else text[:limit] + "..."


def check_lisp_file(run_dir, name, source, expected):
    """Return None if lisp-check prints `expected` (OK or FAIL) as last line, else a reason."""
    (run_dir / name).write_text(source)
    env = dict(os.environ, LISP_CHECK_LOG=str(run_dir / ".lisp-check.log"))
    result = subprocess.run(
        [str(LISP_CHECK), name],
        cwd=run_dir,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    lines = result.stdout.splitlines()
    last = lines[-1] if lines else ""
    expected_exit = 0 if expected == "OK" else 1
    if last != expected or result.returncode != expected_exit:
        output = " | ".join(lines + result.stderr.splitlines()) or "no output"
        return f"expected {expected} (exit {expected_exit}), got exit {result.returncode}: {output}"
    return None


def model_settings():
    return dict(
        base_url=os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL),
        model=os.environ.get("LLM_MODEL", DEFAULT_MODEL),
        api_key=os.environ.get("LLM_API_KEY", DEFAULT_API_KEY),
        timeout=float(os.environ.get("LLM_TIMEOUT", DEFAULT_TIMEOUT)),
    )


def run_status_command(command):
    """Run a login status command; return (result, None) or (None, reason)."""
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, capture_output=True, text=True
        )
    except OSError as error:
        return None, f"could not run {command[0]}: {error}"
    return result, None


def no_login_reason(command, result):
    output = " | ".join((result.stdout + result.stderr).splitlines()) or "no output"
    return (
        f"`{' '.join(command)}` does not report a login "
        f"(exit {result.returncode}): {snippet(output)}"
    )


def check_claude_login(claude):
    """Return None if `claude auth status` reports a login, else a reason. Sends no prompt."""
    command = [claude, "auth", "status", "--json"]
    result, problem = run_status_command(command)
    if problem:
        return problem
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError:
        status = None
    if isinstance(status, dict) and status.get("loggedIn") is True:
        return None
    return no_login_reason(command, result)


def find_codex():
    """CODEX_BIN, then `codex` on PATH, then the CLI bundled in ChatGPT.app; None if none."""
    if "CODEX_BIN" in os.environ:
        return os.environ["CODEX_BIN"]
    on_path = shutil.which("codex")
    if on_path:
        return on_path
    if os.access(CHATGPT_BUNDLED_CODEX, os.X_OK):
        return CHATGPT_BUNDLED_CODEX
    return None


def is_runnable(binary):
    return shutil.which(binary) is not None


def found_backends():
    """The backends whose CLI is installed, used when no --backend is given."""
    found = []
    if is_runnable(os.environ.get("CLAUDE_BIN", "claude")):
        found.append("claude")
    codex = find_codex()
    if codex is not None and is_runnable(codex):
        found.append("codex")
    if is_runnable(os.environ.get("OPENCODE_BIN", "opencode")):
        found.append("opencode")
    return found


def check_codex_login(codex):
    """Return None if `codex login status` succeeds, else a reason. Sends no prompt."""
    command = [codex, "login", "status"]
    result, problem = run_status_command(command)
    if problem:
        return problem
    if result.returncode == 0:
        return None
    return no_login_reason(command, result)


def check_opencode_model(skip_model):
    if skip_model:
        print("SKIP model tool call (skipped by --skip-model)")
        return True
    settings = model_settings()
    label = f"model {settings['model']} at {settings['base_url']} answers with a valid tool call"
    return report(label, check_tool_call(**settings))


def report(label, problem):
    if problem is None:
        print(f"PASS {label}")
    else:
        print(f"FAIL {label}: {problem}")
    return problem is None


def main(args):
    parser = argparse.ArgumentParser(
        prog="preflight",
        description="Check lisp-check and each backend before a run.",
    )
    parser.add_argument(
        "--skip-model", action="store_true", help="opencode: do not send a request to the model"
    )
    parser.add_argument(
        "--backend",
        action="append",
        choices=BACKENDS,
        help="backend to check (repeatable); default: every backend whose CLI is installed",
    )
    options = parser.parse_args(args)
    backends = options.backend or found_backends()

    results = []
    with tempfile.TemporaryDirectory(prefix="preflight-") as tmp:
        run_dir = Path(tmp).resolve()
        (run_dir / ".git").mkdir()
        results.append(report(
            "lisp-check prints OK on a correct file",
            check_lisp_file(run_dir, "correct.lisp", CORRECT_LISP, "OK"),
        ))
        results.append(report(
            "lisp-check prints FAIL on a broken file",
            check_lisp_file(run_dir, "broken.lisp", BROKEN_LISP, "FAIL"),
        ))

    if not backends:
        results.append(report(
            "a backend CLI is installed",
            "found none of claude, codex, opencode; pass --backend",
        ))

    if "claude" in backends:
        claude = os.environ.get("CLAUDE_BIN", "claude")
        results.append(report(f"Claude CLI {claude} is logged in", check_claude_login(claude)))

    if "codex" in backends:
        codex = find_codex()
        if codex is None:
            results.append(report("Codex CLI is logged in", CODEX_NOT_FOUND))
        else:
            results.append(report(f"Codex CLI {codex} is logged in", check_codex_login(codex)))

    if "opencode" in backends:
        results.append(check_opencode_model(options.skip_model))

    ok = all(results)
    print("preflight: OK" if ok else "preflight: FAIL")
    return 0 if ok else 1
