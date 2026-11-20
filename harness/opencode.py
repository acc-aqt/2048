"""Environment for running the pinned OpenCode isolated from the user's own setup."""

import json
import os
import shutil
from pathlib import Path

PINNED_VERSION = "1.19.6"
CONFIG_FILE = Path(__file__).resolve().parent / "opencode.json"


def write_run_config(state_dir, rules_file=None):
    """Write CONFIG_FILE into `state_dir`; with `rules_file`, add a copy of it as always-loaded instructions."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG_FILE.read_text())
    if rules_file is not None:
        rules_copy = state_dir / "instructions" / Path(rules_file).name
        rules_copy.parent.mkdir()
        shutil.copy2(rules_file, rules_copy)
        config["instructions"] = [str(rules_copy)]
    config_file = state_dir / "opencode.json"
    config_file.write_text(json.dumps(config, indent=2) + "\n")
    return config_file


def isolated_env(state_dir, base_env=None, config_file=CONFIG_FILE):
    """Env that points every OpenCode config/data dir into `state_dir` and loads only `config_file`."""
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
        OPENCODE_CONFIG=str(config_file),
        OPENCODE_DISABLE_CLAUDE_CODE="1",
        OPENCODE_DISABLE_CLAUDE_CODE_PROMPT="1",
        OPENCODE_DISABLE_EXTERNAL_SKILLS="1",
        OPENCODE_DISABLE_AUTOUPDATE="1",
        OPENCODE_DISABLE_MODELS_FETCH="1",
    )
    return env
