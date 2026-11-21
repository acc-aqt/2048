"""Write RESULTS.md for a task from its result records."""

import argparse
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

from harness.batch import COUNTED_RUNS
from harness.runner import CONTINUE_MESSAGE, DEFAULT_RECORDS, PRACTICE_RUN, REPO, TASKS, task_files
from harness.setups import SETUPS

LISP_SKILLS = REPO / "vendor" / "lisp-skills"
RUN_COLUMNS = ["Setup", "Run", "Check-fix rounds", "Hidden tests", "Duration", "Limit hit",
               "Continue sent", "Result"]
SUMMARY_COLUMNS = ["Setup", "Counted runs", "Passed", "Median hidden tests", "Median rounds",
                   "Median duration"]

BACKENDS = {
    "opencode": {"agent": "OpenCode", "driven": "driven by OpenCode with thinking mode on and a 32k context",
                 "rules": "as always-loaded OpenCode instructions"},
    "codex": {"agent": "Codex CLI", "driven": "driven by the Codex CLI, isolated from the user's Codex config, plugins and bundled skills",
              "rules": "as a generated `AGENTS.md` in the model folder"},
    "claude": {"agent": "Claude Code",
               "driven": ("driven by Claude Code, isolated from the user's `CLAUDE.md`, plugins and memory, with no skills, "
                          "subagents or web tools, its file tools and sandboxed shell confined to the model folder"),
               "rules": "as a generated `CLAUDE.md` in the model folder"},
}

QUANTISATION_THREAT = """\
- **Q4_K_M, not FP8.** The local runs used Qwen3-8B quantised to Q4_K_M through Ollama. At work the model is served as FP8 behind LiteLLM. Q4 usually loses some quality, so treat local results as a lower bound for the work setup.
"""

HOSTED_THREAT = """\
- **Model plus agent harness.** Each hosted run measures the model together with its agent harness (Claude Code or the Codex CLI), not the model alone. The hosted models also change over time; every record names the model and effort it ran with.
"""

MIXED_BACKENDS_THREAT = """\
- **Different agent harnesses.** Rows from different backends differ in model, agent harness, tools and token accounting at once. Compare the two setups within one backend first; a difference between backends is not a model-only comparison. Runs get no agent skills or plugins on any backend, and the only extra text a `with-skills` run gets is the rules file, but each agent's built-in system prompt and tools still differ (Claude Code vs the Codex CLI) and can't be removed.
"""

BACKEND_THREATS = {
    "codex": """\
- **Codex shell network.** Codex shell commands have open network access: its sandbox enables the network so `lisp-check` can reach Docker, so a run could download code (web search itself is off).
""",
    "claude": """\
- **Claude's sandbox and tool set.** Claude's shell reaches only the Docker socket, no other network. Claude's tool set is limited to `Bash`, `Edit`, `Read` and `Write` (no `Glob`, `Grep` or `TodoWrite`), so it searches and plans through the shell, unlike a default Claude Code session.
""",
}

THREATS = """\
- **Unreviewed v0.1 lisp-skills advice.** The with-skills setup loads `dist/lisp-rules.md` from lisp-skills v0.1, which nobody on the team has reviewed. A difference between the setups says how this version of the text helped or hurt, not how good Lisp advice could be.
- **5 runs per setup.** Five counted runs per setup is a small sample. A difference of one or two passing runs can be chance.
- **Docker emulation timing.** On the Mac, `lisp-check` runs Allegro CL in an amd64 Docker image under x86 emulation. Durations include that overhead and the model's speed, so they don't predict timings at work (native Allegro, other hardware).
- **Human-written spec and tests.** The spec, the hidden tests and the reference implementation that validates them were written by the human side. Their wording and coverage shape what counts as correct; a different spec or test suite could rank the runs differently.
"""


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="results", description=__doc__)
    parser.add_argument("task", help="folder name under tasks/")
    parser.add_argument("--records-dir", default=str(DEFAULT_RECORDS),
                        help="where result records are (default: runs/ in the repo)")
    parser.add_argument("--overview", nargs="+", metavar="RECORDS_DIR",
                        help="write one overview table from several records directories instead")
    parser.add_argument("--output", help="default: RESULTS.md, or RESULTS-overview.md with --overview, in the repo")
    args = parser.parse_args(argv)
    if args.output is None:
        args.output = str(REPO / ("RESULTS-overview.md" if args.overview else "RESULTS.md"))
    if not (TASKS / args.task / "spec.md").is_file():
        parser.error(f"unknown task '{args.task}': no tasks/{args.task}/spec.md")
    return args


def load_records(records_dir, task):
    records = [json.loads(path.read_text()) for path in Path(records_dir).glob(f"{task}/*/*/result.json")]
    return sorted(records, key=lambda r: (r["run_number"], sorted(SETUPS).index(r["setup"])))


def lisp_skills_commit():
    completed = subprocess.run(["git", "-C", str(LISP_SKILLS), "rev-parse", "HEAD"],
                               capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


PLAY_FUNCTION = re.compile(r"^#+ `\(play[ )]", re.MULTILINE)


def records_location(records_dir, output):
    """RECORDS_DIR as written in RESULTS.md: relative to the output file's folder if inside it, else absolute."""
    records_dir, base = Path(records_dir).resolve(), Path(output).resolve().parent
    return str(records_dir.relative_to(base)) if records_dir.is_relative_to(base) else str(records_dir)


def record_path(records, record):
    return f"{records}/{record['task']}/{record['setup']}/{record['run_number']}"


def defines_play(task):
    return bool(PLAY_FUNCTION.search((TASKS / task / "spec.md").read_text()))


def minutes(seconds):
    return f"{seconds / 60:.1f}".removesuffix(".0") + " min"


def number(value):
    return f"{value:g}"


def table(columns, rows):
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def run_row(r):
    return [r["setup"], r["run_number"], r["check_fix_rounds"],
            f"{r['hidden_tests_passed']}/{r['hidden_tests_total']}", minutes(r["duration_seconds"]),
            r["limit_hit"] or "-", "yes" if r["continue_sent"] else "no", "PASS" if r["passed"] else "FAIL"]


USAGE_COLUMNS = {"total_tokens": "Median tokens", "cost_usd": "Median cost"}


def usage_fields(records):
    """The optional usage fields that at least one record has a value for."""
    return [field for field in USAGE_COLUMNS if any(r.get(field) is not None for r in records)]


def tokens(value):
    return f"{round(value):,}"


def dollars(value):
    return f"${value:.2f}"


def usage_text(field, value):
    if value is None:
        return "n/a"
    return (tokens if field == "total_tokens" else dollars)(value)


def median_usage(runs, field):
    values = [r[field] for r in runs if r.get(field) is not None]
    return usage_text(field, statistics.median(values) if values else None)


def summary_row(setup, runs, fields=()):
    if not runs:
        return [setup, 0] + ["-"] * (4 + len(fields))
    total = number(statistics.median(r["hidden_tests_total"] for r in runs))
    return [setup, len(runs), f"{sum(r['passed'] for r in runs)}/{len(runs)}",
            f"{number(statistics.median(r['hidden_tests_passed'] for r in runs))}/{total}",
            number(statistics.median(r["check_fix_rounds"] for r in runs)),
            minutes(statistics.median(r["duration_seconds"] for r in runs))] + [
        median_usage(runs, field) for field in fields]


def joined(values):
    return ", ".join(f"`{value}`" for value in sorted(set(values))) or "unknown"


def backend_of(record):
    return record.get("backend", "opencode")


def backends(records):
    return [name for name in BACKENDS if any(backend_of(r) == name for r in records)] or ["opencode"]


def effort_text(runs):
    efforts = sorted({r["reasoning_effort"] for r in runs if r.get("reasoning_effort")})
    return f" at {joined(efforts)} effort" if efforts else ""


def model_text(records):
    return "; ".join(
        f"{joined(r['model'] for r in runs)}{effort_text(runs)}, {BACKENDS[name]['driven']}"
        for name in backends(records) for runs in [[r for r in records if backend_of(r) == name]])


def listing(items):
    return " and ".join(filter(None, [", ".join(items[:-1]), items[-1]]))


def rules_text(records):
    names = backends(records)
    if len(names) == 1:
        return BACKENDS[names[0]]["rules"]
    return listing([f"{BACKENDS[name]['rules']} for {BACKENDS[name]['agent']}" for name in names])


def agents_text(records):
    return " or ".join(BACKENDS[name]["agent"] for name in backends(records))


def threats(records):
    names = backends(records)
    hosted = HOSTED_THREAT if set(names) - {"opencode"} else ""
    mixed = MIXED_BACKENDS_THREAT if len(names) > 1 else ""
    per_backend = "".join(BACKEND_THREATS.get(name, "") for name in names)
    return (QUANTISATION_THREAT if "opencode" in names else "") + hosted + mixed + per_backend + THREATS


def limits_text(records):
    distinct = sorted({json.dumps(r["limits"], sort_keys=True) for r in records})
    return "; ".join(
        f"{limits['max_rounds']} check-fix rounds, {minutes(limits['timeout_seconds'])} wall clock, "
        f"{limits['check_timeout_seconds']} s per grading check"
        for limits in map(json.loads, distinct)) or "unknown"


def method(task, records, commit, locations):
    return f"""\
- **Model:** {model_text(records)}.
- **Task:** `tasks/{task}/spec.md`, the same text for every run.
- **Setups:** `with-skills` gets the lisp-skills rules (`vendor/lisp-skills/dist/lisp-rules.md`, lisp-skills commit `{commit}`) {rules_text(records)}; `without-skills` gets only the sentence "Run lisp-check FILE until it prints OK." Nothing else differs.
- **Runs:** {len(COUNTED_RUNS)} counted runs per setup, run with `bin/run-batch`, alternating which setup goes first. Run {PRACTICE_RUN} was an uncounted practice run. Every run starts in a fresh, empty folder.
- **Human input:** one fixed prompt, and at most once the fixed message "{CONTINUE_MESSAGE}" if the model stopped before every file printed OK. Nobody edited the model's code.
- **Limits:** {limits_text(records)}. Hitting a limit fails the run.
- **Pass:** every `.lisp` file prints OK in `lisp-check` and all hidden tests ({joined(r['hidden_tests_total'] for r in records)} assertions) pass through `lisp-check --test`. The model never saw the hidden tests.
- **Records:** {listing([f"`{location}/{task}/<setup>/<run>/`" for location in locations])} {"holds" if len(locations) == 1 else "hold"} `result.json`, the transcript, the exported session, the round log, the grading log and `src/`, the model's final files.
"""


def leaks_section(flagged):
    """FLAGGED: (label, record path) of every run whose transcript names the repo, hidden tests or reference."""
    if not flagged:
        return "No run is flagged: no transcript names the repo, `hidden-tests` or `reference/`.\n"
    items = "\n".join(f"- {label}`{path}`" for label, path in flagged)
    return f"""\
These runs' transcripts name the repo, `hidden-tests` or `reference/`, so the model may have looked for the hidden tests or the reference solution. Their results stand as recorded; review each transcript before trusting it:

{items}
"""


def play_section(task, counted, location):
    passing = [r for r in counted if r["passed"]]
    if not passing:
        return "No counted run passed, so there is no game to play.\n"
    best = min(passing, key=lambda r: (r["check_fix_rounds"], r["duration_seconds"]))
    src = f"{record_path(location, best)}/src"
    system = next((Path(name).stem for name in task_files((TASKS / task / "spec.md").read_text())
                   if name.endswith(".asd")), task)
    forms = (f"-e '(require :asdf)' -e '(asdf:load-asd (truename \"{system}.asd\"))' "
             f"-e '(asdf:load-system \"{system}\")' -e '({system}:play)' -kill")
    return f"""\
The best passing run is **{best['setup']} #{best['run_number']}** ({best['check_fix_rounds']} check-fix rounds, {minutes(best['duration_seconds'])}); passing runs are ranked by fewest rounds, then shortest duration. Its code is in `{src}`.

Copy `src/` to a temporary folder first, so the compiled files Allegro writes don't end up in the record:

```sh
play_dir=$(mktemp -d)
cp -R {src}/. "$play_dir"
cd "$play_dir"
```

Then, on a Mac, with the `lisp-skills-allegro` Docker image:

```sh
docker run --rm -it --platform linux/amd64 -v "$PWD:$PWD" -w "$PWD" lisp-skills-allegro:latest \\
  alisp -qq {forms}
```

Or with Allegro CL installed natively:

```sh
alisp -qq {forms}
```

Allegro prints its compile messages first, then the board. Type `w`, `a`, `s` or `d` and Enter to move, `q` to quit.
"""


def render(task, records, commit, location):
    counted = [r for r in records if r["counted"]]
    practice = [r for r in records if not r["counted"]]
    expected = len(SETUPS) * len(COUNTED_RUNS)
    fields = usage_fields(counted)
    summaries = [summary_row(setup, [r for r in counted if r["setup"] == setup], fields) for setup in sorted(SETUPS)]
    summary_columns = SUMMARY_COLUMNS + [USAGE_COLUMNS[field] for field in fields]
    practice_text = table(RUN_COLUMNS, map(run_row, practice)) if practice else "No practice run recorded."
    example = record_path(location, counted[0]) if counted else f"{location}/{task}/with-skills/1"
    play = f"\n## Play the best game\n\n{play_section(task, counted, location)}" if defines_play(task) else ""
    return f"""\
# Results: {task}

Generated by `bin/results {task}` from the result records in `{location}/{task}/`. {len(counted)} of {expected} counted runs have a record.

## Summary per setup

{table(summary_columns, summaries)}

Medians are over the counted runs of each setup. Durations are the time spent in {agents_text(records)} turns, both together, as counted by the wall-clock limit: not the status check between turns, the export or grading.

## Counted runs

{table(RUN_COLUMNS, map(run_row, counted))}

## Practice run (not counted)

{practice_text}

## Suspected leaks

{leaks_section([("", record_path(location, r)) for r in records if r.get("suspected_leak")])}
## Method

{method(task, records, commit, [location])}
## Threats to validity

{threats(records)}
## Rerun the hidden tests yourself

`bin/regrade` copies a run's saved `src/` into a temporary folder, adds the hidden tests from `tasks/{task}/hidden-tests/`, grades it with the same `lisp-check` commands as the run did, prints every file's status and the hidden-test score, and says whether that matches the run's `result.json` (exit 0 if it does, 1 if not):

```sh
export PATH="$PWD/bin:$PATH"
bin/regrade {example}
```

Any record folder works. Set `LISP_CHECK_MODE=native` to use an installed Allegro CL instead of Docker.
{play}"""


OVERVIEW_COLUMNS = ["Backend", "Model", "Effort", "Setup", "Counted runs", "Passed", "Median hidden tests",
                    "Median rounds", "Median duration", "Median tokens", "Median cost", "Records"]


def plain(values):
    return ", ".join(sorted({value for value in values if value})) or "-"


def overview_groups(sources):
    """(location, backend, setup, records) per records directory, backend and setup that has records."""
    for location, records in sources:
        for name in backends(records):
            for setup in sorted(SETUPS):
                runs = [r for r in records if backend_of(r) == name and r["setup"] == setup]
                if runs:
                    yield location, name, setup, runs


def overview_row(location, backend, setup, runs):
    counted = [r for r in runs if r["counted"]]
    summary = summary_row(setup, counted, list(USAGE_COLUMNS))[1:]
    return [backend, plain(r["model"] for r in runs), plain(r.get("reasoning_effort") for r in runs), setup,
            *summary, location]


PRACTICE_COLUMNS = ["Backend"] + RUN_COLUMNS + ["Tokens", "Cost", "Records"]


def practice_row(location, record):
    return [backend_of(record), *run_row(record), *(usage_text(field, record.get(field)) for field in USAGE_COLUMNS),
            location]


def render_overview(task, sources, commit):
    records = [r for _, runs in sources for r in runs]
    groups = list(overview_groups(sources))
    rows = [overview_row(*group) for group in groups]
    practice = [practice_row(location, r) for location, _, _, runs in groups for r in runs if not r["counted"]]
    practice_text = table(PRACTICE_COLUMNS, practice) if practice else "No practice run recorded."
    flagged = [(f"{backend}: ", record_path(location, r))
               for location, backend, _, runs in groups for r in runs if r.get("suspected_leak")]
    return f"""\
# Results overview: {task}

## Overview

{table(OVERVIEW_COLUMNS, rows)}

Each row covers the counted runs (1 to {COUNTED_RUNS[-1]}) of one backend and setup from the records directory in its last column. Medians are over those runs; "n/a" means the records hold no value (Codex and OpenCode report no cost).

## Practice runs (not counted)

{practice_text}

## Suspected leaks

{leaks_section(flagged)}
## Method

{method(task, records, commit, [location for location, _ in sources])}
## Threats to validity

{threats(records)}"""


def mixing_error(task, records_dir, records):
    """Why RECORDS from RECORDS_DIR can't go into an overview of TASK, or None if they can."""
    others = sorted({r["task"] for r in records if r["task"] != task})
    if others:
        return f"{records_dir} has records for {', '.join(others)} under {task}/; refusing to mix tasks"
    if not records:
        found = sorted({path.parts[-4] for path in Path(records_dir).glob("*/*/*/result.json")})
        return f"{records_dir} has no records for {task} (found: {', '.join(found) or 'none'})"
    return None


def overview(args):
    sources = []
    for records_dir in args.overview:
        records = load_records(records_dir, args.task)
        error = mixing_error(args.task, records_dir, records)
        if error:
            print(f"results: {error}", file=sys.stderr)
            return 2
        sources.append((records_location(records_dir, args.output), records))
    Path(args.output).write_text(render_overview(args.task, sources, lisp_skills_commit()))
    count = sum(len(records) for _, records in sources)
    print(f"results: wrote {args.output} from {count} records in {len(sources)} records directories")
    return 0


def main(argv):
    args = parse_args(argv)
    if args.overview:
        return overview(args)
    records = load_records(args.records_dir, args.task)
    location = records_location(args.records_dir, args.output)
    Path(args.output).write_text(render(args.task, records, lisp_skills_commit(), location))
    print(f"results: wrote {args.output} from {len(records)} records")
    return 0
