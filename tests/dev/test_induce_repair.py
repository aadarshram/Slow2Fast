"""Induce keeps complete goal cues from a trace; repair relaxes them later."""

import unittest

from slow2fast.blocksworld import Tower
from slow2fast.curriculum import FINALS, LESSONS, SkillLibrary, run_skill_episode
from slow2fast.induce import groundings, induce_from_plan
from slow2fast.planner import search


def sources(result):
    return [step.source for step in result.steps]


class CompleteGoalFromOneTrace(unittest.TestCase):
    def test_first_rule_may_store_complete_goal_literals(self):
        tower = Tower(["a", "b"])
        plan = search(tower.initial, tower.goal, tower.blocks)
        rule = induce_from_plan(tower.initial, tower.goal, plan)
        self.assertIsNotNone(rule)
        goal_preds = {pred for pred, _args in rule.goal_pos}
        self.assertIn("on", goal_preds)
        for pred in ("ontable", "clear", "handempty"):
            if any(atom[0] == pred for atom in tower.goal):
                self.assertIn(pred, goal_preds, f"missing complete-goal predicate {pred}")
        self.assertEqual(groundings(rule, tower.initial, tower.goal), [plan[0]])


class RepairRelaxesFatGoals(unittest.TestCase):
    def test_taller_goal_cue_is_repaired_on_shorter_tower(self):
        from slow2fast.induce import InducedLibrary

        library = InducedLibrary(threshold=2)
        tall = Tower(["a", "b", "c"])
        plan = search(tall.initial, tall.goal, tall.blocks)
        library.observe(tall.initial, tall.goal, plan[0], plan=plan)
        self.assertEqual(len(library.rules), 1)
        fat = library.rules[0]
        self.assertGreaterEqual(len(fat.goal_pos), 1)
        before = list(fat.goal_pos)

        short = Tower(["x", "y"])
        plan2 = search(short.initial, short.goal, short.blocks)
        library.observe(short.initial, short.goal, plan2[0], plan=plan2)
        self.assertEqual(len(library.rules), 1)
        repaired = library.rules[0]
        self.assertEqual(groundings(repaired, short.initial, short.goal), [plan2[0]])
        self.assertLessEqual(len(repaired.goal_pos), len(before))

    def test_ckpt2_frozen_still_all_system_1_after_repair_induce(self):
        library = SkillLibrary(known_rules=False)
        for name, problem in LESSONS:
            result = run_skill_episode(problem, library, update=True)
            self.assertTrue(result.goal_reached, name)
        for name, problem in FINALS:
            result = run_skill_episode(problem, library, update=False)
            self.assertTrue(result.goal_reached, name)
            self.assertEqual(sources(result), ["s1"] * len(result.steps), name)


if __name__ == "__main__":
    unittest.main()
