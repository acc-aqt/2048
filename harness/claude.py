"""Running Claude Code isolated from the user's own Claude setup."""

import os

DEFAULT_MODEL = "haiku"
DEFAULT_EFFORT = "low"


def find_claude():
    """$CLAUDE_BIN, else `claude` on PATH."""
    return os.environ.get("CLAUDE_BIN") or "claude"


def model_settings(model=None, effort=None):
    """(model, effort): the given values, else $CLAUDE_MODEL / $CLAUDE_EFFORT, else the defaults."""
    return (model or os.environ.get("CLAUDE_MODEL") or DEFAULT_MODEL,
            effort or os.environ.get("CLAUDE_EFFORT") or DEFAULT_EFFORT)


def isolated_env(base_env, effort):
    """BASE_ENV with the effort pinned; the env var beats --effort and every settings file."""
    return {**base_env, "CLAUDE_CODE_EFFORT_LEVEL": effort}


def base_options(model, effort):
    """Options shared by the first turn and the resumed turn."""
    return ["-p", "--output-format", "stream-json", "--verbose", "--model", model, "--effort", effort]
