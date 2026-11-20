import re
import shutil
import tempfile
import unittest
from pathlib import Path

from harness.grade import count_assertions, grade
from tests.support import docker_image_available

REPO = Path(__file__).resolve().parent.parent
TASK = REPO / "tasks" / "game-2048"
HIDDEN_TESTS = TASK / "hidden-tests"
REFERENCE = REPO / "reference" / "game-2048"

INTERFACE = {"slide-row", "move", "spawn-tile", "won-p", "game-over-p", "play"}
MODEL_FILES = {"game-2048.asd", "package.lisp", "game-2048.lisp", "game-2048-tests.lisp"}
SEAMS = {
    "hidden-slide-row-tests.lisp": {"slide-row"},
    "hidden-move-tests.lisp": {"move"},
    "hidden-spawn-tile-tests.lisp": {"spawn-tile"},
    "hidden-won-game-over-tests.lisp": {"won-p", "game-over-p"},
    "hidden-play-tests.lisp": {"play"},
}

# A classic 2048 bug: a merged tile merges again in the same move, so
# [2 2 2 2] left becomes [8 0 0 0] instead of [4 4 0 0].
DOUBLE_MERGE = (
    "game-2048.lisp",
    "(push tile merged)",
    "(if (and merged (= tile (first merged)))"
    " (incf (first merged) tile)"
    " (push tile merged))",
)
UNEXPORTED_WON_P = ("package.lisp", "           #:won-p\n", "")


def hidden_test_files():
    return sorted(HIDDEN_TESTS.glob("*.lisp"))


def interface_used(path):
    code = re.sub(r";.*", "", path.read_text())
    return code, set(re.findall(r"game-2048:([a-z0-9-]+)", code))


class TaskLayoutTest(unittest.TestCase):
    def test_one_hidden_test_file_per_seam(self):
        self.assertEqual({path.name for path in hidden_test_files()}, set(SEAMS))

    def test_hidden_tests_cannot_collide_with_model_files(self):
        names = {path.name for path in hidden_test_files()}
        self.assertFalse(names & MODEL_FILES)
        self.assertFalse(names & {path.name for path in REFERENCE.iterdir()})

    def test_each_hidden_test_file_uses_only_its_part_of_the_public_interface(self):
        for path in hidden_test_files():
            with self.subTest(file=path.name):
                code, used = interface_used(path)
                self.assertNotIn("game-2048::", code)
                self.assertEqual(used, SEAMS[path.name])

    def test_reference_has_the_layout_the_spec_asks_for(self):
        self.assertEqual({path.name for path in REFERENCE.iterdir()}, MODEL_FILES)

    def test_spec_states_the_merge_examples(self):
        spec = (TASK / "spec.md").read_text()
        for example in ("`[2 2 2 2]` becomes `[4 4 0 0]`", "`[2 2 2 0]` becomes `[4 2 0 0]`"):
            self.assertIn(example, spec)


@unittest.skipUnless(docker_image_available(), "lisp-skills-allegro image not available")
class HiddenTestsAgainstReferenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def grade_copy(self, mutation=None):
        source = self.root / "source"
        shutil.copytree(REFERENCE, source)
        if mutation:
            name, old, new = mutation
            path = source / name
            text = path.read_text()
            self.assertEqual(text.count(old), 1)
            path.write_text(text.replace(old, new))
        return grade(source, HIDDEN_TESTS, self.root / "grading")

    def test_reference_passes_every_hidden_test_and_every_file_prints_ok(self):
        result = self.grade_copy()
        self.assertEqual(
            result["source_files"],
            {"package.lisp": "OK", "game-2048.lisp": "OK", "game-2048-tests.lisp": "OK"},
            result["log"],
        )
        self.assertEqual(result["hidden_tests_total"], 66)
        self.assertEqual(result["hidden_tests_passed"], 66, result["log"])
        self.assertTrue(result["passed"])

    def test_wrong_merge_rule_fails_some_hidden_tests(self):
        result = self.grade_copy(DOUBLE_MERGE)
        self.assertEqual(result["source_files"]["game-2048.lisp"], "OK")
        self.assertGreater(result["hidden_tests_passed"], 0)
        self.assertLess(result["hidden_tests_passed"], result["hidden_tests_total"])
        self.assertFalse(result["passed"])

    def test_unexported_function_loses_only_its_own_file(self):
        result = self.grade_copy(UNEXPORTED_WON_P)
        lost = count_assertions(HIDDEN_TESTS / "hidden-won-game-over-tests.lisp")
        self.assertEqual(result["hidden_tests_passed"], result["hidden_tests_total"] - lost)


if __name__ == "__main__":
    unittest.main()
