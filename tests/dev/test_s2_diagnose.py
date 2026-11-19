"""Diagnose why System 2 was called: no_match, multi_match, below_threshold."""

import unittest

from slow2fast.blocksworld import Tower, complete_goal, state_from_towers
from slow2fast.curriculum import SkillLibrary, run_skill_episode
from slow2fast.generate import format_row, parse_log, summarize_s2_reasons
from slow2fast.induce import InducedLibrary, InducedRule


def _rule(action_name, param_vars, state_pos, goal_pos, confirmations):
    rule = InducedRule(action_name, param_vars, state_pos, goal_pos, [])
    rule.confirmations = confirmations
    return rule


class DiagnosePropose(unittest.TestCase):
    def test_empty_library_is_no_match(self):
        library = SkillLibrary(known_rules=False)
        tower = Tower(["a", "b"])
        reason, detail = library.diagnose(tower.initial, tower.goal)
        self.assertEqual(reason, "no_match")
        self.assertEqual(detail, [])

    def test_only_unpracticed_match_is_below_threshold(self):
        library = SkillLibrary(known_rules=False)
        # pickup(?x0) with operator-like state cue; conf 1 < threshold 2
        library._impl.rules.append(
            _rule(
                "pickup",
                ("?x0",),
                [("clear", ("?x0",)), ("ontable", ("?x0",)), ("handempty", ())],
                [("on", ("?x0", "?x1")), ("ontable", ("?x1",)), ("handempty", ())],
                confirmations=1,
            )
        )
        state = state_from_towers([["a"], ["b"]])
        goal = complete_goal([["a", "b"]])
        reason, detail = library.diagnose(state, goal)
        self.assertEqual(reason, "below_threshold")
        self.assertGreaterEqual(len(detail), 1)

    def test_two_practiced_pickup_groundings_is_multi_match(self):
        library = SkillLibrary(known_rules=False)
        library._impl.rules.append(
            _rule(
                "pickup",
                ("?x0",),
                [("clear", ("?x0",)), ("ontable", ("?x0",)), ("handempty", ())],
                [("handempty", ())],
                confirmations=2,
            )
        )
        # Two clear table blocks; goal does not prefer one → two groundings.
        state = state_from_towers([["a"], ["b"], ["c"]])
        goal = complete_goal([["a"], ["b"], ["c"]])
        reason, detail = library.diagnose(state, goal)
        self.assertEqual(reason, "multi_match")
        self.assertGreaterEqual(len(detail), 2)

    def test_episode_records_reason_and_planner_action_on_s2(self):
        library = SkillLibrary(known_rules=False)
        tower = Tower(["a", "b"])
        result = run_skill_episode(tower, library, update=False)
        self.assertGreater(result.s2_steps, 0)
        s2 = [step for step in result.steps if step.source == "s2"]
        self.assertTrue(all(step.s2_reason == "no_match" for step in s2))
        self.assertTrue(all(step.action is not None for step in s2))

    def test_log_row_includes_s2_diag(self):
        library = SkillLibrary(known_rules=False)
        tower = Tower(["a", "b"])
        result = run_skill_episode(tower, library, update=False)
        line = format_row("random", "random-1", tower, result)
        self.assertIn("s2_diag", line)
        self.assertIn("no_match", line)
        header = "mode test tasks 1\n" + line + "\n"
        mode, tasks, rows = parse_log(header)
        self.assertEqual(mode, "test")
        self.assertEqual(tasks, 1)
        _phase, _name, _sources, _reached, diags = rows[0]
        self.assertTrue(any(d.startswith("no_match:") for d in diags))

    def test_summarize_counts_reasons(self):
        rows = [
            (
                "random",
                "a",
                ["s2", "s1", "s2"],
                True,
                ["no_match:pickup(a)", "multi_match:unstack(b,c)"],
            ),
            ("random", "b", ["s1"], True, []),
        ]
        summary = summarize_s2_reasons(rows)
        self.assertEqual(summary["no_match"], 1)
        self.assertEqual(summary["multi_match"], 1)
        self.assertEqual(summary["below_threshold"], 0)
        self.assertEqual(summary["loop_cut"], 0)


if __name__ == "__main__":
    unittest.main()
