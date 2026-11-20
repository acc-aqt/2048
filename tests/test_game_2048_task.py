import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_lisp_check import LISP_CHECK, docker_image_available

REPO = Path(__file__).resolve().parent.parent
TASK = REPO / "tasks" / "game-2048"
HIDDEN_TESTS = TASK / "hidden-tests"
REFERENCE = REPO / "reference" / "game-2048"

INTERFACE = {"slide-row", "move", "spawn-tile", "won-p", "game-over-p", "play"}
MODEL_FILES = {"game-2048.asd", "package.lisp", "game-2048.lisp", "game-2048-tests.lisp"}

# A classic 2048 bug: a merged tile merges again in the same move, so
# [2 2 2 2] left becomes [8 0 0 0] instead of [4 4 0 0].
BROKEN_MERGE_RULE = (
    "(push tile merged)",
    "(if (and merged (= tile (first merged)))"
    " (incf (first merged) tile)"
    " (push tile merged))",
)


def hidden_test_files():
    return sorted(HIDDEN_TESTS.glob("*.lisp"))


def assertion_count(path):
    """Number of top-level tester assertions: each starts a line with (test."""
    return len(re.findall(r"^\(test", path.read_text(), re.MULTILINE))


def make_run_folder(parent, source=REFERENCE):
    """Lay out a folder the way a graded run looks: the project, its own .git, the hidden tests."""
    run_dir = Path(parent) / "run"
    shutil.copytree(source, run_dir)
    (run_dir / ".git").mkdir()
    for path in hidden_test_files():
        shutil.copy(path, run_dir / path.name)
    return run_dir


def lisp_check(run_dir, name, test=False):
    args = [str(LISP_CHECK), *(["--test"] if test else []), name]
    return subprocess.run(args, cwd=run_dir, capture_output=True, text=True)


class TaskLayoutTest(unittest.TestCase):
    def test_hidden_tests_cannot_collide_with_model_files(self):
        names = {path.name for path in hidden_test_files()}
        self.assertTrue(names)
        self.assertFalse(names & MODEL_FILES)
        self.assertFalse(names & {path.name for path in REFERENCE.iterdir()})

    def test_hidden_tests_use_only_the_public_interface(self):
        for path in hidden_test_files():
            code = re.sub(r";.*", "", path.read_text())
            with self.subTest(file=path.name):
                self.assertNotIn("game-2048::", code)
                used = set(re.findall(r"game-2048:([a-z0-9-]+)", code))
                self.assertTrue(used)
                self.assertLessEqual(used, INTERFACE)

    def test_reference_has_the_layout_the_spec_asks_for(self):
        self.assertEqual({path.name for path in REFERENCE.iterdir()}, MODEL_FILES)

    def test_spec_states_the_merge_examples(self):
        spec = (TASK / "spec.md").read_text()
        for example in ("`[2 2 2 2]` becomes `[4 4 0 0]`", "`[2 2 2 0]` becomes `[4 2 0 0]`"):
            self.assertIn(example, spec)


@unittest.skipUnless(docker_image_available(), "lisp-skills-allegro image not available")
class ReferenceValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def assert_ok(self, result):
        self.assertEqual(result.stdout.splitlines()[-1:], ["OK"], result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_every_reference_file_prints_ok(self):
        run_dir = make_run_folder(self.parent)
        for path in sorted(REFERENCE.glob("*.lisp")):
            with self.subTest(file=path.name):
                self.assert_ok(
                    lisp_check(run_dir, path.name, test=path.name.endswith("-tests.lisp"))
                )

    def test_hidden_tests_pass_against_the_reference(self):
        run_dir = make_run_folder(self.parent)
        for path in hidden_test_files():
            with self.subTest(file=path.name):
                self.assert_ok(lisp_check(run_dir, path.name, test=True))

    def test_hidden_tests_fail_against_a_wrong_merge_rule(self):
        broken = self.parent / "broken"
        shutil.copytree(REFERENCE, broken)
        source = broken / "game-2048.lisp"
        text = source.read_text()
        old, new = BROKEN_MERGE_RULE
        self.assertIn(old, text)
        source.write_text(text.replace(old, new))
        run_dir = make_run_folder(self.parent, source=broken)
        self.assert_ok(lisp_check(run_dir, "game-2048.lisp"))
        for path in hidden_test_files():
            with self.subTest(file=path.name):
                result = lisp_check(run_dir, path.name, test=True)
                self.assertEqual(result.returncode, 1, result.stdout)
                failed = re.search(r"test: (\d+) of (\d+) assertions failed", result.stdout)
                self.assertIsNotNone(failed, result.stdout)
                self.assertEqual(int(failed.group(2)), assertion_count(path))


if __name__ == "__main__":
    unittest.main()
