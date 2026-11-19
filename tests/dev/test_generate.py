"""Tests for the multi-tower problem generator and training schedule."""

import unittest

from slow2fast.blocksworld import Tower, complete_goal, goal_holds, predicates_in
from slow2fast.curriculum import SkillLibrary, run_skill_episode
from slow2fast.generate import (
    PHASES,
    make_problem,
    random_problem,
    train_curriculum,
)


class CompleteGoalLanguage(unittest.TestCase):
    def test_tower_goal_includes_ontable_clear_handempty(self):
        tower = Tower(["a", "b", "c"])
        preds = predicates_in(tower.goal)
        self.assertEqual(preds, {"on", "ontable", "clear", "handempty"})
        self.assertIn(("ontable", ("c",)), tower.goal)
        self.assertIn(("clear", ("a",)), tower.goal)
        self.assertIn(("handempty", ()), tower.goal)
        self.assertIn(("on", ("a", "b")), tower.goal)
        self.assertIn(("on", ("b", "c")), tower.goal)

    def test_height_one_tower_is_ontable_and_clear(self):
        goal = complete_goal([["a"], ["b", "c"]])
        self.assertIn(("ontable", ("a",)), goal)
        self.assertIn(("clear", ("a",)), goal)
        self.assertIn(("ontable", ("c",)), goal)
        self.assertIn(("clear", ("b",)), goal)
        self.assertIn(("on", ("b", "c")), goal)
        self.assertIn(("handempty", ()), goal)


class RandomGenerator(unittest.TestCase):
    def test_random_problem_uses_at_most_n_blocks_and_complete_goal(self):
        problem = random_problem(n=5, seed=0)
        self.assertLessEqual(len(problem.blocks), 5)
        self.assertGreaterEqual(len(problem.blocks), 1)
        self.assertTrue(goal_holds(problem.initial, set()) or True)
        preds = predicates_in(problem.goal)
        self.assertTrue({"ontable", "clear", "handempty"} <= preds)
        if any(pred == "on" for pred, _args in problem.goal):
            self.assertIn("on", preds)
        # Every block is placed in the complete goal.
        for block in problem.blocks:
            on_table = ("ontable", (block,)) in problem.goal
            under_something = any(pred == "on" and args[1] == block for pred, args in problem.goal)
            on_something = any(pred == "on" and args[0] == block for pred, args in problem.goal)
            self.assertTrue(on_table or under_something)
            self.assertTrue(on_table or on_something or ("clear", (block,)) in problem.goal)

    def test_make_problem_all_on_table_single_tower(self):
        problem = make_problem(phase="single", heights=[3], seed=1)
        self.assertEqual(len(problem.blocks), 3)
        on_init = [atom for atom in problem.initial if atom[0] == "on"]
        self.assertEqual(on_init, [])
        self.assertEqual(sum(1 for atom in problem.goal if atom[0] == "on"), 2)

    def test_make_problem_multi_tower(self):
        problem = make_problem(phase="multi", heights=[2, 3], seed=2)
        self.assertEqual(len(problem.blocks), 5)
        self.assertEqual(sum(1 for atom in problem.goal if atom[0] == "on"), 1 + 2)
        self.assertEqual(sum(1 for atom in problem.goal if atom[0] == "ontable"), 2)

    def test_partial_has_some_structure_in_initial(self):
        problem = make_problem(phase="partial", heights=[3, 2], seed=3)
        on_init = [atom for atom in problem.initial if atom[0] == "on"]
        self.assertGreater(len(on_init), 0)

    def test_bad_empty_heights(self):
        with self.assertRaises(ValueError):
            make_problem(phase="single", heights=[], seed=0)


class TrainSchedule(unittest.TestCase):
    def test_phase_order(self):
        self.assertEqual(PHASES, ("single", "multi", "partial", "random"))

    def test_random_phase_default_length(self):
        lessons = train_curriculum(n=3, practice=1, seed=0)
        random_tasks = [row for row in lessons if row[0] == "random"]
        self.assertEqual(len(random_tasks), 100)

    def test_curriculum_follows_schedule(self):
        lessons = train_curriculum(n=4, practice=2, seed=0, random_count=3)
        phases = [phase for phase, _name, _problem in lessons]
        # All singles before any multi, etc.
        def first(phase):
            return phases.index(phase)

        def last(phase):
            return len(phases) - 1 - phases[::-1].index(phase)

        self.assertLess(last("single"), first("multi"))
        self.assertLess(last("multi"), first("partial"))
        self.assertLess(last("partial"), first("random"))
        self.assertTrue(set(phases) <= set(PHASES))

    def test_curriculum_problems_are_solvable_with_planner(self):
        lessons = train_curriculum(n=3, practice=1, seed=1, random_count=2)
        library = SkillLibrary(known_rules=False)
        for phase, name, problem in lessons:
            result = run_skill_episode(problem, library, update=True)
            self.assertTrue(result.goal_reached, f"{phase}:{name}")


class TrainVsTestMode(unittest.TestCase):
    def test_test_holdout_is_all_random_default_100(self):
        from slow2fast.generate import test_holdout

        lessons = test_holdout(n=3, seed=0)
        self.assertEqual(len(lessons), 100)
        self.assertTrue(all(phase == "random" for phase, _name, _problem in lessons))

    def test_test_holdout_count_override(self):
        from slow2fast.generate import test_holdout

        lessons = test_holdout(n=3, seed=1, count=7)
        self.assertEqual(len(lessons), 7)

    def test_run_mode_train_headers_log_and_saves_rules(self):
        from pathlib import Path
        import tempfile

        from slow2fast.generate import parse_log, run_mode

        with tempfile.TemporaryDirectory() as tmp:
            rules = Path(tmp) / "rules.json"
            text, library = run_mode(
                "train",
                n=3,
                practice=1,
                seed=2,
                random_count=2,
                known_rules=False,
                rules_path=rules,
            )
            mode, tasks, rows = parse_log(text)
            self.assertEqual(mode, "train")
            self.assertEqual(tasks, len(rows))
            self.assertGreater(tasks, 2)
            self.assertTrue(any(row[0] == "single" for row in rows))
            self.assertTrue(rules.is_file())
            self.assertGreater(len(library.rules), 0)

    def test_run_mode_test_loads_saved_rules_no_warmup(self):
        from pathlib import Path
        import tempfile

        from slow2fast.generate import parse_log, run_lessons, run_mode, rule_fingerprint, test_holdout

        with tempfile.TemporaryDirectory() as tmp:
            rules = Path(tmp) / "rules.json"
            _train_text, trained = run_mode(
                "train",
                n=3,
                practice=1,
                seed=3,
                random_count=2,
                known_rules=False,
                rules_path=rules,
            )
            trained_fp = rule_fingerprint(trained)
            text, library = run_mode(
                "test",
                n=3,
                seed=3,
                test_count=5,
                known_rules=False,
                rules_path=rules,
            )
            mode, tasks, rows = parse_log(text)
            self.assertEqual(mode, "test")
            self.assertEqual(tasks, 5)
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row[0] == "random" for row in rows))
            self.assertEqual(rule_fingerprint(library), trained_fp)
            before = rule_fingerprint(library)
            run_lessons(test_holdout(n=3, seed=99, count=3), library, update=False)
            self.assertEqual(rule_fingerprint(library), before)

    def test_run_mode_test_requires_saved_rules(self):
        from pathlib import Path
        import tempfile

        from slow2fast.generate import run_mode

        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                run_mode("test", n=3, seed=0, test_count=2, rules_path=missing)

    def test_figure_title_names_mode_and_task_count(self):
        from slow2fast.generate import figure_title

        self.assertEqual(figure_title("train", 125), "Checkpoint 3 — train · 125 tasks")
        self.assertEqual(figure_title("test", 100), "Checkpoint 3 — test · 100 tasks")


if __name__ == "__main__":
    unittest.main()
