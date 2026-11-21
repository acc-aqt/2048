"""Running the Codex CLI isolated from the user's own Codex setup."""

import os

DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_EFFORT = "low"


def model_settings(model=None, effort=None):
    """(model, reasoning effort): the given values, else $CODEX_MODEL / $CODEX_REASONING_EFFORT, else the defaults."""
    return (model or os.environ.get("CODEX_MODEL") or DEFAULT_MODEL,
            effort or os.environ.get("CODEX_REASONING_EFFORT") or DEFAULT_EFFORT)


def exec_options(model, effort):
    """Options shared by `codex exec` and `codex exec resume`."""
    return ["--json", "-m", model, "-c", f'model_reasoning_effort="{effort}"']
