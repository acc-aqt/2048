"""Grade a project folder: check every .lisp file, then run the hidden tests on a copy."""

import os
import re
import shutil
import subprocess
from pathlib import Path

LISP_CHECK = Path(__file__).resolve().parent.parent / "bin" / "lisp-check"
DEFAULT_CHECK_TIMEOUT = 120
HIDDEN_TESTS_FOLDER = "hidden-tests"
TIMED_OUT = re.compile(r"^lisp-check: timed out after ", re.MULTILINE)

ASSERTION = re.compile(r"^\((?:util\.test:)?test(?:-[a-z-]+)?[\s)]", re.MULTILINE)
FAILED_ASSERTIONS = re.compile(r": test: (\d+) of (\d+) assertions failed")


def is_test_file(path):
    return path.name.endswith("tests.lisp")


def count_assertions(path):
    """Hidden test files keep one assertion per top-level tester form, so they can be counted."""
    return len(ASSERTION.findall(path.read_text()))


def printed_ok(result):
    """Like preflight: exit code 0 and OK as the last line of stdout. Stderr (Docker warnings) is ignored."""
    return result.returncode == 0 and result.stdout.splitlines()[-1:] == ["OK"]


def assertions_passed(result, total):
    if printed_ok(result):
        return total
    failed = FAILED_ASSERTIONS.search(result.stdout)
    if failed:
        return int(failed.group(2)) - int(failed.group(1))
    return 0


def status(result):
    if printed_ok(result):
        return "OK"
    return "TIMEOUT" if TIMED_OUT.search(result.stdout) else "FAIL"


def lisp_check(relative, cwd, test, check_timeout):
    """One lisp-check that is not a model round: own log, killed after CHECK_TIMEOUT seconds."""
    args = (["--test"] if test else []) + [str(relative)]
    env = dict(os.environ, LISP_CHECK_LOG=str(cwd / ".grading-lisp-check.log"),
               LISP_CHECK_TIMEOUT=str(check_timeout))
    result = subprocess.run(
        [str(LISP_CHECK), *args], cwd=cwd, env=env,
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
    )
    return result, f"$ lisp-check {' '.join(args)}\n{result.stdout}{result.stderr}"


def copy_project(project_dir, grading_dir):
    shutil.copytree(project_dir, grading_dir, ignore=shutil.ignore_patterns(".git"))
    (grading_dir / ".git").mkdir(exist_ok=True)


def unused_folder(parent, name):
    """PARENT/NAME, or PARENT/NAME-2, -3, ... if the model already made that path."""
    candidate, number = parent / name, 1
    while candidate.exists() or candidate.is_symlink():
        number += 1
        candidate = parent / f"{name}-{number}"
    return candidate


def copy_hidden_tests(hidden_tests_dir, grading_dir):
    """Copy the hidden tests into a folder of their own in GRADING_DIR, so no model file can clash with them.

    lisp-check still finds the project's .asd: it looks in the test file's folder, then upwards.
    """
    target_dir = unused_folder(grading_dir, HIDDEN_TESTS_FOLDER)
    hidden = []
    for source in sorted(hidden_tests_dir.rglob("*.lisp")):
        target = target_dir / source.relative_to(hidden_tests_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hidden.append(target.relative_to(grading_dir))
    return hidden


def check_project_files(grading_dir, required_files=(), check_timeout=DEFAULT_CHECK_TIMEOUT):
    """lisp-check every .lisp file in GRADING_DIR: OK, FAIL, TIMEOUT, or MISSING for any absent required file."""
    present = {str(p.relative_to(grading_dir)) for p in grading_dir.rglob("*.lisp")}
    statuses, log = {}, []
    for name in required_files:
        if not (grading_dir / name).is_file():
            statuses[name] = "MISSING"
    for name in sorted(present):
        result, entry = lisp_check(Path(name), grading_dir, is_test_file(Path(name)), check_timeout)
        statuses[name] = status(result)
        log.append(entry)
    return dict(sorted(statuses.items())), log


def all_files_ok(project_dir, check_dir, required_files=(), check_timeout=DEFAULT_CHECK_TIMEOUT):
    """True if every required file in PROJECT_DIR exists and every .lisp file prints OK, checked in a copy."""
    copy_project(Path(project_dir), Path(check_dir))
    statuses, _ = check_project_files(Path(check_dir), required_files, check_timeout)
    return bool(statuses) and set(statuses.values()) == {"OK"}


def grade(project_dir, hidden_tests_dir, grading_dir, required_files=(), check_timeout=DEFAULT_CHECK_TIMEOUT):
    """Grade PROJECT_DIR in a fresh GRADING_DIR; PROJECT_DIR itself is never changed."""
    project_dir, hidden_tests_dir, grading_dir = map(Path, (project_dir, hidden_tests_dir, grading_dir))
    copy_project(project_dir, grading_dir)
    source_files, log = check_project_files(grading_dir, required_files, check_timeout)
    hidden_files = copy_hidden_tests(hidden_tests_dir, grading_dir)

    total = passed = 0
    for relative in hidden_files:
        file_total = count_assertions(grading_dir / relative)
        result, entry = lisp_check(relative, grading_dir, True, check_timeout)
        total += file_total
        passed += assertions_passed(result, file_total)
        log.append(entry)

    return {
        "source_files": source_files,
        "hidden_tests_passed": passed,
        "hidden_tests_total": total,
        "passed": bool(source_files) and set(source_files.values()) == {"OK"}
                  and total > 0 and passed == total,
        "log": "\n".join(log),
    }
