"""Random-walk curriculum: solvable non-trivial problems, goal predicates, partial goals, adaptive schedule."""

import random
from pathlib import Path

from cmc import standard_problems as SP
from cmc.contrast_induce import ContrastLibrary
from cmc.experiment import NullLibrary, evaluate
from cmc.pddl import PddlDomain
from cmc.random_walks import WalkTraining, goal_predicates, random_walk, walk_problem
from cmc.system2 import System2

ROOT = Path(__file__).resolve().parents[1]
GRIPPER = PddlDomain(ROOT / "domains" / "gripper" / "domain.pddl")


def templates(count=4):
    return SP.train_set("gripper", GRIPPER, 0, count)


def test_a_random_walk_only_makes_legal_moves_and_stays_put_when_there_are_none():
    t = templates(1)[0]
    rng = random.Random(0)
    end = random_walk(GRIPPER, t.initial, t.objects, 6, rng)
    assert end != t.initial and all(isinstance(a, tuple) for a in end)
    assert random_walk(GRIPPER, t.initial, t.objects, 0, rng) == t.initial


def test_walk_problems_are_solvable_and_not_already_solved():
    ts, rng, bfs = templates(), random.Random(1), System2("bfs")
    for i in range(10):
        p = walk_problem(GRIPPER, ts, 1 + i % 5, rng, f"w{i}")
        assert p is not None
        assert not GRIPPER.goal_holds(p.initial, p.goal)
        assert bfs.plan(p, p.initial) is not None  # the goal is true at the end of a path from the start


def test_goals_use_only_the_predicates_of_the_templates_goal():
    ts = templates()
    allowed = set().union(*(goal_predicates(t) for t in ts))
    rng = random.Random(2)
    for i in range(8):
        p = walk_problem(GRIPPER, ts, 4, rng, f"w{i}")
        assert {a[0] for a in p.goal} <= allowed


def test_partial_goals_are_smaller_but_never_already_satisfied():
    ts = templates()
    full = [walk_problem(GRIPPER, ts, 8, random.Random(s), "f") for s in range(6)]
    part = [walk_problem(GRIPPER, ts, 8, random.Random(s), "p", goal_fraction=0.3) for s in range(6)]
    assert all(p is not None and not GRIPPER.goal_holds(p.initial, p.goal) for p in part)
    assert sum(len(p.goal) for p in part) <= sum(len(p.goal) for p in full)


def test_the_schedule_runs_records_what_it_did_and_respects_its_bounds():
    schedule = WalkTraining(GRIPPER, templates(), budget=12, seed=0, window=2, patience=3, n_max=9)
    sources = schedule.run(NullLibrary(), System2("bfs"))  # System 1 never acts: share 0 throughout
    lengths = [n for n, _share in schedule.history]
    assert len(schedule.history) == 12 and sources and set(sources) == {"s2"}
    assert lengths[0] == 1 and max(lengths) > 1 and 1 <= min(lengths) and max(lengths) <= 9


def test_next_length_follows_how_system_1_is_doing():
    from collections import deque

    sched = WalkTraining(GRIPPER, templates(), budget=1, window=2, patience=3, n_max=9)  # tau 0.9, delta 0.1
    shares = lambda *v: deque(v, maxlen=2)
    assert sched.next_length(1, shares(1.0), 0) == 1            # not enough recent problems yet
    assert sched.next_length(1, shares(1.0, 1.0), 2) == 2       # on top of it: longer
    assert sched.next_length(4, shares(0.95, 0.9), 2) == 6      # grows geometrically (4 * 1.5)
    assert sched.next_length(2, shares(0.2, 0.2), 2) == 1       # fell behind a longer walk: shorter
    assert sched.next_length(3, shares(0.85, 0.85), 2) == 3     # between tau - delta and tau: stay
    assert sched.next_length(1, shares(0.2, 0.2), 3) == 2       # stuck at the shortest walks: advance on patience
    assert sched.next_length(9, shares(1.0, 1.0), 2) == 9       # never beyond n_max


def test_evaluate_accepts_a_walk_schedule_in_place_of_a_list_of_problems():
    test = SP.holdout_set("gripper", GRIPPER, 0, 3)
    schedule = WalkTraining(GRIPPER, templates(), budget=6, seed=0)
    out = evaluate(lambda: ContrastLibrary(GRIPPER.operators, GRIPPER.apply, derived=True), "bfs", schedule, test,
                   audit_results=False)
    assert out["reach"] == 3 and len(schedule.history) == 6
