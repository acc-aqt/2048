import os
import subprocess


def docker_image_available():
    image = os.environ.get("LISP_CHECK_IMAGE", "lisp-skills-allegro:latest")
    try:
        result = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
    except OSError:
        return False
    return result.returncode == 0
