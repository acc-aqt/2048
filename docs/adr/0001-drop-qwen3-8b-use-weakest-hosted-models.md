# 0001: Drop local Qwen3-8B; run the experiment with the weakest hosted Codex and Claude models

Date: 2026-11-21

## Status

Accepted. Supersedes the model choice in issue #1.

## Context

Issue #1 planned to prove that an on-prem Qwen3-8B, driven by OpenCode, can write Common Lisp with the lisp-skills rules. Locally that meant `qwen3:8b` Q4_K_M in Ollama with a 32k context on a 16 GB M2 Pro.

Before any Lisp run, a hand-driven smoke test asked that model to build a simple FastAPI server in Python. It did not perform well enough. A model that struggles with a small Python task in a well-known framework would not give a meaningful result on Lisp, so the 2048 runs would only measure model weakness, not the effect of the skills.

## Decision

The default Mac benchmark runs hosted agents on their weakest available models at low reasoning effort:

- Codex CLI: model `gpt-6-luna`, `low` reasoning effort, one agent (no multi-agent).
- Claude Code: model `haiku`, `low` effort, with no user CLAUDE.md, plugins, memory, subagents or web tools (built: [#10](https://github.com/acc-aqt/2048/issues/10), part of [#8](https://github.com/acc-aqt/2048/issues/8)).

In `with-skills`, the pinned rules reach each agent through its own project instructions file: a generated `AGENTS.md` for Codex and a generated `CLAUDE.md` for Claude Code.

These stand in for "small, cheap model" while still being able to drive an agent loop. Everything else stays: the task and spec, the 66 hidden tests, `lisp-check`, the two setups (`with-skills` and `without-skills`), the limits, the continue message, the practice run and the batch of 5 counted runs per setup.

Each backend writes its own records folder and `RESULTS` file, and the backends are compared as end-to-end setups (model plus agent harness), not as models alone.

## Consequences

- The question changes from "can an on-prem 8B model do it?" to "do the lisp-skills rules help a weak model write working Lisp?" The result does not by itself prove anything about Qwen3-8B on-prem.
- The OpenCode backend and `bin/preflight`'s OpenAI-compatible model check stay as an alternate, because the openSUSE/LiteLLM work setup still needs them. `bin/preflight` gains Claude and Codex login checks.
- Runs cost API usage and need logged-in Codex and Claude accounts; they no longer run fully offline.
- Hosted models change over time. Every record stores the model name and effort, so a rerun can tell which model it compared against.
