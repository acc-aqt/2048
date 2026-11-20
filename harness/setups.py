"""The experiment setups. A setup decides what the model gets besides the task spec.

The two setups differ only in the rules text: "with-skills" gets the pinned lisp-skills
rules as always-loaded OpenCode instructions, "without-skills" gets one sentence instead.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

LISP_RULES = Path(__file__).resolve().parent.parent / "vendor" / "lisp-skills" / "dist" / "lisp-rules.md"


@dataclass(frozen=True)
class Setup:
    name: str
    prompt_note: str
    rules_file: Optional[Path] = None


SETUPS = {
    setup.name: setup
    for setup in (
        Setup("with-skills", prompt_note="", rules_file=LISP_RULES),
        Setup("without-skills", prompt_note="Run lisp-check FILE until it prints OK."),
    )
}
