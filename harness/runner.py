"""Run one experiment: a fresh run folder, an unattended OpenCode session within the limits, grading, records."""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from harness.grade import DEFAULT_CHECK_TIMEOUT, all_files_ok, grade, is_test_file
from harness.opencode import isolated_env, write_run_config
from harness.preflight import DEFAULT_API_KEY, DEFAULT_BASE_URL, DEFAULT_MODEL
from harness.setups import SETUPS

REPO = Path(__file__).resolve().parent.parent
TASKS = REPO / "tasks"
LISP_CHECK = REPO / "bin" / "lisp-check"
DEFAULT_RUN_ROOT = "/tmp/2048-runs"
DEFAULT_RECORDS = REPO / "runs"
DEFAULT_TIMEOUT = 7200
DEFAULT_MAX_ROUNDS = 40
PRACTICE_RUN = 0
POLL_SECONDS = 0.2
KILL_GRACE_SECONDS = 10
EXPORT_TIMEOUT = 120

PROMPT = """Implement the task below in the current folder. Work on your own until it is done; nobody will answer questions.

Create these files directly in the current folder, not in a subfolder: {files}. Check every .lisp file with lisp-check until each prints OK: {checks}.

{spec}
{note}
"""
CONTINUE_MESSAGE = "Continue until every file is created and every .lisp file prints OK in lisp-check."
SPEC_FILE_ROW =re.compile(r"^\| `([\w.-]+\.(?:asd|lisp))` \|", re.MULTILINE)


def task_files(spec):
    """The files the spec's file table asks for, in table order."""
    return SPEC_FILE_ROW.findall(spec)


def check_command(name):
    return "lisp-check " + ("--test " if is_test_file(Path(name)) else "") + name


def prompt(spec, note):
    files = task_files(spec)
    return PROMPT.format(
        files=", ".join(f"`{name}`" for name in files),
        checks=", ".join(f"`{check_command(name)}`" for name in files if name.endswith(".lisp")),
        spec=spec,
        note=note,
    )


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="run-task", description=__doc__)
    parser.add_argument("task", help="folder name under tasks/")
    parser.add_argument("setup", choices=sorted(SETUPS))
    parser.add_argument("run_number", type=int, help=f"{PRACTICE_RUN} is the uncounted practice run")
    parser.add_argument("--run-root", default=os.environ.get("RUN_ROOT", DEFAULT_RUN_ROOT),
                        help=f"where run folders are created (default $RUN_ROOT or {DEFAULT_RUN_ROOT})")
    parser.add_argument("--records-dir", default=str(DEFAULT_RECORDS),
                        help="where result records go (default: runs/ in the repo)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"wall-clock seconds before OpenCode is killed and the run fails (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--check-timeout", type=int, default=DEFAULT_CHECK_TIMEOUT,
                        help="seconds before one grading lisp-check is killed and counts as failed "
                             f"(default {DEFAULT_CHECK_TIMEOUT})")
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS,
                        help=f"check-fix rounds before OpenCode is killed and the run fails (default {DEFAULT_MAX_ROUNDS})")
    args = parser.parse_args(argv)

    if not (TASKS / args.task / "spec.md").is_file():
        parser.error(f"unknown task '{args.task}': no tasks/{args.task}/spec.md")
    if args.run_number < 0:
        parser.error("run number must be 0 or more")
    args.run_root = Path(args.run_root).resolve()
    for outside in (REPO, Path.home().resolve()):
        if args.run_root.is_relative_to(outside):
            parser.error(f"run root {args.run_root} must be outside {outside}")
    args.records_dir = Path(args.records_dir).resolve()
    return args


def utc_now():
    return datetime.now(timezone.utc)


def prepare_run_folder(run_folder):
    """Layout: work/ is the model's folder; everything else stays out of its reach."""
    work = run_folder / "work"
    work.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(work)], check=True, stdin=subprocess.DEVNULL)
    bin_dir = run_folder / "bin"
    bin_dir.mkdir()
    (bin_dir / "lisp-check").symlink_to(LISP_CHECK)
    return work


def opencode_env(run_folder, setup):
    state_dir = run_folder / "opencode"
    env = isolated_env(state_dir, config_file=write_run_config(state_dir, setup.rules_file))
    env.setdefault("LLM_BASE_URL", DEFAULT_BASE_URL)
    env.setdefault("LLM_MODEL", DEFAULT_MODEL)
    env.setdefault("LLM_API_KEY", DEFAULT_API_KEY)
    env["PATH"] = f"{run_folder / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    env["LISP_CHECK_LOG"] = str(run_folder / "lisp-check.log")
    return env


def kill_group(process, sig):
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


def wait_within_limits(process, timeout, round_log, max_rounds):
    """Wait for PROCESS; return the limit hit first ("rounds" or "wall_clock"), or None if it exited."""
    deadline = time.monotonic() + timeout
    while True:
        if count_rounds(round_log) >= max_rounds:
            return "rounds"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "wall_clock"
        try:
            process.wait(timeout=min(POLL_SECONDS, remaining))
            return "rounds" if count_rounds(round_log) >= max_rounds else None
        except subprocess.TimeoutExpired:
            pass


def run_opencode(opencode, run_args, work, env, transcript, stderr_log, timeout, round_log, max_rounds):
    """Run one `opencode run` turn; return (exit code, limit hit or None).

    The whole process group is killed once TIMEOUT seconds pass or ROUND_LOG reaches MAX_ROUNDS lines.
    """
    command = [opencode, "run", "--format", "json", "--thinking", *run_args]
    with open(transcript, "a") as out, open(stderr_log, "a") as err:
        process = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=err, start_new_session=True)
        try:
            limit_hit = wait_within_limits(process, timeout, round_log, max_rounds)
            if limit_hit:
                kill_group(process, signal.SIGTERM)
                try:
                    process.wait(timeout=KILL_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    kill_group(process, signal.SIGKILL)
                    process.wait()
            return process.returncode, limit_hit
        finally:
            kill_group(process, signal.SIGKILL)


def session_id(transcript):
    for line in transcript.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("sessionID"):
            return event["sessionID"]
    return None


def export_session(opencode, sid, work, env, target):
    with open(target, "w") as out:
        try:
            subprocess.run([opencode, "export", sid], cwd=work, env=env, stdin=subprocess.DEVNULL,
                           stdout=out, stderr=subprocess.DEVNULL, timeout=EXPORT_TIMEOUT)
        except subprocess.TimeoutExpired:
            pass


def count_rounds(log):
    return len(log.read_text().splitlines()) if log.exists() else 0


def save_records(record_dir, run_folder, work, grading, result):
    record_dir.mkdir(parents=True)
    for name in ("transcript.jsonl", "opencode.stderr.log", "session.json", "lisp-check.log"):
        if (run_folder / name).exists():
            shutil.copy2(run_folder / name, record_dir / name)
    (record_dir / "grading.log").write_text(grading["log"])
    shutil.copytree(work, record_dir / "src", ignore=shutil.ignore_patterns(".git"))
    (record_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def main(argv):
    args = parse_args(argv)
    task_dir = TASKS / args.task
    setup = SETUPS[args.setup]
    record_dir = args.records_dir / args.task / args.setup / str(args.run_number)
    if record_dir.exists():
        print(f"run-task: record {record_dir} already exists; not overwriting it", file=sys.stderr)
        return 1

    started = utc_now()
    run_folder = args.run_root / args.task / args.setup / f"{args.run_number}-{started:%Y%m%dT%H%M%SZ}"
    work = prepare_run_folder(run_folder)
    env = opencode_env(run_folder, setup)
    opencode = os.environ.get("OPENCODE_BIN", "opencode")
    transcript = run_folder / "transcript.jsonl"
    spec = (task_dir / "spec.md").read_text()
    message = prompt(spec, setup.prompt_note)
    required = task_files(spec)

    def turn(run_args):
        remaining = max(deadline - time.monotonic(), 0)
        return run_opencode(opencode, run_args, work, env, transcript,
                            run_folder / "opencode.stderr.log", remaining,
                            run_folder / "lisp-check.log", args.max_rounds)

    clock = time.monotonic()
    deadline = clock + args.timeout
    exit_code, limit_hit = turn([message])
    sid = session_id(transcript)
    continue_sent = False
    stopped_early = sid and not limit_hit and not all_files_ok(
        work, run_folder / "status-check", required, args.check_timeout)
    if stopped_early:
        continue_sent = True
        exit_code, limit_hit = turn(["-s", sid, CONTINUE_MESSAGE])
    duration = time.monotonic() - clock

    if sid:
        export_session(opencode, sid, work, env, run_folder / "session.json")
    grading = grade(work, task_dir / "hidden-tests", run_folder / "grading", required, args.check_timeout)

    result = {
        "task": args.task,
        "setup": args.setup,
        "run_number": args.run_number,
        "counted": args.run_number != PRACTICE_RUN,
        "model": env["LLM_MODEL"],
        "started_at": started.isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 1),
        "limits": {"max_rounds": args.max_rounds, "timeout_seconds": args.timeout,
                   "check_timeout_seconds": args.check_timeout},
        "limit_hit": limit_hit,
        "opencode_exit_code": exit_code,
        "continue_sent": continue_sent,
        "check_fix_rounds": count_rounds(run_folder / "lisp-check.log"),
        "hidden_tests_passed": grading["hidden_tests_passed"],
        "hidden_tests_total": grading["hidden_tests_total"],
        "source_files": grading["source_files"],
        "passed": grading["passed"] and not limit_hit,
        "session_id": sid,
        "run_folder": str(run_folder),
    }
    save_records(record_dir, run_folder, work, grading, result)
    print(f"{args.task} {args.setup} #{args.run_number}: "
          f"{'PASS' if result['passed'] else 'FAIL'}, "
          f"hidden tests {result['hidden_tests_passed']}/{result['hidden_tests_total']}, "
          f"{result['check_fix_rounds']} rounds, record {record_dir}")
    return 0
