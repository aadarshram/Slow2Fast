import unittest

from slow2fast.blocksworld import Tower, goal_holds, initial_state
from slow2fast.episode import run_episode
from slow2fast.library import Library
from slow2fast.planner import search


def sources(result):
    return [step.source for step in result.steps]


class TypicalTower(unittest.TestCase):
    def test_three_block_training_then_four_block_test(self):
        library = Library()
        train = run_episode(Tower(["a", "b", "c"]), library, update=True)
        self.assertTrue(train.goal_reached)
        self.assertEqual(sources(train), ["s2", "s2", "s2", "s2"])
        self.assertEqual(train.s1_ok, 0)
        self.assertEqual(library.confirmation_count("stack"), 2)

        test = run_episode(Tower(["w", "x", "y", "z"]), library, update=False)
        self.assertTrue(test.goal_reached)
        self.assertEqual(sources(test), ["s2", "s1", "s2", "s1", "s2", "s2", "s2", "s1", "s2", "s1"])
        self.assertEqual(test.s1_ok, 4)
        self.assertEqual(test.s1_bad, 0)
        self.assertEqual(library.confirmation_count("stack"), 2)


class EdgePractice(unittest.TestCase):
    def test_two_block_tower_needs_a_second_example(self):
        library = Library()
        first = run_episode(Tower(["a", "b"]), library, update=True)
        self.assertTrue(first.goal_reached)
        self.assertEqual(sources(first), ["s2", "s2"])
        self.assertEqual(library.confirmation_count("stack"), 1)

        second = run_episode(Tower(["c", "d"]), library, update=True)
        self.assertEqual(sources(second), ["s2", "s2"])
        self.assertEqual(library.confirmation_count("stack"), 2)

        third = run_episode(Tower(["e", "f"]), library, update=False)
        self.assertEqual(sources(third), ["s2", "s1"])
        self.assertTrue(third.goal_reached)
        self.assertEqual(library.confirmation_count("stack"), 2)


class BadInput(unittest.TestCase):
    def test_cyclic_goal_stops_without_a_plan(self):
        tower = Tower(["a", "b"])
        tower.goal = frozenset({("on", ("a", "b")), ("on", ("b", "a"))})
        self.assertIsNone(search(tower.initial, tower.goal, tower.blocks))
        result = run_episode(tower, Library(), update=True)
        self.assertFalse(result.goal_reached)
        self.assertEqual(result.steps, [])
        self.assertEqual(library_count(result), 0)

    def test_goal_already_true_is_an_empty_episode(self):
        tower = Tower(["a", "b"])
        tower.initial = goal_state_with_tower(["a", "b"])
        self.assertTrue(goal_holds(tower.initial, tower.goal))
        result = run_episode(tower, Library(), update=True)
        self.assertTrue(result.goal_reached)
        self.assertEqual(result.steps, [])

    def test_two_groundings_propose_nothing(self):
        library = Library()
        library.add_practiced_stack()
        state = initial_state(["a", "b", "c"])
        state = apply_holding(state, "a")
        goal = frozenset({("on", ("a", "b")), ("on", ("a", "c"))})
        self.assertIsNone(library.propose(state, goal))


class Revision(unittest.TestCase):
    def test_one_separating_literal_is_added(self):
        library = Library()
        library.add_practiced_stack()
        rule = library.only_rule()
        rule.record_success(state_holding("a", ontable=["b", "c"]), {"?x": "a", "?y": "b"})
        rule.record_success(state_holding("c", ontable=["a", "b"]), {"?x": "c", "?y": "b"})
        failed = state_holding("a", ontable=["c"], on=[("b", "d")])
        library.revise(rule, failed, {"?x": "a", "?y": "b"})
        self.assertFalse(rule.retired)
        self.assertIn(("ontable", ("?y",)), rule.state_cue)

    def test_no_separating_literal_retires_the_rule(self):
        library = Library()
        library.add_practiced_stack()
        rule = library.only_rule()
        held = state_holding("a", ontable=["b"])
        rule.record_success(held, {"?x": "a", "?y": "b"})
        library.revise(rule, held, {"?x": "a", "?y": "b"})
        self.assertTrue(rule.retired)
        self.assertIsNone(library.propose(held, frozenset({("on", ("a", "b"))})))


class PrematureStack(unittest.TestCase):
    def test_holding_the_top_block_still_reaches_the_goal(self):
        library = Library()
        library.add_practiced_stack()
        tower = Tower(["a", "b", "c"])
        tower.initial = state_holding("a", ontable=["b", "c"])
        result = run_episode(tower, library, update=False)
        self.assertTrue(result.goal_reached)
        self.assertLessEqual(len(result.steps), 8 * 3)
        self.assertGreaterEqual(result.s2_steps, 1)


def library_count(result):
    return result.s1_ok + result.s1_bad + result.s2_steps


def goal_state_with_tower(names):
    state = initial_state(names)
    for top, support in zip(names, names[1:]):
        state = state - {("ontable", (top,)), ("clear", (support,))}
        state = state | {("on", (top, support))}
    return state


def apply_holding(state, block):
    return (state - {("ontable", (block,)), ("clear", (block,)), ("handempty", ())}) | {
        ("holding", (block,))
    }


def state_holding(block, ontable, on=()):
    blocks = [block, *ontable, *[b for pair in on for b in pair]]
    state = initial_state(sorted(set(blocks)))
    state = apply_holding(state, block)
    for top, support in on:
        if ("ontable", (top,)) in state:
            state = state - {("ontable", (top,))}
        state = state - {("clear", (support,))}
        state = state | {("on", (top, support))}
    return state


if __name__ == "__main__":
    unittest.main()
