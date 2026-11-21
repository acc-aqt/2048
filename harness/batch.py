"""Run the counted runs of a task for both setups back to back, unattended.

The setup that goes first alternates from run to run, so a slow or fast stretch of the
night doesn't favour one setup. Runs that already have a record are skipped, so an
interrupted batch resumes where it stopped. A failed run doesn't stop the batch.
"""

import argparse
import os
import subprocess
from pathlib import Path

from harness.grade import DEFAULT_CHECK_TIMEOUT
from harness.runner import (BACKENDS, DEFAULT_MAX_ROUNDS, DEFAULT_RECORDS, DEFAULT_RUN_ROOT, DEFAULT_TIMEOUT,
                            REPO, TASKS, has_record)
from harness.setups import SETUPS

RUN_TASK = REPO / "bin" / "run-task"
COUNTED_RUNS = range(1, 6)


def schedule(setups=tuple(SETUPS), runs=COUNTED_RUNS):
    """(setup, run number) pairs: run 1 in setup order, run 2 reversed, and so on."""
    order = []
    for number in runs:
        names = setups if number % 2 else tuple(reversed(setups))
        order.extend((name, number) for name in names)
    return order


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="run-batch", description=__doc__)
    parser.add_argument("task", help="folder name under tasks/")
    parser.add_argument("--run-root", default=os.environ.get("RUN_ROOT", DEFAULT_RUN_ROOT), help="passed to every run-task call")
    parser.add_argument("--records-dir", default=str(DEFAULT_RECORDS), help="passed to every run-task call")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="passed to every run-task call")
    parser.add_argument("--check-timeout", type=int, default=DEFAULT_CHECK_TIMEOUT, help="passed to every run-task call")
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS, help="passed to every run-task call")
    parser.add_argument("--backend", choices=sorted(BACKENDS), default="opencode", help="passed to every run-task call")
    parser.add_argument("--model", help="passed to every run-task call")
    parser.add_argument("--reasoning-effort", help="passed to every run-task call")
    args = parser.parse_args(argv)
    if not (TASKS / args.task / "spec.md").is_file():
        parser.error(f"unknown task '{args.task}': no tasks/{args.task}/spec.md")
    return args


def main(argv):
    args = parse_args(argv)
    records = Path(args.records_dir).resolve()
    flags = ["--run-root", args.run_root, "--records-dir", str(records),
             "--timeout", str(args.timeout), "--check-timeout", str(args.check_timeout),
             "--max-rounds", str(args.max_rounds), "--backend", args.backend]
    for flag, value in (("--model", args.model), ("--reasoning-effort", args.reasoning_effort)):
        if value:
            flags += [flag, value]
    failed = []
    for setup, number in schedule():
        label = f"{args.task} {setup} #{number}"
        if has_record(records / args.task / setup / str(number)):
            print(f"run-batch: skip {label}: record exists", flush=True)
            continue
        print(f"run-batch: start {label}", flush=True)
        completed = subprocess.run([str(RUN_TASK), args.task, setup, str(number), *flags],
                                   stdin=subprocess.DEVNULL)
        if completed.returncode != 0:
            failed.append(label)
            print(f"run-batch: run-task failed for {label} (exit {completed.returncode})", flush=True)
    print(f"run-batch: done, {len(failed)} failed" + (f": {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0
