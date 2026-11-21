"""Running the Codex CLI isolated from the user's own Codex setup."""

import os
import shutil
import subprocess
from pathlib import Path

DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_EFFORT = "low"
BUNDLED_BIN = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
PERMISSIONS_PROFILE = "harness"
DOCKER_QUERY_TIMEOUT = 30


class CodexNotFound(Exception):
    pass


def find_codex():
    """$CODEX_BIN, else `codex` on PATH, else the Codex CLI bundled with the ChatGPT app."""
    if os.environ.get("CODEX_BIN"):
        return os.environ["CODEX_BIN"]
    on_path = shutil.which("codex")
    if on_path:
        return on_path
    bundled = os.environ.get("CODEX_BUNDLED_BIN", BUNDLED_BIN)
    if os.access(bundled, os.X_OK):
        return bundled
    raise CodexNotFound(f"no Codex CLI found: not on PATH and not at {bundled}; "
                        "set CODEX_BIN to the codex binary")


def model_settings(model=None, effort=None):
    """(model, reasoning effort): the given values, else $CODEX_MODEL / $CODEX_REASONING_EFFORT, else the defaults."""
    return (model or os.environ.get("CODEX_MODEL") or DEFAULT_MODEL,
            effort or os.environ.get("CODEX_REASONING_EFFORT") or DEFAULT_EFFORT)


def user_codex_home():
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def isolated_env(codex_home, base_env):
    """BASE_ENV with CODEX_HOME pointing at a fresh CODEX_HOME that links only the user's auth.json."""
    codex_home.mkdir(parents=True)
    auth = user_codex_home() / "auth.json"
    if auth.exists():
        (codex_home / "auth.json").symlink_to(auth)
    return {**base_env, "CODEX_HOME": str(codex_home)}


def toml_table(entries):
    """An inline TOML table; ENTRIES maps keys to values already written as TOML."""
    return "{" + ", ".join(f'"{key}"={value}' for key, value in entries.items()) + "}"


def docker_socket():
    """The Unix socket lisp-check's docker talks to, resolved to its real path, or None."""
    if os.environ.get("LISP_CHECK_MODE", "docker") != "docker":
        return None
    host = os.environ.get("DOCKER_HOST")
    if not host:
        try:
            host = subprocess.run(
                [os.environ.get("LISP_CHECK_DOCKER", "docker"), "context", "inspect",
                 "--format", "{{.Endpoints.docker.Host}}"],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=DOCKER_QUERY_TIMEOUT,
            ).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return None
    if not host.startswith("unix://"):
        return None
    return os.path.realpath(host.removeprefix("unix://"))


def permission_options(round_log_dir, readable, unreadable):
    """A sandbox profile: read everywhere but UNREADABLE (except the narrower READABLE), write only the
    workspace and ROUND_LOG_DIR, reach docker's socket.

    The plain workspace-write sandbox blocks the docker socket, so lisp-check could not run.
    """
    filesystem = {":root": '"read"', ":project_roots": '"write"', str(round_log_dir): '"write"',
                  **{str(path): '"none"' for path in unreadable}, **{str(path): '"read"' for path in readable}}
    socket = docker_socket()
    network = ({"enabled": "true", "unix_sockets": toml_table({socket: '"allow"'})} if socket
               else {"enabled": "false"})
    profile = f"permissions.{PERMISSIONS_PROFILE}"
    return ["-c", f'default_permissions="{PERMISSIONS_PROFILE}"',
            "-c", f"{profile}.filesystem={toml_table(filesystem)}",
            "-c", f"{profile}.network={toml_table(network)}"]


def usage(events):
    """(token totals summed over every `turn.completed` event, input plus output tokens), or (None, None).

    Codex counts cached input inside input_tokens and reasoning inside output_tokens.
    """
    totals = {}
    for event in events:
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            for key, value in event["usage"].items():
                if isinstance(value, int):
                    totals[key] = totals.get(key, 0) + value
    if not totals:
        return None, None
    return totals, totals.get("input_tokens", 0) + totals.get("output_tokens", 0)


def exec_options(model, effort, round_log_dir, readable, unreadable):
    """Options shared by `codex exec` and `codex exec resume`."""
    return [
        "--json", "--ignore-user-config", "--ignore-rules", "--disable", "multi_agent",
        "-m", model, "-c", f'model_reasoning_effort="{effort}"',
        "-c", "features.plugins=false", "-c", "skills.include_instructions=false",
        "-c", 'web_search="disabled"', "-c", 'approval_policy="never"',
        *permission_options(round_log_dir, readable, unreadable),
    ]
