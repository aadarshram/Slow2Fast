"""Complexity-ordered discriminators and greedy minimisation"""

import random
from pathlib import Path

from cmc import gripper_problems as GP
from cmc.contrast_induce import ContrastLibrary, Rule, _complexity, lifted_pre
from cmc.pddl import PddlDomain

ROOT = Path(__file__).resolve().parents[1]
GRIPPER = PddlDomain(ROOT / "domains" / "gripper" / "domain.pddl")
NEEDED = ("+", "g", "at", ("?a0", "?g3"))        # the ball has a goal
UNNEEDED = ("-", "s", "at", ("?a0", "?a2"))      # the ball is not "at" the gripper: always true, never separates


def scenario():
    """Two balls in the robot's room; only ball 0 has a goal. Picking ball 1 is the bad case."""
    rng = random.Random(1)
    p = GP.make(GRIPPER, "m", rng, rooms=2, balls=2, grippers=1, robot_room=0, ball_rooms=[0, 0],
                goal_rooms=[1, 1], goal_balls=[0])
    balls = sorted(o for o, t in p.object_types.items() if t == "ball")
    with_goal = next(b for b in balls if any(a[0] == "at" and a[1][0] == b for a in p.goal))
    without = next(b for b in balls if b != with_goal)
    room = next(a[1][0] for a in p.initial if a[0] == "at-robby")
    grip = next(o for o, t in p.object_types.items() if t == "gripper")
    return p, ("pick", (without, room, grip))


def practiced_rule(lib):
    params = ("?a0", "?a1", "?a2")
    pre = lifted_pre(GRIPPER.operators, "pick", params)
    rule = Rule("pick", params, pre + [NEEDED, UNNEEDED], pre)
    rule.confirmations = 2
    return lib._register(rule)


def test_complexity_counts_negation_and_fresh_objects():
    assert _complexity(("+", "s", "free", ("?a0",))) == 1
    assert _complexity(("-", "s", "free", ("?a0",))) == 2
    assert _complexity(("+", "s", "carry", ("?v3_0", "?v3_1"))) == 3
    assert _complexity(("-", "g", "at", ("?a0", "?v3_0"))) == 3


def test_minimisation_drops_the_condition_nothing_needs_and_keeps_the_one_a_bad_case_needs():
    p, bad = scenario()
    lib = ContrastLibrary(GRIPPER.operators, GRIPPER.apply, minimize=True)
    rule = practiced_rule(lib)
    view = lib._view(p.initial, p.goal)
    assert bad not in rule.groundings(view)  # with the goal condition the rule does not pick the ball without a goal
    assert bad in rule.groundings(view, [l for l in rule.lits if l != NEEDED])  # ... and without it, it would
    rule.neg = [(view, bad)]
    lib._minimize(rule)
    assert NEEDED in rule.lits and UNNEEDED not in rule.lits
    assert lib.stats["minimized"] == 1


def test_a_pinned_case_keeps_its_condition_even_after_the_bounded_store_has_forgotten_it():
    p, bad = scenario()
    view = ContrastLibrary(GRIPPER.operators, GRIPPER.apply)._view(p.initial, p.goal)
    kept = ContrastLibrary(GRIPPER.operators, GRIPPER.apply, minimize=True)
    rule = practiced_rule(kept)
    rule.neg = []                                  # forgotten ...
    rule.pinned = {NEEDED: [(view, bad)]}          # ... but pinned to the condition added for it
    kept._minimize(rule)
    assert NEEDED in rule.lits
    lost = ContrastLibrary(GRIPPER.operators, GRIPPER.apply, minimize=True)
    rule2 = practiced_rule(lost)
    rule2.neg = []                                 # forgotten and not pinned: nothing protects the condition
    lost._minimize(rule2)
    assert NEEDED not in rule2.lits


def test_unpracticed_rules_are_left_alone():
    lib = ContrastLibrary(GRIPPER.operators, GRIPPER.apply, minimize=True)
    rule = practiced_rule(lib)
    rule.confirmations = 1
    lib._minimize(rule)
    assert NEEDED in rule.lits and UNNEEDED in rule.lits


def test_memory_stays_bounded():
    lib = ContrastLibrary(GRIPPER.operators, GRIPPER.apply, memory=6)
    store = []
    for i in range(50):
        lib._remember(store, (i, i))
    assert len(store) == 6 and store[0] == (44, 44)
