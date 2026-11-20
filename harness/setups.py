"""The experiment setups. A setup decides what the model gets besides the task spec."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Setup:
    name: str
    prompt_note: str


# Placeholders: ticket #5 gives "with-skills" the pinned dist/lisp-rules.md as OpenCode instructions.
SETUPS = {
    setup.name: setup
    for setup in (
        Setup("with-skills", prompt_note=""),
        Setup("without-skills", prompt_note="Run lisp-check FILE until it prints OK."),
    )
}
