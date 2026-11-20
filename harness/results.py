"""Write RESULTS.md for a task from its result records."""

import argparse
import json
import re
import statistics
import subprocess
from pathlib import Path

from harness.batch import COUNTED_RUNS
from harness.runner import CONTINUE_MESSAGE, DEFAULT_RECORDS, PRACTICE_RUN, REPO, TASKS, task_files
from harness.setups import SETUPS

LISP_SKILLS = REPO / "vendor" / "lisp-skills"
RUN_COLUMNS = ["Setup", "Run", "Check-fix rounds", "Hidden tests", "Duration", "Limit hit",
               "Continue sent", "Result"]
SUMMARY_COLUMNS = ["Setup", "Counted runs", "Passed", "Median hidden tests", "Median rounds",
                   "Median duration"]

THREATS = """\
- **Q4_K_M, not FP8.** The local runs used Qwen3-8B quantised to Q4_K_M through Ollama. At work the model is served as FP8 behind LiteLLM. Q4 usually loses some quality, so treat local results as a lower bound for the work setup.
- **Unreviewed v0.1 lisp-skills advice.** The with-skills setup loads `dist/lisp-rules.md` from lisp-skills v0.1, which nobody on the team has reviewed. A difference between the setups says how this version of the text helped or hurt, not how good Lisp advice could be.
- **5 runs per setup.** Five counted runs per setup is a small sample. A difference of one or two passing runs can be chance.
- **Docker emulation timing.** On the Mac, `lisp-check` runs Allegro CL in an amd64 Docker image under x86 emulation. Durations include that overhead and the local model's speed, so they don't predict timings at work (native Allegro, other hardware).
- **Human-written spec and tests.** The spec, the hidden tests and the reference implementation that validates them were written by the human side. Their wording and coverage shape what counts as correct; a different spec or test suite could rank the runs differently.
"""


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="results", description=__doc__)
    parser.add_argument("task", help="folder name under tasks/")
    parser.add_argument("--records-dir", default=str(DEFAULT_RECORDS),
                        help="where result records are (default: runs/ in the repo)")
    parser.add_argument("--output", default=str(REPO / "RESULTS.md"), help="default: RESULTS.md in the repo")
    args = parser.parse_args(argv)
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


def summary_row(setup, runs):
    if not runs:
        return [setup, 0, "-", "-", "-", "-"]
    total = number(statistics.median(r["hidden_tests_total"] for r in runs))
    return [setup, len(runs), f"{sum(r['passed'] for r in runs)}/{len(runs)}",
            f"{number(statistics.median(r['hidden_tests_passed'] for r in runs))}/{total}",
            number(statistics.median(r["check_fix_rounds"] for r in runs)),
            minutes(statistics.median(r["duration_seconds"] for r in runs))]


def joined(values):
    return ", ".join(f"`{value}`" for value in sorted(set(values))) or "unknown"


def limits_text(records):
    distinct = sorted({json.dumps(r["limits"], sort_keys=True) for r in records})
    return "; ".join(
        f"{limits['max_rounds']} check-fix rounds, {minutes(limits['timeout_seconds'])} wall clock, "
        f"{limits['check_timeout_seconds']} s per grading check"
        for limits in map(json.loads, distinct)) or "unknown"


def method(task, records, commit, location):
    return f"""\
- **Model:** {joined(r['model'] for r in records)}, driven by OpenCode with thinking mode on and a 32k context.
- **Task:** `tasks/{task}/spec.md`, the same text for every run.
- **Setups:** `with-skills` gets the lisp-skills rules (`vendor/lisp-skills/dist/lisp-rules.md`, lisp-skills commit `{commit}`) as always-loaded instructions; `without-skills` gets only the sentence "Run lisp-check FILE until it prints OK." Nothing else differs.
- **Runs:** {len(COUNTED_RUNS)} counted runs per setup, run with `bin/run-batch`, alternating which setup goes first. Run {PRACTICE_RUN} was an uncounted practice run. Every run starts in a fresh, empty folder.
- **Human input:** one fixed prompt, and at most once the fixed message "{CONTINUE_MESSAGE}" if the model stopped before every file printed OK. Nobody edited the model's code.
- **Limits:** {limits_text(records)}. Hitting a limit fails the run.
- **Pass:** every `.lisp` file prints OK in `lisp-check` and all hidden tests ({joined(r['hidden_tests_total'] for r in records)} assertions) pass through `lisp-check --test`. The model never saw the hidden tests.
- **Records:** `{location}/{task}/<setup>/<run>/` holds `result.json`, the transcript, the exported session, the round log, the grading log and `src/`, the model's final files.
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
    summaries = [summary_row(setup, [r for r in counted if r["setup"] == setup]) for setup in sorted(SETUPS)]
    practice_text = table(RUN_COLUMNS, map(run_row, practice)) if practice else "No practice run recorded."
    example = record_path(location, counted[0]) if counted else f"{location}/{task}/with-skills/1"
    play = f"\n## Play the best game\n\n{play_section(task, counted, location)}" if defines_play(task) else ""
    return f"""\
# Results: {task}

Generated by `bin/results {task}` from the result records in `{location}/{task}/`. {len(counted)} of {expected} counted runs have a record.

## Summary per setup

{table(SUMMARY_COLUMNS, summaries)}

Medians are over the counted runs of each setup. Durations are the time spent in OpenCode turns, both together, as counted by the wall-clock limit: not the status check between turns, the export or grading.

## Counted runs

{table(RUN_COLUMNS, map(run_row, counted))}

## Practice run (not counted)

{practice_text}

## Method

{method(task, records, commit, location)}
## Threats to validity

{THREATS}
## Rerun the hidden tests yourself

`bin/regrade` copies a run's saved `src/` into a temporary folder, adds the hidden tests from `tasks/{task}/hidden-tests/`, grades it with the same `lisp-check` commands as the run did, prints every file's status and the hidden-test score, and says whether that matches the run's `result.json` (exit 0 if it does, 1 if not):

```sh
export PATH="$PWD/bin:$PATH"
bin/regrade {example}
```

Any record folder works. Set `LISP_CHECK_MODE=native` to use an installed Allegro CL instead of Docker.
{play}"""


def main(argv):
    args = parse_args(argv)
    records = load_records(args.records_dir, args.task)
    location = records_location(args.records_dir, args.output)
    Path(args.output).write_text(render(args.task, records, lisp_skills_commit(), location))
    print(f"results: wrote {args.output} from {len(records)} records")
    return 0
