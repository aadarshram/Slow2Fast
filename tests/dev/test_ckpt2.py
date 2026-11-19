import unittest

from cmc.blocksworld import Tower, apply, goal_holds, initial_state
from cmc.curriculum import FINALS, LESSONS, SkillLibrary, run_skill_episode, sunk_support
from cmc.episode import run_episode
from cmc.library import Library
from cmc.planner import search


def sources(result):
    return [step.source for step in result.steps]


EXPECTED_SOURCES = {
    "h2-1": ["s2", "s2"],
    "h2-2": ["s2", "s2"],
    "h2-3": ["s1", "s1"],
    "h3-1": ["s1", "s1", "s2", "s1"],
    "h3-2": ["s1", "s1", "s2", "s1"],
    "h3-3": ["s1", "s1", "s1", "s1"],
    "h4": ["s1", "s1", "s1", "s1", "s1", "s1"],
    "inv-1": ["s2", "s2", "s1", "s1"],
    "inv-2": ["s2", "s2", "s1", "s1"],
    "inv-3": ["s1", "s1", "s1", "s1"],
}

# The step that raises a count from 1 to 2 is still System 2, so these are the counts after that step.
EXPECTED_COUNTS = {
    "h2-1": {"pickup-base": 1, "pickup-next": 0, "stack": 1, "unstack": 0, "putdown": 0},
    "h2-2": {"pickup-base": 2, "pickup-next": 0, "stack": 2, "unstack": 0, "putdown": 0},
    "h2-3": {"pickup-base": 3, "pickup-next": 0, "stack": 3, "unstack": 0, "putdown": 0},
    "h3-1": {"pickup-base": 4, "pickup-next": 1, "stack": 5, "unstack": 0, "putdown": 0},
    "h3-2": {"pickup-base": 5, "pickup-next": 2, "stack": 7, "unstack": 0, "putdown": 0},
    "h3-3": {"pickup-base": 6, "pickup-next": 3, "stack": 9, "unstack": 0, "putdown": 0},
    "h4": {"pickup-base": 7, "pickup-next": 5, "stack": 12, "unstack": 0, "putdown": 0},
    "inv-1": {"pickup-base": 8, "pickup-next": 5, "stack": 13, "unstack": 1, "putdown": 1},
    "inv-2": {"pickup-base": 9, "pickup-next": 5, "stack": 14, "unstack": 2, "putdown": 2},
    "inv-3": {"pickup-base": 10, "pickup-next": 5, "stack": 15, "unstack": 3, "putdown": 3},
}


class GrowthSequence(unittest.TestCase):
    def test_lessons_then_frozen_block(self):
        library = SkillLibrary(known_rules=True)
        self.assertEqual([name for name, _problem in LESSONS], list(EXPECTED_SOURCES))
        for name, problem in LESSONS:
            result = run_skill_episode(problem, library, update=True)
            self.assertTrue(result.goal_reached, name)
            self.assertEqual(sources(result), EXPECTED_SOURCES[name], name)
            self.assertEqual(result.s1_bad, 0, name)
            self.assertEqual(result.s1_ok, sources(result).count("s1"), name)
            self.assertEqual(result.s2_steps, sources(result).count("s2"), name)
            self.assertEqual(library.counts(), EXPECTED_COUNTS[name], name)

        frozen = library.counts()
        for name, problem in FINALS:
            result = run_skill_episode(problem, library, update=False)
            self.assertTrue(result.goal_reached, name)
            self.assertGreater(len(result.steps), 0, name)
            self.assertEqual(sources(result), ["s1"] * len(result.steps), name)
            self.assertEqual(result.s1_bad, 0, name)
            self.assertEqual(result.s2_steps, 0, name)
        self.assertEqual(library.counts(), frozen)
        self.assertEqual([name for name, _problem in FINALS], ["final-h2", "final-h3", "final-h4", "final-inv"])


class AmbiguousCue(unittest.TestCase):
    def test_two_pickup_groundings_propose_nothing(self):
        library = SkillLibrary(known_rules=True)
        for name, problem in LESSONS[:2]:
            run_skill_episode(problem, library, update=True)
        state = initial_state(["a", "b", "c"])
        goal = frozenset({("on", ("a", "c")), ("on", ("b", "c"))})
        self.assertIsNone(library.propose(state, goal))

    def test_two_stack_groundings_propose_nothing(self):
        library = SkillLibrary(known_rules=True)
        for _name, problem in LESSONS:
            run_skill_episode(problem, library, update=True)
        state = set(initial_state(["a", "b", "c"]))
        state.remove(("ontable", ("a",)))
        state.remove(("clear", ("a",)))
        state.discard(("handempty", ()))
        state.add(("holding", ("a",)))
        goal = frozenset({("on", ("a", "b")), ("on", ("a", "c"))})
        self.assertIsNone(library.propose(frozenset(state), goal))

    def test_two_misplaced_blocks_do_not_unstack(self):
        library = SkillLibrary(known_rules=True)
        for _name, problem in LESSONS:
            run_skill_episode(problem, library, update=True)
        state = set(initial_state(["p", "q", "r", "s"]))
        for top, support in (("p", "q"), ("r", "s")):
            state.remove(("ontable", (top,)))
            state.remove(("clear", (support,)))
            state.add(("on", (top, support)))
        goal = frozenset({("on", ("q", "p")), ("on", ("s", "r"))})
        self.assertIsNone(library.propose(frozenset(state), goal))


class OutsideTheFamily(unittest.TestCase):
    def test_sunk_support_still_needs_the_planner(self):
        library = SkillLibrary(known_rules=True)
        for _name, problem in LESSONS:
            run_skill_episode(problem, library, update=True)
        result = run_skill_episode(sunk_support(), library, update=False)
        self.assertTrue(result.goal_reached)
        self.assertIn("s2", sources(result))
        self.assertEqual(result.s1_bad, 0)
        self.assertTrue(goal_holds(result_state(result), sunk_support().goal))


class LoopCut(unittest.TestCase):
    def test_repeated_state_is_cut_before_the_action(self):
        tower = Tower(["a", "b", "c"])
        plan = search(tower.initial, tower.goal, tower.blocks)
        self.assertEqual(
            plan,
            [
                ("pickup", ("b",)),
                ("stack", ("b", "c")),
                ("pickup", ("a",)),
                ("stack", ("a", "b")),
            ],
        )
        state = tower.initial
        seen = {state}
        for action in plan:
            state = apply(state, action)
            self.assertNotIn(state, seen)
            seen.add(state)
        self.assertTrue(goal_holds(state, tower.goal))


class Checkpoint1Unchanged(unittest.TestCase):
    def test_stack_only_library_still_reports_the_old_split(self):
        library = Library()
        train = run_episode(Tower(["a", "b", "c"]), library, update=True)
        self.assertEqual(sources(train), ["s2", "s2", "s2", "s2"])
        test = run_episode(Tower(["w", "x", "y", "z"]), library, update=False)
        self.assertEqual(sources(test), ["s2", "s1", "s2", "s1", "s2", "s2", "s2", "s1", "s2", "s1"])



class InduceFromTraces(unittest.TestCase):
    def test_empty_library_proposes_nothing(self):
        library = SkillLibrary(known_rules=False)
        tower = Tower(["a", "b"])
        self.assertIsNone(library.propose(tower.initial, tower.goal))
        self.assertEqual(library.rules, [])

    def test_lessons_then_frozen_all_system_1(self):
        library = SkillLibrary(known_rules=False)
        for name, problem in LESSONS:
            result = run_skill_episode(problem, library, update=True)
            self.assertTrue(result.goal_reached, name)
            self.assertEqual(result.s1_bad, 0, name)
        self.assertGreater(len(library.rules), 0)
        frozen = [rule.confirmations for rule in library.rules]
        for name, problem in FINALS:
            result = run_skill_episode(problem, library, update=False)
            self.assertTrue(result.goal_reached, name)
            self.assertEqual(sources(result), ["s1"] * len(result.steps), name)
            self.assertEqual(result.s1_bad, 0, name)
            self.assertEqual(result.s2_steps, 0, name)
        self.assertEqual([rule.confirmations for rule in library.rules], frozen)

    def test_learned_rules_agree_with_known_schemas_on_probes(self):
        known = SkillLibrary(known_rules=True)
        induced = SkillLibrary(known_rules=False)
        for _name, problem in LESSONS:
            run_skill_episode(problem, known, update=True)
            run_skill_episode(problem, induced, update=True)
        probes = []
        for _name, problem in FINALS:
            state = frozenset(problem.initial)
            bound = 8 * max(1, len(tuple(problem.blocks)))
            for _ in range(bound):
                if goal_holds(state, problem.goal):
                    break
                probes.append((state, problem.goal))
                known_step = known.propose(state, problem.goal)
                induced_step = induced.propose(state, problem.goal)
                self.assertIsNotNone(known_step)
                self.assertIsNotNone(induced_step)
                self.assertEqual(induced_step[1], known_step[1])
                state = apply(state, known_step[1])
        self.assertGreaterEqual(len(probes), 2 + 4 + 6 + 4)

    def test_ambiguous_pickup_still_refuses(self):
        library = SkillLibrary(known_rules=False)
        for _name, problem in LESSONS[:3]:
            run_skill_episode(problem, library, update=True)
        state = initial_state(["a", "b", "c"])
        goal = frozenset({("on", ("a", "c")), ("on", ("b", "c"))})
        self.assertIsNone(library.propose(state, goal))



def result_state(result):
    state = sunk_support().initial
    from cmc.blocksworld import apply

    for step in result.steps:
        state = apply(state, step.action)
    return state
