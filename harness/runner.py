"""Run one experiment: a fresh run folder, an unattended agent session within the limits, grading, records."""

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

from harness import claude, codex
from harness.grade import DEFAULT_CHECK_TIMEOUT, all_files_ok, copy_model_files, grade, is_test_file
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
LEAK_MARKERS = (str(REPO), "hidden-tests", "reference/")
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
                        help=f"wall-clock seconds before the agent is killed and the run fails (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--check-timeout", type=int, default=DEFAULT_CHECK_TIMEOUT,
                        help="seconds before one grading lisp-check is killed and counts as failed "
                             f"(default {DEFAULT_CHECK_TIMEOUT})")
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS,
                        help=f"check-fix rounds before the agent is killed and the run fails (default {DEFAULT_MAX_ROUNDS})")
    parser.add_argument("--backend", choices=sorted(BACKENDS), default="opencode",
                        help="the agent that does the run (default opencode)")
    parser.add_argument("--model", help="codex and claude: the model (default $CODEX_MODEL or "
                                         f"{codex.DEFAULT_MODEL}; $CLAUDE_MODEL or {claude.DEFAULT_MODEL})")
    parser.add_argument("--reasoning-effort",
                        help="codex and claude: the reasoning effort (default $CODEX_REASONING_EFFORT or "
                             f"{codex.DEFAULT_EFFORT}; $CLAUDE_REASONING_EFFORT or {claude.DEFAULT_EFFORT})")
    parser.add_argument("--max-budget-usd", type=float,
                        help=f"claude only: the most a run may cost; reaching it fails the run (default {claude.DEFAULT_BUDGET_USD:g})")
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
    if args.backend == "opencode" and (args.model or args.reasoning_effort):
        parser.error("--model and --reasoning-effort are for --backend codex or claude; OpenCode reads LLM_MODEL")
    if args.backend != "claude" and args.max_budget_usd is not None:
        parser.error("--max-budget-usd is for --backend claude")
    return args


def utc_now():
    return datetime.now(timezone.utc)


def prepare_run_folder(run_folder):
    """Layout: work/ is the model's folder; everything else stays out of its reach."""
    work = run_folder / "work"
    work.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(work)], check=True, stdin=subprocess.DEVNULL)
    round_log(run_folder).parent.mkdir()
    bin_dir = run_folder / "bin"
    bin_dir.mkdir()
    (bin_dir / "lisp-check").symlink_to(LISP_CHECK)
    return work


def transcript_path(run_folder):
    return run_folder / "transcript.jsonl"


def round_log(run_folder):
    """The log with one line per lisp-check the model runs; its folder holds nothing else."""
    return run_folder / "rounds" / "lisp-check.log"


def with_lisp_check(env, run_folder):
    """ENV plus the run's lisp-check wrapper first on PATH and the round log it writes to."""
    env["PATH"] = f"{run_folder / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    env["LISP_CHECK_LOG"] = str(round_log(run_folder))
    return env


def opencode_env(run_folder, setup):
    state_dir = run_folder / "opencode"
    env = isolated_env(state_dir, config_file=write_run_config(state_dir, setup.rules_file))
    env.setdefault("LLM_BASE_URL", DEFAULT_BASE_URL)
    env.setdefault("LLM_MODEL", DEFAULT_MODEL)
    env.setdefault("LLM_API_KEY", DEFAULT_API_KEY)
    return with_lisp_check(env, run_folder)


class OpenCodeBackend:
    """`opencode run` turns; the continue message goes to the same session with `-s`."""

    name = "opencode"
    stderr_log = "opencode.stderr.log"

    @staticmethod
    def find_binary():
        return os.environ.get("OPENCODE_BIN", "opencode")

    def __init__(self, binary, args, run_folder, work, setup):
        self.binary = binary
        self.work = work
        self.run_folder = run_folder
        self.env = opencode_env(run_folder, setup)

    def first_turn(self, message):
        return [self.binary, "run", "--format", "json", "--thinking", message]

    def continue_turn(self, sid, message):
        return [self.binary, "run", "--format", "json", "--thinking", "-s", sid, message]

    def session_id(self, transcript):
        return first_event_value(transcript, "sessionID")

    def turn_limit(self, transcript):
        return None

    def finish(self, sid):
        if sid:
            export_session(self.binary, sid, self.work, self.env, self.run_folder / "session.json")

    def result_fields(self, transcript, exit_code):
        return {"backend": self.name, "model": self.env["LLM_MODEL"], "opencode_exit_code": exit_code,
                "usage": None, "total_tokens": None, "cost_usd": None}


class CodexBackend:
    """`codex exec` turns; the continue message resumes the same thread with `codex exec resume`."""

    name = "codex"
    stderr_log = "codex.stderr.log"

    @staticmethod
    def find_binary():
        return codex.find_codex()

    def __init__(self, binary, args, run_folder, work, setup):
        self.binary = binary
        self.model, self.effort = codex.model_settings(args.model, args.reasoning_effort)
        self.env = with_lisp_check(codex.isolated_env(run_folder / "codex-home", os.environ), run_folder)
        self.options = codex.exec_options(self.model, self.effort, round_log(run_folder).parent)
        if setup.rules_file is not None:
            shutil.copy2(setup.rules_file, work / "AGENTS.md")

    def first_turn(self, message):
        return [self.binary, "exec", *self.options, message]

    def continue_turn(self, sid, message):
        return [self.binary, "exec", "resume", *self.options, sid, message]

    def session_id(self, transcript):
        return first_event_value(transcript, "thread_id")

    def turn_limit(self, transcript):
        return None

    def finish(self, sid):
        pass

    def result_fields(self, transcript, exit_code):
        usage, total_tokens = codex.usage(json_events(transcript))
        return {"backend": self.name, "model": self.model, "reasoning_effort": self.effort,
                "codex_exit_code": exit_code, "usage": usage, "total_tokens": total_tokens, "cost_usd": None}


class ClaudeBackend:
    """`claude -p` turns; the continue message resumes the same session with `--resume`."""

    name = "claude"
    stderr_log = "claude.stderr.log"
    LISP_CHECK_PARTS = ("bin", "harness")

    @staticmethod
    def find_binary():
        return claude.find_claude()

    def __init__(self, binary, args, run_folder, work, setup):
        self.binary = binary
        self.model, self.effort = claude.model_settings(args.model, args.reasoning_effort)
        self.env = with_lisp_check(claude.isolated_env(os.environ, self.effort), run_folder)
        rounds = round_log(run_folder).parent
        readable = [REPO, run_folder / "bin", rounds, Path.home() / ".docker"]
        unreadable = [*(path for path in sorted(REPO.iterdir()) if path.name not in self.LISP_CHECK_PARTS),
                      DEFAULT_RECORDS, args.records_dir, args.run_root, Path.home()]
        settings = claude.run_settings(work, rounds, readable, unique(unreadable), codex.docker_socket())
        settings_file = claude.write_settings(run_folder / "claude" / "settings.json", settings)
        self.options = claude.base_options(self.model, self.effort, settings_file)
        self.budget = claude.DEFAULT_BUDGET_USD if args.max_budget_usd is None else args.max_budget_usd
        self.transcript = transcript_path(run_folder)
        if setup.rules_file is not None:
            shutil.copy2(setup.rules_file, work / "CLAUDE.md")

    def first_turn(self, message):
        return [self.binary, *self.options, "--max-budget-usd", f"{self.budget:g}", message]

    def continue_turn(self, sid, message):
        """The budget caps one `claude` process, so the resumed turn gets what the session left of it."""
        _, cost = claude.usage(json_events(self.transcript))
        left = max(self.budget - (cost or 0), 0)
        return [self.binary, *self.options, "--max-budget-usd", f"{round(left, 4):g}", "--resume", sid, message]

    def session_id(self, transcript):
        return first_event_value(transcript, "session_id")

    def turn_limit(self, transcript):
        return "budget" if claude.budget_exhausted(json_events(transcript)) else None

    def finish(self, sid):
        pass

    def result_fields(self, transcript, exit_code):
        usage, cost = claude.usage(json_events(transcript))
        return {"backend": self.name, "model": self.model, "reasoning_effort": self.effort,
                "budget_usd": self.budget, "claude_exit_code": exit_code, "usage": usage,
                "total_tokens": sum(usage.values()) if usage else None, "cost_usd": cost}


def unique(paths):
    return list(dict.fromkeys(paths))


# Every backend has find_binary(), which may raise one of AGENT_NOT_FOUND, and, once built with
# (binary, args, run_folder, work, setup): env, stderr_log, first_turn(message),
# continue_turn(sid, message), session_id(transcript), turn_limit(transcript) (a limit the agent itself
# stopped at, or None), finish(sid) and result_fields(transcript, exit_code).
BACKENDS = {backend.name: backend for backend in (OpenCodeBackend, CodexBackend, ClaudeBackend)}
AGENT_NOT_FOUND = (codex.CodexNotFound,)


def kill_group(process, sig):
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


def group_alive(process):
    try:
        os.killpg(process.pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def stop_group(process):
    """SIGTERM PROCESS's group and give every member, not just PROCESS, KILL_GRACE_SECONDS to exit.

    A lisp-check wrapper in the group uses that time to kill its own check and container.
    """
    kill_group(process, signal.SIGTERM)
    deadline = time.monotonic() + KILL_GRACE_SECONDS
    try:
        process.wait(timeout=KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    while group_alive(process) and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
    kill_group(process, signal.SIGKILL)
    process.wait()


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


def run_turn(command, work, env, transcript, stderr_log, timeout, round_log, max_rounds):
    """Run one agent turn; return (exit code, limit hit or None).

    The whole process group is killed once TIMEOUT seconds pass or ROUND_LOG reaches MAX_ROUNDS lines.
    """
    with open(transcript, "a") as out, open(stderr_log, "a") as err:
        process = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=err, start_new_session=True)
        try:
            limit_hit = wait_within_limits(process, timeout, round_log, max_rounds)
            if limit_hit:
                stop_group(process)
            return process.returncode, limit_hit
        finally:
            kill_group(process, signal.SIGKILL)


def json_events(transcript):
    """The JSON objects in TRANSCRIPT, one per line; other lines are skipped."""
    if not transcript.exists():
        return []
    events = []
    for line in transcript.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def first_event_value(transcript, key):
    """The first non-empty KEY of a JSON event in TRANSCRIPT, or None."""
    return next((event[key] for event in json_events(transcript) if event.get(key)), None)


def export_session(opencode, sid, work, env, target):
    with open(target, "w") as out:
        try:
            subprocess.run([opencode, "export", sid], cwd=work, env=env, stdin=subprocess.DEVNULL,
                           stdout=out, stderr=subprocess.DEVNULL, timeout=EXPORT_TIMEOUT)
        except subprocess.TimeoutExpired:
            pass


def suspected_leak(transcript):
    """Whether TRANSCRIPT names the repo, the hidden tests or the reference solution; flagged for review, not failed."""
    text = transcript.read_text(errors="replace") if transcript.exists() else ""
    return any(marker in text for marker in LEAK_MARKERS)


def count_rounds(log):
    return len(log.read_text().splitlines()) if log.exists() else 0


def has_record(record_dir):
    """A record counts only once its result.json exists; a folder without one is a leftover."""
    return (record_dir / "result.json").is_file()


def save_records(record_dir, run_folder, work, grading, result):
    """Build the record in a hidden sibling folder, then rename it to RECORD_DIR, so a record is complete or absent.

    A leftover RECORD_DIR without result.json is renamed to <run>.incomplete-<UTC time> first.
    """
    record_dir.parent.mkdir(parents=True, exist_ok=True)
    partial = record_dir.parent / f".{record_dir.name}.partial-{os.getpid()}"
    partial.mkdir()
    for name in ("transcript.jsonl", "opencode.stderr.log", "codex.stderr.log", "claude.stderr.log", "session.json"):
        if (run_folder / name).exists():
            shutil.copy2(run_folder / name, partial / name)
    if round_log(run_folder).exists():
        shutil.copy2(round_log(run_folder), partial / "lisp-check.log")
    (partial / "grading.log").write_text(grading["log"])
    copy_model_files(work, partial / "src")
    (partial / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    if record_dir.exists():
        record_dir.rename(record_dir.parent / f"{record_dir.name}.incomplete-{utc_now():%Y%m%dT%H%M%SZ}")
    partial.rename(record_dir)


def main(argv):
    args = parse_args(argv)
    task_dir = TASKS / args.task
    setup = SETUPS[args.setup]
    record_dir = args.records_dir / args.task / args.setup / str(args.run_number)
    if has_record(record_dir):
        print(f"run-task: record {record_dir} already exists; not overwriting it", file=sys.stderr)
        return 1

    try:
        binary = BACKENDS[args.backend].find_binary()
    except AGENT_NOT_FOUND as error:
        print(f"run-task: {error}", file=sys.stderr)
        return 1

    started = utc_now()
    run_folder = args.run_root / args.task / args.setup / f"{args.run_number}-{started:%Y%m%dT%H%M%SZ}"
    work = prepare_run_folder(run_folder)
    backend = BACKENDS[args.backend](binary, args, run_folder, work, setup)
    transcript = transcript_path(run_folder)
    spec = (task_dir / "spec.md").read_text()
    message = prompt(spec, setup.prompt_note)
    required = task_files(spec)

    model_seconds = 0.0

    def turn(command):
        """One agent turn; the wall-clock limit covers only the time spent in turns."""
        nonlocal model_seconds
        start = time.monotonic()
        exit_code, limit_hit = run_turn(command, work, backend.env, transcript,
                                        run_folder / backend.stderr_log, max(args.timeout - model_seconds, 0),
                                        round_log(run_folder), args.max_rounds)
        model_seconds += time.monotonic() - start
        return exit_code, limit_hit or backend.turn_limit(transcript)

    exit_code, limit_hit = turn(backend.first_turn(message))
    sid = backend.session_id(transcript)
    continue_sent = False
    stopped_early = sid and not limit_hit and not all_files_ok(
        work, run_folder / "status-check", required, args.check_timeout)
    if stopped_early:
        continue_sent = True
        exit_code, limit_hit = turn(backend.continue_turn(sid, CONTINUE_MESSAGE))

    backend.finish(sid)
    grading = grade(work, task_dir / "hidden-tests", run_folder / "grading", required, args.check_timeout)

    result = {
        "task": args.task,
        "setup": args.setup,
        "run_number": args.run_number,
        "counted": args.run_number != PRACTICE_RUN,
        **backend.result_fields(transcript, exit_code),
        "started_at": started.isoformat(timespec="seconds"),
        "duration_seconds": round(model_seconds, 1),
        "limits": {"max_rounds": args.max_rounds, "timeout_seconds": args.timeout,
                   "check_timeout_seconds": args.check_timeout},
        "limit_hit": limit_hit,
        "continue_sent": continue_sent,
        "check_fix_rounds": count_rounds(round_log(run_folder)),
        "hidden_tests_passed": grading["hidden_tests_passed"],
        "hidden_tests_total": grading["hidden_tests_total"],
        "source_files": grading["source_files"],
        "skipped_files": grading["skipped_files"],
        "passed": grading["passed"] and not limit_hit,
        "suspected_leak": suspected_leak(transcript),
        "session_id": sid,
        "run_folder": str(run_folder),
    }
    save_records(record_dir, run_folder, work, grading, result)
    print(f"{args.task} {args.setup} #{args.run_number}: "
          f"{'PASS' if result['passed'] else 'FAIL'}, "
          f"hidden tests {result['hidden_tests_passed']}/{result['hidden_tests_total']}, "
          f"{result['check_fix_rounds']} rounds, record {record_dir}")
    return 0
