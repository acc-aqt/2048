"""lisp-check wrapper: runs the pinned upstream lisp-check in Docker or natively."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO / "vendor" / "lisp-skills" / "plugins" / "lisp-skills"
CONTAINER_PLUGIN_DIR = "/opt/lisp-skills"


def docker_command(args, cwd):
    docker = os.environ.get("LISP_CHECK_DOCKER", "docker")
    image = os.environ.get("LISP_CHECK_IMAGE", "lisp-skills-allegro:latest")
    return [
        docker, "run", "--rm", "--platform", "linux/amd64",
        "-v", f"{PLUGIN_DIR}:{CONTAINER_PLUGIN_DIR}:ro",
        "-v", f"{cwd}:{cwd}",
        "-w", str(cwd),
        image,
        f"{CONTAINER_PLUGIN_DIR}/bin/lisp-check", *args,
    ]


UPSTREAM_EXIT_CODES = (0, 1, 2)
TOOL_ERROR = 2


def tool_error(reason):
    sys.stdout.write(f"lisp-check: {reason}\nFAIL\n")
    return TOOL_ERROR


def run_docker(args):
    cwd = Path.cwd()
    command = docker_command(args, cwd)
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, capture_output=True, text=True
        )
    except OSError as error:
        return tool_error(f"could not start docker ({command[0]}): {error}")
    if result.returncode not in UPSTREAM_EXIT_CODES:
        details = " ".join(result.stderr.split()) or "no error output"
        return tool_error(f"docker failed with exit {result.returncode}: {details}")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def run_native(args):
    command = [str(PLUGIN_DIR / "bin" / "lisp-check"), *args]
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, capture_output=True, text=True
        )
    except OSError as error:
        return tool_error(f"could not start {command[0]}: {error}")
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
    exit_code = run(args)
    log_invocation(args, exit_code)
    return exit_code
