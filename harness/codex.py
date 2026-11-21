"""Running the Codex CLI isolated from the user's own Codex setup."""

import os
import subprocess
from pathlib import Path

DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_EFFORT = "low"
PERMISSIONS_PROFILE = "harness"
DOCKER_QUERY_TIMEOUT = 30


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


def permission_options(round_log_dir):
    """A sandbox profile: read everywhere, write only the workspace and ROUND_LOG_DIR, reach docker's socket.

    The plain workspace-write sandbox blocks the docker socket, so lisp-check could not run.
    """
    filesystem = {":root": '"read"', ":project_roots": '"write"', str(round_log_dir): '"write"'}
    socket = docker_socket()
    network = ({"enabled": "true", "unix_sockets": toml_table({socket: '"allow"'})} if socket
               else {"enabled": "false"})
    profile = f"permissions.{PERMISSIONS_PROFILE}"
    return ["-c", f'default_permissions="{PERMISSIONS_PROFILE}"',
            "-c", f"{profile}.filesystem={toml_table(filesystem)}",
            "-c", f"{profile}.network={toml_table(network)}"]


def exec_options(model, effort, round_log_dir):
    """Options shared by `codex exec` and `codex exec resume`."""
    return [
        "--json", "--ignore-user-config", "--ignore-rules", "--disable", "multi_agent",
        "-m", model, "-c", f'model_reasoning_effort="{effort}"',
        "-c", "features.plugins=false", "-c", "skills.include_instructions=false",
        "-c", 'web_search="disabled"', "-c", 'approval_policy="never"',
        *permission_options(round_log_dir),
    ]
