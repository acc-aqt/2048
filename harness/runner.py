"""Run one experiment: a fresh run folder, one unattended OpenCode session, grading, records."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from harness.grade import grade
from harness.opencode import isolated_env
from harness.preflight import DEFAULT_API_KEY, DEFAULT_BASE_URL, DEFAULT_MODEL
from harness.setups import SETUPS

REPO = Path(__file__).resolve().parent.parent
TASKS = REPO / "tasks"
LISP_CHECK = REPO / "bin" / "lisp-check"
DEFAULT_RUN_ROOT = "/tmp/2048-runs"
DEFAULT_RECORDS = REPO / "runs"
DEFAULT_TIMEOUT = 7200
KILL_GRACE_SECONDS = 10
EXPORT_TIMEOUT = 120

PROMPT = """Implement the task below in the current folder. Work on your own until it is done; nobody will answer questions.

{spec}
{note}
"""


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="run-task", description=__doc__)
    parser.add_argument("task", help="folder name under tasks/")
    parser.add_argument("setup", choices=sorted(SETUPS))
    parser.add_argument("run_number", type=int)
    parser.add_argument("--run-root", default=os.environ.get("RUN_ROOT", DEFAULT_RUN_ROOT),
                        help=f"where run folders are created (default $RUN_ROOT or {DEFAULT_RUN_ROOT})")
    parser.add_argument("--records-dir", default=str(DEFAULT_RECORDS),
                        help="where result records go (default: runs/ in the repo)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help=f"wall-clock seconds before OpenCode is killed (default {DEFAULT_TIMEOUT})")
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


def opencode_env(run_folder):
    env = isolated_env(run_folder / "opencode")
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


def run_opencode(opencode, message, work, env, transcript, stderr_log, timeout):
    """Run one `opencode run` turn; return (exit code, timed out). Never waits past TIMEOUT."""
    command = [opencode, "run", "--format", "json", "--thinking", message]
    with open(transcript, "a") as out, open(stderr_log, "a") as err:
        process = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=err, start_new_session=True)
        try:
            return process.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            kill_group(process, signal.SIGTERM)
            try:
                process.wait(timeout=KILL_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                kill_group(process, signal.SIGKILL)
                process.wait()
            return process.returncode, True
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
    env = opencode_env(run_folder)
    opencode = os.environ.get("OPENCODE_BIN", "opencode")
    transcript = run_folder / "transcript.jsonl"
    message = PROMPT.format(spec=(task_dir / "spec.md").read_text(), note=setup.prompt_note)

    clock = time.monotonic()
    exit_code, timed_out = run_opencode(opencode, message, work, env, transcript,
                                        run_folder / "opencode.stderr.log", args.timeout)
    duration = time.monotonic() - clock

    sid = session_id(transcript)
    if sid:
        export_session(opencode, sid, work, env, run_folder / "session.json")
    grading = grade(work, task_dir / "hidden-tests", run_folder / "grading")

    result = {
        "task": args.task,
        "setup": args.setup,
        "run_number": args.run_number,
        "model": env["LLM_MODEL"],
        "started_at": started.isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 1),
        "timed_out": timed_out,
        "opencode_exit_code": exit_code,
        "check_fix_rounds": count_rounds(run_folder / "lisp-check.log"),
        "hidden_tests_passed": grading["hidden_tests_passed"],
        "hidden_tests_total": grading["hidden_tests_total"],
        "source_files": grading["source_files"],
        "passed": grading["passed"] and not timed_out,
        "session_id": sid,
        "run_folder": str(run_folder),
    }
    save_records(record_dir, run_folder, work, grading, result)
    print(f"{args.task} {args.setup} #{args.run_number}: "
          f"{'PASS' if result['passed'] else 'FAIL'}, "
          f"hidden tests {result['hidden_tests_passed']}/{result['hidden_tests_total']}, "
          f"{result['check_fix_rounds']} rounds, record {record_dir}")
    return 0
