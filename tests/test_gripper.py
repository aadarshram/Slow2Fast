"""Gripper: generator, symmetry, and the staged learning results (regression guards)."""

import random
from pathlib import Path

from slow2fast import gripper_problems as GP
from slow2fast.contrast_induce import ContrastLibrary, symmetric
from slow2fast.experiment import evaluate
from slow2fast.pddl import PddlDomain
from slow2fast.system2 import System2, run_episode

ROOT = Path(__file__).resolve().parents[1]
GRIPPER = PddlDomain(ROOT / "domains" / "gripper" / "domain.pddl")


def library(**kw):
    return lambda: ContrastLibrary(GRIPPER.operators, GRIPPER.apply, **kw)


def test_generator_makes_typed_problems_with_fresh_names():
    a = GP.make(GRIPPER, "a", random.Random(1), rooms=3, balls=4, grippers=2, prefix="t")
    b = GP.make(GRIPPER, "b", random.Random(2), rooms=3, balls=4, grippers=2, prefix="h")
    kinds = lambda p: sorted(v for v in p.object_types.values())
    assert kinds(a) == ["ball"] * 4 + ["gripper"] * 2 + ["room"] * 3
    assert not set(a.objects) & set(b.objects)  # different prefixes: no shared names
    assert sum(1 for p, _ in a.initial if p == "free") == 2
    assert all(p == "at" for p, _ in a.goal)


def test_generator_is_deterministic():
    one = [p.initial for p in GP.holdout(GRIPPER, 3, 5)]
    two = [p.initial for p in GP.holdout(GRIPPER, 3, 5)]
    assert one == two


def test_symmetric_actions_are_recognised_only_when_truly_interchangeable():
    p = GP.make(GRIPPER, "s", random.Random(0), rooms=2, balls=2, grippers=2, robot_room=0,
                ball_rooms=[0, 0], goal_rooms=[1, 1])
    ball1, ball2 = sorted(o for o, t in p.object_types.items() if t == "ball")
    g1, g2 = sorted(o for o, t in p.object_types.items() if t == "gripper")
    room = next(a[1] for a in p.initial if a[0] == "at-robby")
    pick = lambda b, g: ("pick", (b, room, g))
    assert symmetric(p.initial, p.goal, pick(ball1, g1), pick(ball1, g2))  # two free grippers
    assert symmetric(p.initial, p.goal, pick(ball1, g1), pick(ball2, g1))  # same room, same goal
    q = GP.make(GRIPPER, "s2", random.Random(0), rooms=2, balls=2, grippers=2, robot_room=0,
                ball_rooms=[0, 0], goal_rooms=[1, 0])  # now ball2 is already home: not interchangeable
    b1, b2 = sorted(o for o, t in q.object_types.items() if t == "ball")
    rm = next(a[1] for a in q.initial if a[0] == "at-robby")
    gr = sorted(o for o, t in q.object_types.items() if t == "gripper")[0]
    assert not symmetric(q.initial, q.goal, ("pick", (b1, rm, gr)), ("pick", (b2, rm, gr)))
    assert not symmetric(q.initial, q.goal, ("pick", (b1, rm, gr)), ("move", (rm, rm)))


def test_stage1_a_few_rules_take_over_completely():
    train = GP.stage1(GRIPPER, random.Random(0), 6, "t")
    test = GP.stage1(GRIPPER, random.Random(99), 20, "h")
    out = evaluate(library(derived=True), "bfs", train, test)
    assert out["reach"] == 20 and out["test"] == 1.0 and out["prec"] == 1.0
    assert {r.op for r in out["library"].rules} == {"pick", "move", "drop"}


def test_without_symmetry_the_two_grippers_block_system1_on_pick():
    train = GP.stage1(GRIPPER, random.Random(0), 6, "t")
    test = GP.stage1(GRIPPER, random.Random(99), 20, "h")
    out = evaluate(library(derived=True, symmetry=False), "bfs", train, test)
    assert out["reach"] == 20 and out["test"] < 0.7 and out["reasons"]["multi_match"] == 20


def test_stage3_generalises_to_frozen_random_and_larger_problems():
    train = GP.stage3_train(GRIPPER, 0, 100)
    test = GP.holdout(GRIPPER, 0, 60)
    out = evaluate(library(derived=True, ties=True), "bfs", train, test)
    assert out["reach"] == 60 and out["test"] > 0.9 and out["prec"] > 0.98 and out["rules"] < 15
    lib, s2 = out["library"], System2("bfs")
    big = GP.holdout(GRIPPER, 500, 10, prefix="o", max_rooms=4, max_balls=5, max_grippers=3)
    results = [run_episode(p, lib, s2, update=False) for p in big]
    assert all(r.goal_reached for r in results)
    assert sum(r.s1_ok for r in results) / sum(len(r.steps) for r in results) > 0.8


def test_tie_tolerance_is_opt_in():
    assert ContrastLibrary(GRIPPER.operators, GRIPPER.apply).ties is False
