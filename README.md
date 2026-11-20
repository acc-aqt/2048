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
| `LISP_CHECK_TIMEOUT` | none | seconds before the check is killed (Docker mode: `docker kill` of its container); it then prints `lisp-check: timed out after N s` and `FAIL` and exits 2. Only grading sets it; the model's own checks have no timeout |

### `bin/preflight`

Run it before any long run. It checks that `lisp-check` prints OK on a correct file and FAIL on a broken one, and that the model answers a chat request with a valid `bash` tool call. Each check prints `PASS` or `FAIL <reason>`. The last line is `preflight: OK` (exit 0) or `preflight: FAIL` (exit 1). `--skip-model` sends no request to the model.

| Env var | Default | Meaning |
|---|---|---|
| `LLM_BASE_URL` | `http://127.0.0.1:11434/v1` | OpenAI-compatible endpoint |
| `LLM_MODEL` | `qwen3-8b-32k` | model name sent to the endpoint |
| `LLM_API_KEY` | `ollama` | bearer token |
| `LLM_TIMEOUT` | `300` | seconds to wait for the model |

### OpenCode

`harness/opencode.json` defines the provider `local` with model `local/qwen3`, taking base URL, API key and model name from the same `LLM_*` variables, with the context limit set to 32768. Set all three variables; an unset one becomes an empty string. Start OpenCode with the environment from `harness.opencode.isolated_env(state_dir)`. That environment moves every OpenCode config, data, state and cache directory into `state_dir`, loads `harness/opencode.json` (or the `config_file` passed in) as the config file, and sets `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1`. So no global OpenCode config and no `~/.claude/CLAUDE.md` is used.

The config allows every tool without asking, but denies `task` (subagents), `webfetch`, `websearch`, `question`, `skill` and `external_directory` (anything outside the run folder).

## Running an experiment

### Tasks

A task lives in `tasks/<task-name>/`:

- `spec.md`: the task text. The runner puts it into the prompt.
- `hidden-tests/*.lisp`: tester files graded after the run, never present during it. They are copied to the same relative path in the root of a grading copy of the model's folder, next to its `.asd`. Write every assertion as one top-level `(test ...)`/`(test-error ...)` form: the grader counts them to get the total. An error while loading a hidden test file (for example a missing function) means 0 passed for that file.

A private reference solution lives in `reference/<task-name>/`. It only validates the hidden tests (see `tests/test_dummy_task.py`); the runner never reads it. `tasks/dummy-slide-row` is a tiny task (only `slide-row`) for trying the chain end to end.

### `bin/run-task`

```sh
bin/run-task TASK SETUP RUN_NUMBER [--run-root DIR] [--records-dir DIR]
             [--timeout SECONDS] [--max-rounds N] [--check-timeout SECONDS]
bin/run-task dummy-slide-row without-skills 0
```

### Setups

| Setup | Gets besides the shared prompt |
|---|---|
| `with-skills` | the pinned `vendor/lisp-skills/dist/lisp-rules.md` as always-loaded OpenCode `instructions` |
| `without-skills` | the sentence "Run lisp-check FILE until it prints OK." after the spec |

Nothing else differs. The shared prompt is identical for both: work alone, create the files from the spec's file table directly in the current folder, and check every `.lisp` file with the listed `lisp-check` commands (`--test` for `*tests.lisp`), then the spec. Each run writes its own OpenCode config to `<run folder>/opencode/opencode.json`: a copy of `harness/opencode.json`, plus, for `with-skills` only, `instructions` pointing at a copy of the rules in `<run folder>/opencode/instructions/`. The without-skills run folder never contains the rules.

### Limits and the continue message

| Limit | Default | Flag | On hit |
|---|---|---|---|
| check-fix rounds (lines in the round log) | 40 | `--max-rounds` | process group killed, run failed, `limit_hit: "rounds"` |
| wall clock, both turns together | 7200 s | `--timeout` | process group killed, run failed, `limit_hit: "wall_clock"` |
| one grading `lisp-check` | 600 s | `--check-timeout` | that file `TIMEOUT` (a hidden test file counts 0 passed), run failed |

Reaching the round limit fails the run even if the model stopped on its own at that round. The runner polls the round log every 0.2 s, so `check_fix_rounds` can end slightly above the limit.

If the first turn ends without hitting a limit, the runner checks every required and every present `.lisp` file in a copy of `work/` (own log, not counted as rounds). If any is missing or not OK, it sends the one fixed message "Continue until every file is created and every .lisp file prints OK in lisp-check." with `opencode run -s <session>`. It never sends a second one.

### Practice run

Run number 0 is the uncounted practice run (`"counted": false`); counted runs are 1 to 5. The limits may change once, after the practice run only; write the change and its reason under "Limit changes" below.

```sh
export PATH="$PWD/bin:$PATH"
bin/preflight
bin/run-task game-2048 with-skills 0
```

#### Limit changes

None yet.

### What one call does

1. Creates a fresh run folder `<run root>/<task>/<setup>/<run>-<UTC time>/` with `work/` (the model's folder: an empty `git init` repo), `bin/lisp-check`, the OpenCode state directory and the round log, which stays outside `work/`. The run root (default `$RUN_ROOT` or `/tmp/2048-runs`) must be outside the repo and outside `$HOME`.
2. Runs `opencode run --format json --thinking` in `work/` with the shared prompt, stdin closed and the isolated environment, enforcing the limits above, and sends the continue message if needed.
3. Exports the session with `opencode export`, then grades: every required and every present `.lisp` file in `work/` through `lisp-check` (`--test` for `*tests.lisp`) and the hidden tests with `lisp-check --test`, all in a copy of `work/`. These grading checks don't count as rounds.
4. Writes `runs/<task>/<setup>/<run>/`: `result.json`, `transcript.jsonl` (the JSON event stream), `session.json` (the export), `opencode.stderr.log`, `lisp-check.log` (one line per round), `grading.log` and `src/` (the model's final files). It refuses to overwrite an existing record.

`result.json` holds task, setup, run number, `counted`, model, start time, duration, `limits`, `limit_hit` (`null`, `"rounds"` or `"wall_clock"`), the last turn's OpenCode exit code, `continue_sent`, `check_fix_rounds`, `hidden_tests_passed`/`hidden_tests_total`, per-file status in `source_files` (`OK`, `FAIL`, `TIMEOUT` or `MISSING`) and `passed` (every file OK, every hidden assertion passed, no limit hit).

The tests drive `bin/run-task` with `tests/fixtures/fake-opencode` (set through `OPENCODE_BIN`), so they never contact a model.

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
