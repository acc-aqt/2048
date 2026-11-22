# Findings: do the lisp-skills rules help a weak model write Common Lisp?

**Short answer: yes for the weakest model we tried, hardly at all for the other.** With the [lisp-skills](https://github.com/acc-aqt/lisp-skills) rules, Claude Code on `haiku` passed every run and needed about 40% fewer check-fix rounds and half the tokens. Codex on `gpt-6-luna` passed 3 of 5 runs with the rules and 3 of 5 without.

Date of the runs: 2026-11-22. Five counted runs per backend and setup, 20 in total.

## The question

Our team wants to use small, cheap models to write Common Lisp for Allegro CL, and nobody on the team knows Lisp well enough to review the code. The lisp-skills repo claims that its rules file (`dist/lisp-rules.md`) plus the `lisp-check` verify loop let small models write correct Allegro CL code. This repo tests that claim with a repeatable, hands-off experiment. The full spec is [issue #1](https://github.com/acc-aqt/2048/issues/1).

The plan was a local Qwen3-8B. It failed a simple Python smoke test, so the weakest hosted models at low effort stand in for "a weak model" ([ADR 0001](docs/adr/0001-drop-qwen3-8b-use-weakest-hosted-models.md)).

## The experiment

```text
spec (tasks/game-2048/spec.md): a terminal 2048 game in Common Lisp, fixed interface of 6 functions
  │
  ├── with-skills:    the agent also gets the lisp-skills rules as its project instructions
  │                   (work/CLAUDE.md for Claude Code, work/AGENTS.md for Codex)
  └── without-skills: the agent gets one sentence instead: "Run lisp-check FILE until it prints OK."
        │
        ▼
agent works alone in an empty folder, checks its files with lisp-check (each call = 1 round)
  limits: 40 rounds, 2 hours, $5 (Claude); one fixed "continue" message if it stops early
        │
        ▼
grading: every .lisp file must print OK, plus 66 hidden assertions the agent never sees
  PASS = all files OK + 66/66 hidden + no limit hit
```

| | Claude backend | Codex backend |
|---|---|---|
| Agent | Claude Code 2.1.330 | Codex CLI 0.164.0-alpha.11.1 |
| Model, effort | `haiku`, low | `gpt-6-luna`, low |
| Lisp | Allegro CL 11.0 Express in Docker (`lisp-skills-allegro:latest`) | same |
| Rules | lisp-skills `dist/lisp-rules.md` at `07effc0` | same |

Nobody edits the model's code. Each agent is isolated from the user's own setup: no personal instructions, plugins, skills, memory, subagents or web tools. It is sandboxed so it can't read the hidden tests, the reference solution, other runs or (without skills) the rules. Details are in the [README](README.md#isolation-and-confinement).

## Results

| Backend | Setup | Passed | Median hidden tests | Median rounds | Median duration | Median tokens | Median cost |
|---|---|---|---|---|---|---|---|
| Claude `haiku`/low | **with-skills** | **5/5** | 66/66 | **6** | **1.6 min** | **308k** | **$0.02** |
| Claude `haiku`/low | without-skills | 4/5 | 66/66 | 10 | 2.5 min | 599k | $0.03 |
| Codex `gpt-6-luna`/low | with-skills | 3/5 | 66/66 | 24 | 3.4 min | 996k | n/a |
| Codex `gpt-6-luna`/low | without-skills | 3/5 | 66/66 | 25 | 4.4 min | 1.18M¹ | n/a |

¹ Median of 4 runs: one run was stopped at the round limit before Codex reported its usage. Codex reports no cost.

Every run, as result, hidden tests passed and check-fix rounds:

| | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
|---|---|---|---|---|---|
| Claude with-skills | PASS 66/66, 5 | PASS 66/66, 4 | PASS 66/66, 9 | PASS 66/66, 9 | PASS 66/66, 6 |
| Claude without-skills | PASS 66/66, 9 | PASS 66/66, 10 | PASS 66/66, 16 | FAIL 66/66, 10 | PASS 66/66, 10 |
| Codex with-skills | PASS 66/66, 8 | PASS 66/66, 10 | PASS 66/66, 28 | FAIL 60/66, 24 | FAIL 59/66, 40 (limit) |
| Codex without-skills | PASS 66/66, 33 | FAIL 66/66, 41 (limit) | PASS 66/66, 25 | FAIL 59/66, 23 | PASS 66/66, 18 |

Full reports: [RESULTS-overview.md](RESULTS-overview.md), [RESULTS-claude.md](RESULTS-claude.md), [RESULTS-codex.md](RESULTS-codex.md). Every run's transcript, code and grading log is under [runs/](runs/).

## What this shows

- **The rules help the weakest model clearly.** Claude `haiku` with the rules never needed more than 9 rounds; without them it never needed fewer than 9. With the rules it also used about half the tokens and was a third faster. Without them, haiku worked out Allegro's `tester` module by trial and error and even searched the machine for documentation (the sandbox blocked it). Its one failure was its own tests file, which still didn't pass at the end. Its game code passed every hidden test.
- **Codex barely changed.** The pass rate was the same, and the rules saved some time and tokens but not rounds. Codex's failures were different from Claude's. Three runs got `move` wrong (59–60 of 66 hidden tests); in two of them the run's own tests passed anyway. Two runs hit the 40-round limit while their own tests file still failed.
- **Cheapest reliable setup: `haiku` with the rules,** at about $0.02 and under 2 minutes per run, 5 of 5 passed. It beat both Codex setups on every measure.
- **Weak models write working Lisp here, but they test poorly.** Two Codex runs ended with every file printing OK and their own tests passing, yet their `move` was wrong. Only the hidden tests caught it. A model's own tests are not enough evidence; independent tests are.

## Can the results be trusted?

- **Leaks were reviewed by hand.** 12 records carry `suspected_leak: true`. Every flagged transcript was read, and all are false positives. The repo path appears because the run's `lisp-check` is a symlink into the repo, because a `lisp-check` traceback names it, or because the agent read `harness/`, which `lisp-check` needs and the sandbox allows. Several without-skills agents tried to open the repo's `vendor/lisp-skills`, `reference/` or `docs/`, and the sandbox refused each time. No counted transcript contains lisp-skills text.
- **One practice run was contaminated, found and fixed.** The first Claude without-skills practice run found a lisp-skills copy left in an old Claude Code scratchpad under `/tmp/claude-<uid>`, a temp folder every Claude Code session on the machine shares, and read it. Both sandboxes now deny `/tmp` and the user's temp folder, the leak check also looks for those paths, and both Claude practice runs were redone. The contaminated record is kept in [runs/superseded-practice/](runs/superseded-practice/). The counted runs all ran with the fix.
- **The rules file stayed read-only.** Probe sessions confirmed that neither agent can overwrite, delete or rename its rules file, from the shell or with its file tools. It is byte-identical to the pinned rules in all 10 counted with-skills runs.
- **No subagents.** No run started a subagent, and Claude used only its Bash, Edit, Read and Write tools.

## Limits of this result

- **Small sample.** 5 runs per cell show a direction, not proof. The Claude difference is consistent across runs; the Codex difference is within noise.
- **One task, one machine.** One task (2048) on a Mac with Allegro in Docker under x86 emulation. The work setup (openSUSE, native Allegro) may behave differently, and durations don't transfer.
- **Model plus agent.** Each row measures a model together with its agent (Claude Code or Codex CLI), not the model alone, and hosted models change over time. Compare setups within one backend.
- **Unreviewed rules.** The rules are lisp-skills v0.1, which no one on the team has reviewed. A better or worse text could change the effect.
- **Open sandbox gap: [#14](https://github.com/acc-aqt/2048/issues/14).** The Docker socket that `lisp-check` needs also lets an agent start its own containers and mount host folders. One Codex run started containers, but mounted only its own work folder and read nothing it shouldn't. Fix this before further runs.
- **No shell here-documents.** Both backends lose shell here-documents (`cat > f <<EOF`) because their temp folder is unreadable. The agents write files with their file tools instead; it affects both setups equally.
- **Human-written grading.** The spec and hidden tests were written by the human side and validated against a private reference implementation. Different tests could rank runs differently.

## Reproduce

See [README: Running an experiment](README.md#running-an-experiment). In short, on a Mac with Docker, Claude Code and the Codex CLI logged in:

```sh
git submodule update --init
export PATH="$PWD/bin:$PATH"
bin/preflight --backend claude --backend codex
bin/run-batch game-2048 --backend claude --records-dir runs/claude
bin/run-batch game-2048 --backend codex  --records-dir runs/codex
bin/results game-2048 --overview runs/claude runs/codex
```

To play the best game (Claude with-skills run 2), see the "Play the best game" section of [RESULTS-claude.md](RESULTS-claude.md#play-the-best-game).
