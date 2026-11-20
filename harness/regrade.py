"""Regrade a saved run: run the task's hidden tests against the run's saved src/ and compare with its record."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from harness.grade import DEFAULT_CHECK_TIMEOUT, grade
from harness.runner import TASKS, task_files


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="regrade", description=__doc__)
    parser.add_argument("record", help="a run's record folder, for example runs/game-2048/with-skills/3")
    parser.add_argument("--check-timeout", type=int, default=DEFAULT_CHECK_TIMEOUT,
                        help=f"seconds before one lisp-check is killed (default {DEFAULT_CHECK_TIMEOUT})")
    args = parser.parse_args(argv)
    args.record = Path(args.record).resolve()
    if not (args.record / "result.json").is_file():
        parser.error(f"{args.record} has no result.json")
    return args


def summary(source_files, passed, total):
    return f"hidden tests {passed}/{total}, files " + ", ".join(
        f"{name} {status}" for name, status in sorted(source_files.items()))


def regrade(record, check_timeout=DEFAULT_CHECK_TIMEOUT):
    result = json.loads((record / "result.json").read_text())
    task_dir = TASKS / result["task"]
    required = task_files((task_dir / "spec.md").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        return result, grade(record / "src", task_dir / "hidden-tests", Path(tmp) / "grading",
                             required, check_timeout)


def main(argv):
    args = parse_args(argv)
    recorded, graded = regrade(args.record, args.check_timeout)
    print(f"{recorded['task']} {recorded['setup']} #{recorded['run_number']}: regraded {args.record / 'src'}")
    for name, status in sorted(graded["source_files"].items()):
        print(f"  {name} {status}")
    print(f"hidden tests {graded['hidden_tests_passed']}/{graded['hidden_tests_total']}")
    print("PASS" if graded["passed"] else "FAIL")
    if graded["passed"] and recorded.get("limit_hit"):
        print(f"run failed anyway: limit hit ({recorded['limit_hit']})")

    now = summary(graded["source_files"], graded["hidden_tests_passed"], graded["hidden_tests_total"])
    before = summary(recorded["source_files"], recorded["hidden_tests_passed"], recorded["hidden_tests_total"])
    if now == before:
        print("matches the record")
        return 0
    print(f"differs from the record, which says: {before}")
    return 1
