# Results overview: game-2048

## Overview

| Backend | Model | Effort | Setup | Counted runs | Passed | Median hidden tests | Median rounds | Median duration | Median tokens | Median cost | Records |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | haiku | low | with-skills | 5 | 5/5 | 66/66 | 6 | 1.6 min | 307,969 | $0.02 | runs/claude |
| claude | haiku | low | without-skills | 5 | 4/5 | 66/66 | 10 | 2.5 min | 598,606 | $0.03 | runs/claude |
| codex | gpt-6-luna | low | with-skills | 5 | 3/5 | 66/66 | 24 | 3.4 min | 995,697 | n/a | runs/codex |
| codex | gpt-6-luna | low | without-skills | 5 | 3/5 | 66/66 | 25 | 4.4 min | 1,180,707 | n/a | runs/codex |

Each row covers the counted runs (1 to 5) of one backend and setup from the records directory in its last column. Medians are over those runs; "n/a" means the records hold no value (Codex and OpenCode report no cost).

## Practice runs (not counted)

| Backend | Setup | Run | Check-fix rounds | Hidden tests | Duration | Limit hit | Continue sent | Result | Tokens | Cost | Records |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | with-skills | 0 | 6 | 66/66 | 1.6 min | - | no | PASS | 319,362 | $0.02 | runs/claude |
| claude | without-skills | 0 | 19 | 66/66 | 3.7 min | - | no | PASS | 971,910 | $0.04 | runs/claude |
| codex | with-skills | 0 | 18 | 66/66 | 3.3 min | - | yes | PASS | 1,390,379 | n/a | runs/codex |
| codex | without-skills | 0 | 29 | 66/66 | 4.3 min | - | no | PASS | 566,207 | n/a | runs/codex |

## Suspected leaks

These runs' transcripts name the repo, `hidden-tests`, `reference/` or another Claude Code session's temp folder (`/tmp/claude-`), or, without skills, `lisp-skills`, so the model may have looked for the hidden tests, the reference solution or the rules. Their results stand as recorded; review each transcript before trusting it:

- claude: `runs/claude/game-2048/with-skills/0`
- claude: `runs/claude/game-2048/with-skills/1`
- claude: `runs/claude/game-2048/without-skills/0`
- claude: `runs/claude/game-2048/without-skills/1`
- claude: `runs/claude/game-2048/without-skills/2`
- claude: `runs/claude/game-2048/without-skills/3`
- claude: `runs/claude/game-2048/without-skills/4`
- claude: `runs/claude/game-2048/without-skills/5`
- codex: `runs/codex/game-2048/with-skills/4`
- codex: `runs/codex/game-2048/without-skills/0`
- codex: `runs/codex/game-2048/without-skills/1`
- codex: `runs/codex/game-2048/without-skills/4`

## Method

- **Model:** `gpt-6-luna` at `low` effort, driven by the Codex CLI, isolated from the user's Codex config, plugins and bundled skills; `haiku` at `low` effort, driven by Claude Code, isolated from the user's `CLAUDE.md`, plugins and memory, with no skills, subagents or web tools, its file tools and sandboxed shell confined to the model folder.
- **Task:** `tasks/game-2048/spec.md`, the same text for every run.
- **Setups:** `with-skills` gets the lisp-skills rules (`vendor/lisp-skills/dist/lisp-rules.md`, lisp-skills commit `07effc058c7d0c89347318f000d16ad5f13612a6`) as a generated `AGENTS.md` in the model folder for Codex CLI and as a generated `CLAUDE.md` in the model folder for Claude Code; `without-skills` gets only the sentence "Run lisp-check FILE until it prints OK." Nothing else differs.
- **Runs:** 5 counted runs per setup, run with `bin/run-batch`, alternating which setup goes first. Run 0 was an uncounted practice run. Every run starts in a fresh, empty folder.
- **Human input:** one fixed prompt, and at most once the fixed message "Continue until every file is created and every .lisp file prints OK in lisp-check." if the model stopped before every file printed OK. Nobody edited the model's code.
- **Limits:** 40 check-fix rounds, 120 min wall clock, 120 s per grading check. Hitting a limit fails the run.
- **Pass:** every `.lisp` file prints OK in `lisp-check` and all hidden tests (`66` assertions) pass through `lisp-check --test`. The model never saw the hidden tests.
- **Records:** `runs/claude/game-2048/<setup>/<run>/` and `runs/codex/game-2048/<setup>/<run>/` hold `result.json`, the transcript, the exported session, the round log, the grading log and `src/`, the model's final files.

## Threats to validity

- **Model plus agent harness.** Each hosted run measures the model together with its agent harness (Claude Code or the Codex CLI), not the model alone. The hosted models also change over time; every record names the model and effort it ran with.
- **Different agent harnesses.** Rows from different backends differ in model, agent harness, tools and token accounting at once. Compare the two setups within one backend first; a difference between backends is not a model-only comparison. Runs get no agent skills or plugins on any backend, and the only extra text a `with-skills` run gets is the rules file, but each agent's built-in system prompt and tools still differ (Claude Code vs the Codex CLI) and can't be removed.
- **Codex shell network.** Codex shell commands have open network access: its sandbox enables the network so `lisp-check` can reach Docker, so a run could download code (web search itself is off).
- **Claude's sandbox and tool set.** Claude's shell reaches only the Docker socket, no other network. Claude's tool set is limited to `Bash`, `Edit`, `Read` and `Write` (no `Glob`, `Grep` or `TodoWrite`), so it searches and plans through the shell, unlike a default Claude Code session.
- **Unreviewed v0.1 lisp-skills advice.** The with-skills setup loads `dist/lisp-rules.md` from lisp-skills v0.1, which nobody on the team has reviewed. A difference between the setups says how this version of the text helped or hurt, not how good Lisp advice could be.
- **5 runs per setup.** Five counted runs per setup is a small sample. A difference of one or two passing runs can be chance.
- **Docker emulation timing.** On the Mac, `lisp-check` runs Allegro CL in an amd64 Docker image under x86 emulation. Durations include that overhead and the model's speed, so they don't predict timings at work (native Allegro, other hardware).
- **Human-written spec and tests.** The spec, the hidden tests and the reference implementation that validates them were written by the human side. Their wording and coverage shape what counts as correct; a different spec or test suite could rank the runs differently.
