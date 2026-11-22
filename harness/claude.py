"""Running Claude Code isolated from the user's own Claude setup and confined to the run's model folder."""

import json
import os
import shutil
from pathlib import Path

DEFAULT_MODEL = "haiku"
DEFAULT_EFFORT = "low"
DEFAULT_BUDGET_USD = 5.0
USAGE_KEYS = {"input_tokens": "inputTokens", "output_tokens": "outputTokens",
              "cache_read_input_tokens": "cacheReadInputTokens",
              "cache_creation_input_tokens": "cacheCreationInputTokens"}
TOOLS = ("Bash", "Edit", "Read", "Write")
DISALLOWED_TOOLS = ("Agent", "WebFetch", "WebSearch")
BUILTIN_PLUGINS = ("cc-plugin-agents-md", "cc-plugin-telemetry", "cc-plugin-privacy",
                   "cc-plugin-plugin-authoring", "cc-plugin-easel")


class ClaudeNotFound(Exception):
    pass


def find_claude():
    """$CLAUDE_BIN, else `claude` on PATH."""
    if os.environ.get("CLAUDE_BIN"):
        return os.environ["CLAUDE_BIN"]
    on_path = shutil.which("claude")
    if on_path:
        return on_path
    raise ClaudeNotFound("no Claude Code CLI found: `claude` is not on PATH; set CLAUDE_BIN to the claude binary")


def model_settings(model=None, effort=None):
    """(model, effort): the given values, else $CLAUDE_MODEL / $CLAUDE_REASONING_EFFORT, else the defaults."""
    return (model or os.environ.get("CLAUDE_MODEL") or DEFAULT_MODEL,
            effort or os.environ.get("CLAUDE_REASONING_EFFORT") or DEFAULT_EFFORT)


def isolated_env(base_env, effort, tmp_dir):
    """BASE_ENV without the variables a parent Claude Code session exports and without any ANTHROPIC_*
    variable, with the effort pinned and auto-memory off.

    ANTHROPIC_* variables (API key, auth token, base URL, model overrides) would change who is billed,
    which provider answers or which model runs, so every run uses the subscription login instead.
    CLAUDE_CODE_EFFORT_LEVEL beats --effort and every settings file. CLAUDE_CONFIG_DIR is kept: it says where
    the user's login lives.
    CLAUDE_CODE_TMPDIR=TMP_DIR keeps Claude Code's own temp files out of the /tmp/claude-<uid> that every
    Claude Code session on the machine shares. The sandboxed shell's TMPDIR stays /tmp/claude-<uid>, which
    the sandbox can't read, so shell here-documents fail, as they do in Codex runs.
    """
    env = {key: value for key, value in base_env.items()
           if not key.startswith(("CLAUDE", "ANTHROPIC_")) or key == "CLAUDE_CONFIG_DIR"}
    return {**env, "CLAUDE_CODE_EFFORT_LEVEL": effort, "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "CLAUDE_CODE_TMPDIR": str(tmp_dir)}


def run_settings(work, writable, readable, unreadable, read_only, docker_socket):
    """The per-run settings: no memory, hooks or user instructions; file tools and shell confined to WORK.

    Shell commands run in Claude Code's OS sandbox: they can't read UNREADABLE (except the narrower
    READABLE paths lisp-check needs), write only WORK (but not the READ_ONLY files in it) and the
    WRITABLE folders, and may reach DOCKER_SOCKET. The file tools can't edit READ_ONLY either.
    """
    home = Path.home()
    sandbox_network = {"allowUnixSockets": [docker_socket]} if docker_socket else {}
    return {
        "autoMemoryEnabled": False,
        "disableAllHooks": True,
        "enabledPlugins": {f"{name}@builtin": False for name in BUILTIN_PLUGINS},
        "claudeMdExcludes": [str(home / ".claude" / "CLAUDE.md"), str(home / ".claude" / "rules" / "**")],
        "permissions": {
            "defaultMode": "dontAsk",
            "allow": [f"Edit(/{work}/**)", "Bash"],
            "deny": [f"Edit(/{path})" for path in read_only],
            "blockReadsOutsideWorkingDirectories": True,
            "disableBypassPermissionsMode": "disable",
        },
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "autoAllowBashIfSandboxed": True,
            "filesystem": {
                "denyRead": [str(path) for path in unreadable],
                "allowRead": [str(work), *(str(path) for path in readable)],
                "allowWrite": [str(path) for path in writable],
                "denyWrite": [str(path) for path in read_only],
            },
            "network": sandbox_network,
        },
    }


def write_settings(path, settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")
    return path


def base_options(model, effort, settings_file):
    """Options shared by the first turn and the resumed turn."""
    return [
        "-p", "--output-format", "stream-json", "--verbose",
        "--model", model, "--effort", effort,
        "--setting-sources", "project", "--settings", str(settings_file),
        "--strict-mcp-config", "--disable-slash-commands", "--tools", ",".join(TOOLS),
        "--disallowedTools", ",".join(DISALLOWED_TOOLS),
        "--permission-mode", "dontAsk",
    ]


def result_events(events):
    return [event for event in events if event.get("type") == "result"]


def budget_exhausted(events):
    """Whether the last turn in EVENTS stopped because it reached --max-budget-usd."""
    results = result_events(events)
    return bool(results) and results[-1].get("subtype") == "error_max_budget_usd"


def usage(events):
    """(token totals, cost in USD) for the whole session, from its last `result` event, or (None, None).

    A resumed session's `modelUsage` and `total_cost_usd` include the earlier turns, while its `usage`
    covers only the last turn and is zero after a budget stop, so the totals come from `modelUsage`.
    """
    results = result_events(events)
    if not results:
        return None, None
    last = results[-1]
    totals = {}
    for model_usage in (last.get("modelUsage") or {}).values():
        for name, key in USAGE_KEYS.items():
            if isinstance(model_usage.get(key), int):
                totals[name] = totals.get(name, 0) + model_usage[key]
    return totals or None, last.get("total_cost_usd")
