"""Environment for running the pinned OpenCode isolated from the user's own setup."""

import os
from pathlib import Path

PINNED_VERSION = "1.19.6"
CONFIG_FILE = Path(__file__).resolve().parent / "opencode.json"


def isolated_env(state_dir, base_env=None):
    """Env that points every OpenCode config/data dir into `state_dir` and loads only CONFIG_FILE."""
    state_dir = Path(state_dir)
    dirs = {
        "XDG_CONFIG_HOME": state_dir / "xdg-config",
        "XDG_DATA_HOME": state_dir / "data",
        "XDG_STATE_HOME": state_dir / "state",
        "XDG_CACHE_HOME": state_dir / "cache",
        "OPENCODE_CONFIG_DIR": state_dir / "config",
        "OPENCODE_TEST_HOME": state_dir / "home",
    }
    env = dict(os.environ if base_env is None else base_env)
    env.update({key: str(path) for key, path in dirs.items()})
    env.update(
        OPENCODE_CONFIG=str(CONFIG_FILE),
        OPENCODE_DISABLE_CLAUDE_CODE="1",
        OPENCODE_DISABLE_CLAUDE_CODE_PROMPT="1",
        OPENCODE_DISABLE_EXTERNAL_SKILLS="1",
        OPENCODE_DISABLE_AUTOUPDATE="1",
        OPENCODE_DISABLE_MODELS_FETCH="1",
    )
    return env
