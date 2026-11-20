"""lisp-check wrapper: runs the pinned upstream lisp-check in Docker or natively."""

import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO / "vendor" / "lisp-skills" / "plugins" / "lisp-skills"
CONTAINER_PLUGIN_DIR = "/opt/lisp-skills"


def docker_binary():
    return os.environ.get("LISP_CHECK_DOCKER", "docker")


def docker_command(args, cwd, name):
    image = os.environ.get("LISP_CHECK_IMAGE", "lisp-skills-allegro:latest")
    return [
        docker_binary(), "run", "--rm", "--name", name, "--platform", "linux/amd64",
        "-v", f"{PLUGIN_DIR}:{CONTAINER_PLUGIN_DIR}:ro",
        "-v", f"{cwd}:{cwd}",
        "-w", str(cwd),
        image,
        f"{CONTAINER_PLUGIN_DIR}/bin/lisp-check", *args,
    ]


UPSTREAM_EXIT_CODES = (0, 1, 2)
TOOL_ERROR = 2
DOCKER_KILL_TIMEOUT = 60


def tool_error(reason):
    sys.stdout.write(f"lisp-check: {reason}\nFAIL\n")
    return TOOL_ERROR


def timeout_setting():
    return os.environ.get("LISP_CHECK_TIMEOUT") or None


FORWARDED_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)


class Terminated(Exception):
    """The wrapper got one of FORWARDED_SIGNALS, for example when the runner kills OpenCode's group."""

    def __init__(self, signum):
        super().__init__(signum)
        self.signum = signum


def raise_terminated(signum, frame):
    raise Terminated(signum)


def kill_group(process):
    """Kill PROCESS's whole group; from here on the wrapper only cleans up, so it ignores further signals."""
    for sig in FORWARDED_SIGNALS:
        signal.signal(sig, signal.SIG_IGN)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.communicate()


def run_limited(command):
    """Run COMMAND without stdin; after LISP_CHECK_TIMEOUT seconds kill its whole process group."""
    timeout = timeout_setting()
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=float(timeout) if timeout else None)
    except (subprocess.TimeoutExpired, Terminated):
        kill_group(process)
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def timed_out():
    return tool_error(f"timed out after {timeout_setting()} s")


def kill_container(name):
    try:
        subprocess.run([docker_binary(), "kill", name], stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=DOCKER_KILL_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_docker(args):
    cwd = Path.cwd()
    name = f"lisp-check-{uuid.uuid4().hex[:12]}"
    command = docker_command(args, cwd, name)
    try:
        result = run_limited(command)
    except OSError as error:
        return tool_error(f"could not start docker ({command[0]}): {error}")
    except subprocess.TimeoutExpired:
        kill_container(name)
        return timed_out()
    except Terminated:
        kill_container(name)
        raise
    if result.returncode not in UPSTREAM_EXIT_CODES:
        details = " ".join(result.stderr.split()) or "no error output"
        return tool_error(f"docker failed with exit {result.returncode}: {details}")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def run_native(args):
    command = [str(PLUGIN_DIR / "bin" / "lisp-check"), *args]
    try:
        result = run_limited(command)
    except OSError as error:
        return tool_error(f"could not start {command[0]}: {error}")
    except subprocess.TimeoutExpired:
        return timed_out()
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def log_invocation(args, exit_code):
    log = os.environ.get("LISP_CHECK_LOG") or str(Path.cwd() / ".lisp-check.log")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(log, "a") as f:
        f.write("\t".join([stamp, str(exit_code), *args]) + "\n")


def run(args):
    mode = os.environ.get("LISP_CHECK_MODE", "docker")
    if mode == "docker":
        return run_docker(args)
    if mode == "native":
        return run_native(args)
    return tool_error(f"unknown LISP_CHECK_MODE '{mode}' (use docker or native)")


def main(args):
    previous = {sig: signal.signal(sig, raise_terminated) for sig in FORWARDED_SIGNALS}
    try:
        exit_code = run(args)
    except Terminated as terminated:
        return 128 + terminated.signum
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    log_invocation(args, exit_code)
    return exit_code
