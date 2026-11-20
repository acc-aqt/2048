# 2048

Proof of concept: can Qwen3-8B, driven by OpenCode, write a 2048 game in Common Lisp (Allegro CL) using the lisp-skills rules and `lisp-check`? See issue #1.

## Toolchain

| Piece | Version / location |
|---|---|
| Ollama | 0.40.16 (brew formula, `brew services start ollama`) |
| Model | `qwen3-8b-32k`: `qwen3:8b` Q4_K_M with `PARAMETER num_ctx 32768` |
| OpenCode | 1.19.6, npm `opencode-ai` (v1 config schema: `provider`, `permission`) |
| lisp-skills | submodule `vendor/lisp-skills`, pinned at `07effc058c7d0c89347318f000d16ad5f13612a6` |
| Allegro CL | 11.0 Express in the Docker image `lisp-skills-allegro:latest` |

After cloning: `git submodule update --init`.

Harness code is Python 3, standard library only. Run the tests (the Docker and OpenCode tests skip when the image or OpenCode 1.19.6 is missing):

```sh
python3 -m unittest discover -s tests -t .
```

### `bin/lisp-check`

Use it exactly like the upstream `lisp-check [--test] FILE`; put `bin/` on `PATH` (a symlink works too). It runs the pinned upstream `lisp-check` and passes its output and exit code through unchanged (0 OK, 1 FAIL, 2 could not run). When Docker itself fails, it prints `lisp-check: <reason>` and `FAIL` and exits 2.

In Docker mode the current directory is mounted at the same path, so run it from the run folder (or a subfolder of it). The upstream ASDF lookup walks up to the nearest `.git`, so give each run folder its own `.git` directory.

Each invocation appends one tab-separated line to the log: UTC timestamp, exit code, arguments. One line is one check-fix round.

| Env var | Default | Meaning |
|---|---|---|
| `LISP_CHECK_MODE` | `docker` | `docker`, or `native` (runs the upstream script directly with the installed Allegro, see "Running at work") |
| `LISP_BIN` | `alisp` | native mode only: Lisp binary, a name on `PATH` or an absolute path (read by upstream `lisp-check`) |
| `LISP_CHECK_LOG` | `./.lisp-check.log` | invocation log file |
| `LISP_CHECK_IMAGE` | `lisp-skills-allegro:latest` | Docker image |
| `LISP_CHECK_DOCKER` | `docker` | Docker binary |

### `bin/preflight`

Run it before any long run. It checks that `lisp-check` prints OK on a correct file and FAIL on a broken one, and that the model answers a chat request with a valid `bash` tool call. Each check prints `PASS` or `FAIL <reason>`. The last line is `preflight: OK` (exit 0) or `preflight: FAIL` (exit 1). `--skip-model` sends no request to the model.

| Env var | Default | Meaning |
|---|---|---|
| `LLM_BASE_URL` | `http://127.0.0.1:11434/v1` | OpenAI-compatible endpoint |
| `LLM_MODEL` | `qwen3-8b-32k` | model name sent to the endpoint |
| `LLM_API_KEY` | `ollama` | bearer token |
| `LLM_TIMEOUT` | `300` | seconds to wait for the model |

### OpenCode

`harness/opencode.json` defines the provider `local` with model `local/qwen3`, taking base URL, API key and model name from the same `LLM_*` variables, with the context limit set to 32768. Set all three variables; an unset one becomes an empty string. Start OpenCode with the environment from `harness.opencode.isolated_env(state_dir)`. That environment moves every OpenCode config, data, state and cache directory into `state_dir`, loads `harness/opencode.json` as the config file, and sets `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1`. So no global OpenCode config and no `~/.claude/CLAUDE.md` is used.

## Running at work (openSUSE + LiteLLM)

Target: openSUSE Linux x86_64 with Allegro CL installed natively, Python 3, no Docker, Qwen3-8B FP8 behind LiteLLM. Only environment variables change; the code is the same as on the Mac.

**The LiteLLM path is untested locally.** The tests only check that the `LLM_*` variables reach the OpenCode config and the preflight request. No request has been sent to a LiteLLM server. Native `lisp-check` mode is tested by running the wrapper inside the `lisp-skills-allegro` image (Ubuntu, Allegro 11.0 Express), not on openSUSE itself.

1. Install OpenCode 1.19.6 (needs Node.js and npm):

   ```sh
   npm i -g opencode-ai@1.19.6
   opencode --version   # 1.19.6
   ```

2. Clone with the pinned lisp-skills submodule (commit `07effc058c7d0c89347318f000d16ad5f13612a6`):

   ```sh
   git clone --recurse-submodules https://github.com/acc-aqt/2048.git
   cd 2048
   git -C vendor/lisp-skills rev-parse HEAD   # 07effc058c7d0c89347318f000d16ad5f13612a6
   ```

3. Set the environment:

   ```sh
   export LISP_CHECK_MODE=native
   export LISP_BIN=/path/to/acl/alisp          # not needed if alisp is on PATH
   export LLM_BASE_URL=https://<litellm-host>/v1
   export LLM_MODEL=<litellm model alias for Qwen3-8B FP8>
   export LLM_API_KEY=<litellm key>
   export PATH="$PWD/bin:$PATH"                # lisp-check for the agent
   ```

   Set all three `LLM_*` variables: OpenCode turns an unset one into an empty string. Upstream `lisp-check` writes ASDF output to `/tmp/lisp-check-asdf/`, shared between runs on the same machine.

4. Run the preflight. It checks that `lisp-check` prints OK and FAIL on known files and that the model answers with a valid `bash` tool call through LiteLLM:

   ```sh
   bin/preflight
   ```

   `bin/preflight --skip-model` checks only `lisp-check`. If the model check fails on a timeout, raise `LLM_TIMEOUT`.

## Task and grading

| Path | What |
|---|---|
| `tasks/game-2048/spec.md` | the task text the model gets, verbatim |
| `tasks/game-2048/hidden-tests/` | hidden tests, copied into the run folder next to `game-2048.asd` only for grading |
| `reference/game-2048/` | private reference implementation; never copied into a run folder |

Grade a run folder (it must have its own `.git`) with `lisp-check --test game-2048-hidden-tests.lisp`. The hidden tests use only the public interface from the spec and catch errors per assertion, so a failing run prints `N of M assertions failed`. M is the number of lines starting with `(test` in the file. A missing or unexported interface function fails at the compile stage instead, without counts.

`tests/test_game_2048_task.py` (part of the unittest run above) validates the hidden tests: it lays out a run folder from the reference and the hidden tests in a temporary directory, checks that every file prints `OK`, and that the hidden tests fail on a copy with a wrong merge rule.
