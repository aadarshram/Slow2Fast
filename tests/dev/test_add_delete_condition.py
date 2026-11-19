"""PG3-style add condition after System 2 induce (delete exists but is not called)."""

import unittest

from slow2fast.blocksworld import Problem, complete_goal, state_from_towers
from slow2fast.curriculum import SkillLibrary, run_skill_episode
from slow2fast.induce import InducedRule, groundings


def _rule(action_name, param_vars, state_pos, goal_pos, confirmations):
    rule = InducedRule(action_name, param_vars, state_pos, goal_pos, [])
    rule.confirmations = confirmations
    return rule


class AddDeleteCondition(unittest.TestCase):
    def test_add_condition_clears_duplicate_practiced_hits(self):
        library = SkillLibrary(known_rules=False)
        library._impl.rules = [
            _rule(
                "putdown",
                ("?x0",),
                [("holding", ("?x0",))],
                [("handempty", ())],
                2,
            ),
            _rule(
                "putdown",
                ("?x0",),
                [("holding", ("?x0",))],
                [("handempty", ()), ("ontable", ("?x0",))],
                2,
            ),
        ]
        state = frozenset(
            {("holding", ("a",)), ("clear", ("b",)), ("ontable", ("b",))}
        )
        goal = complete_goal([["a"], ["b"]])
        action = ("putdown", ("a",))
        self.assertEqual(library.diagnose(state, goal)[0], "multi_match")
        library.observe(state, goal, action, plan=[action])
        self.assertNotEqual(library.diagnose(state, goal)[0], "multi_match")

    def test_delete_condition_drops_duplicate_state_literal(self):
        library = SkillLibrary(known_rules=False)
        rule = _rule(
            "putdown",
            ("?x0",),
            [("holding", ("?x0",)), ("holding", ("?x0",))],
            [("handempty", ()), ("ontable", ("?x0",))],
            2,
        )
        library._impl.rules = [rule]
        state = frozenset({("holding", ("a",)), ("ontable", ("b",)), ("clear", ("b",))})
        goal = complete_goal([["a"], ["b"]])
        action = ("putdown", ("a",))
        library._impl.traces = [(state, goal, action)]
        library._impl._delete_conditions()
        self.assertEqual(groundings(rule, state, goal), [action])
        self.assertEqual(rule.state_pos.count(("holding", ("?x0",))), 1)

    def test_train_episode_still_reaches_goal(self):
        library = SkillLibrary(known_rules=False)
        problem = Problem(
            ["a", "b", "c"],
            state_from_towers([["a"], ["b"], ["c"]]),
            complete_goal([["a", "b", "c"]]),
        )
        result = run_skill_episode(problem, library, update=True)
        self.assertTrue(result.goal_reached)


if __name__ == "__main__":
    unittest.main()
