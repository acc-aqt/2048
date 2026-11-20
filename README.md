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

If the wrapper gets SIGTERM, SIGINT or SIGHUP (for example when the runner kills OpenCode at a limit), it kills the check's process group and, in Docker mode, `docker kill`s its container, then exits 128 + signal number without a log line.

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
- `hidden-tests/*.lisp`: tester files graded after the run, never present during it. They are copied to the same relative path under a `hidden-tests/` folder of a grading copy of the model's folder (`hidden-tests-2/` and so on if the model made a `hidden-tests` itself), so no model file can clash with them; `lisp-check` finds the model's `.asd` one folder up. Write every assertion as one top-level `(test ...)`/`(test-error ...)` form: the grader counts them to get the total. An error while loading a hidden test file (for example a missing function) means 0 passed for that file.

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
| wall clock, both OpenCode turns together (the status check between them is not counted) | 7200 s | `--timeout` | process group killed, run failed, `limit_hit: "wall_clock"` |
| one grading `lisp-check` | 120 s | `--check-timeout` | that file `TIMEOUT` (a hidden test file counts 0 passed), run failed |

"Process group killed" means SIGTERM to OpenCode's process group, up to 10 s for every process in it to exit (a running `lisp-check` uses it to kill its check and container), then SIGKILL. Reaching the round limit fails the run even if the model stopped on its own at that round. The runner polls the round log every 0.2 s, so `check_fix_rounds` can end slightly above the limit.

If the first turn ends without hitting a limit, the runner checks that every required file (`.asd` included) exists and every present `.lisp` file prints OK, in a copy of `work/` (own log, not counted as rounds). If any is missing or not OK, it sends the one fixed message "Continue until every file is created and every .lisp file prints OK in lisp-check." with `opencode run -s <session>`. It never sends a second one.

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
4. Writes `runs/<task>/<setup>/<run>/`: `result.json`, `transcript.jsonl` (the JSON event stream), `session.json` (the export), `opencode.stderr.log`, `lisp-check.log` (one line per round), `grading.log` and `src/` (the model's final files: folders and regular files only; symlinks and special files such as FIFOs are skipped and listed in `skipped_files`). It builds the record in a hidden sibling folder and renames it into place at the end, so a record folder either has its `result.json` or doesn't exist. A record counts as existing only when it has `result.json`: run-task refuses to overwrite one, and renames a leftover folder without `result.json` to `<run>.incomplete-<UTC time>` before saving the new record. Grading copies `work/` the same way, so it sees the same files as `src/`.

`result.json` holds task, setup, run number, `counted`, model, start time, `duration_seconds` (time spent in OpenCode turns, both together: the same time the wall-clock limit counts, so without the status check between turns, the export and grading), `limits`, `limit_hit` (`null`, `"rounds"` or `"wall_clock"`), the last turn's OpenCode exit code, `continue_sent`, `check_fix_rounds`, `hidden_tests_passed`/`hidden_tests_total`, per-file status in `source_files` (`OK`, `FAIL`, `TIMEOUT` for each `.lisp` file, `MISSING` for any absent required file, `.asd` included), `skipped_files` (`{path: "symlink" | "special file"}`) and `passed` (every file OK, every hidden assertion passed, no limit hit).

The tests drive `bin/run-task` with `tests/fixtures/fake-opencode` (set through `OPENCODE_BIN`), so they never contact a model.

### Counted runs, regrading and `RESULTS.md`

```sh
bin/run-batch TASK [--run-root DIR] [--records-dir DIR]
              [--timeout SECONDS] [--max-rounds N] [--check-timeout SECONDS]
bin/regrade RECORD_DIR [--check-timeout SECONDS]
bin/results TASK [--records-dir DIR] [--output FILE]
```

`bin/run-batch` calls `bin/run-task` for the counted runs 1 to 5 of both setups, with the same flags for every run. The setup that goes first alternates (run 1: with, without; run 2: without, with; ...) so a slow or fast stretch of the night doesn't favour one setup. It skips a run whose record already has a `result.json`, so running it again after an interruption resumes with the next unfinished run. A run whose `run-task` fails (no record) doesn't stop the batch; it is listed at the end, the exit code is 1, and the next batch call retries it. It never runs the practice run. Overnight, after the practice run:

```sh
export PATH="$PWD/bin:$PATH"
bin/preflight && caffeinate -i bin/run-batch game-2048 2>&1 | tee -a /tmp/2048-batch.log
```

`bin/regrade runs/game-2048/with-skills/3` grades that run's saved `src/` again against the task's hidden tests in a temporary folder (the record is never changed), prints each file's status and the hidden-test score, and exits 0 if they match `result.json`, 1 if not. It checks the code only; a run that hit a limit failed even if its code passes.

`bin/results game-2048` writes `RESULTS.md` from `<records dir>/game-2048/*/*/result.json` (default `runs/`; record paths in `RESULTS.md` are relative to its folder when the records are inside it, else absolute): a row per counted run, a summary per setup (pass rate, medians of hidden tests, rounds and duration), the practice run listed apart, the method (model name from the records, lisp-skills commit from the submodule, limits from the records), threats to validity, how to regrade, and, for a task whose spec defines `play`, how to play the best passing run (fewest rounds, then shortest duration) from a temporary copy of its `src/`, or that no run passed. Rerun it after the batch; it overwrites `RESULTS.md`.

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
| `tasks/game-2048/hidden-tests/` | hidden tests, one file per seam: `hidden-slide-row-tests.lisp`, `hidden-move-tests.lisp`, `hidden-spawn-tile-tests.lisp`, `hidden-won-game-over-tests.lisp`, `hidden-play-tests.lisp` (66 assertions) |
| `reference/game-2048/` | private reference implementation; never copied into a run folder |

The hidden tests use only the public interface from the spec. They set `util.test:*error-protect-tests*`, so an error inside one assertion fails only that assertion. A compile-time problem, such as an interface function the package does not export, still fails the whole file. Splitting the tests by seam keeps that loss to one file.

`tests/test_game_2048_task.py` grades a copy of the reference with `harness.grade.grade`: every file must print `OK` and all 66 hidden assertions must pass. It also checks that a copy with a double-merge bug fails some hidden tests, and that a copy that does not export `won-p` loses only the `won-p`/`game-over-p` file.
