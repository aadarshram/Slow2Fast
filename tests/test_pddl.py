"""PDDL front end: domains/problems from files, pyperplan planners, typing, cross-checks vs the old
hand-written blocksworld Python."""

import random
from collections import deque
from pathlib import Path

import pytest

from cmc.contrast_induce import ContrastLibrary
from cmc.generate import test_holdout as holdout_tasks
from cmc.pddl import PddlDomain, load_problem, parse_problem_text, problem_from_atoms
from cmc.system2 import System2, run_episode

ROOT = Path(__file__).resolve().parents[1]
BW = PddlDomain(ROOT / "domains" / "blocksworld" / "domain.pddl")
GRIPPER = PddlDomain(ROOT / "domains" / "gripper" / "domain.pddl")

# The operator dict that used to be written by hand in cmc/domain.py.
OLD_OPERATORS = {
    "pickup": {"arity": 1, "pre": (("clear", ("?0",)), ("ontable", ("?0",)), ("handempty", ())),
               "add": (("holding", ("?0",)),),
               "delete": (("clear", ("?0",)), ("ontable", ("?0",)), ("handempty", ()))},
    "putdown": {"arity": 1, "pre": (("holding", ("?0",)),),
                "add": (("ontable", ("?0",)), ("clear", ("?0",)), ("handempty", ())),
                "delete": (("holding", ("?0",)),)},
    "stack": {"arity": 2, "pre": (("holding", ("?0",)), ("clear", ("?1",))),
              "add": (("on", ("?0", "?1")), ("clear", ("?0",)), ("handempty", ())),
              "delete": (("holding", ("?0",)), ("clear", ("?1",)))},
    "unstack": {"arity": 2, "pre": (("on", ("?0", "?1")), ("clear", ("?0",)), ("handempty", ())),
                "add": (("holding", ("?0",)), ("clear", ("?1",))),
                "delete": (("on", ("?0", "?1")), ("clear", ("?0",)), ("handempty", ()))},
}


def old_applicable(state, blocks):
    """The hand-written blocksworld move generator that used to live in cmc/blocksworld.py."""
    state, ordered, actions = set(state), sorted(blocks), []
    for top in ordered:
        for support in ordered:
            if top != support and {("on", (top, support)), ("clear", (top,)), ("handempty", ())} <= state:
                actions.append(("unstack", (top, support)))
    for b in ordered:
        if {("clear", (b,)), ("ontable", (b,)), ("handempty", ())} <= state:
            actions.append(("pickup", (b,)))
    for b in ordered:
        if ("holding", (b,)) in state:
            actions.append(("putdown", (b,)))
    for top in ordered:
        for support in ordered:
            if top != support and {("holding", (top,)), ("clear", (support,))} <= state:
                actions.append(("stack", (top, support)))
    return actions


def bw_problems(count=25, n=4, seed=3, solved_ok=False):
    """Random blocksworld problems; by default only ones whose initial state is not already a goal."""
    out = []
    for i, (_p, name, prob) in enumerate(holdout_tasks(n=n, seed=seed, count=3 * count)):
        problem = problem_from_atoms(BW, f"p{i}", prob.blocks, prob.initial, prob.goal)
        if solved_ok or not BW.goal_holds(problem.initial, problem.goal):
            out.append(problem)
        if len(out) == count:
            break
    return out


def true_distance(problem, state):
    queue, seen = deque([(state, 0)]), {state}
    while queue:
        cur, d = queue.popleft()
        if problem.domain.goal_holds(cur, problem.goal):
            return d
        for a in problem.domain.applicable_actions(cur, problem.objects):
            nxt = problem.domain.apply(cur, a)
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, d + 1))
    return None


def test_operators_come_from_pddl_and_match_the_old_hand_written_dict():
    for name, old in OLD_OPERATORS.items():
        got = BW.operators[name]
        assert got["arity"] == old["arity"]
        for key in ("pre", "add", "delete"):
            assert set(got[key]) == set(old[key]), (name, key)
    assert set(BW.operators) == set(OLD_OPERATORS)


def test_applicable_actions_match_old_python_on_random_states():
    rng = random.Random(0)
    for problem in bw_problems(40):
        state = problem.initial
        for _ in range(12):
            mine = BW.applicable_actions(state, problem.objects)
            assert set(mine) == set(old_applicable(state, problem.objects))
            assert len(mine) == len(set(mine))
            state = BW.apply(state, rng.choice(mine))


def test_apply_rejects_inapplicable_action():
    problem = bw_problems(1)[0]
    with pytest.raises(ValueError):
        BW.apply(problem.initial, ("putdown", (problem.objects[0],)))


def test_problem_round_trips_through_pddl_text():
    for i, (_p, _n, prob) in enumerate(holdout_tasks(n=4, seed=5, count=10)):
        problem = problem_from_atoms(BW, f"rt{i}", prob.blocks, prob.initial, prob.goal)
        assert problem.initial == frozenset(prob.initial)
        assert problem.goal == frozenset(prob.goal)
        assert set(problem.objects) == set(prob.blocks)


def test_problems_load_from_files():
    bw = load_problem(BW, ROOT / "domains" / "blocksworld" / "example_problem.pddl")
    assert set(bw.objects) == {"a", "b", "c"} and ("on", ("c", "a")) in bw.initial
    gr = load_problem(GRIPPER, ROOT / "domains" / "gripper" / "example_problem.pddl")
    assert ("type:ball", ("ball1",)) in gr.initial and ("type:gripper", ("left",)) in gr.initial


@pytest.mark.parametrize("kind", ["bfs", "ehc"])
def test_pyperplan_plans_reach_the_goal(kind):
    s2 = System2(kind)
    for problem in bw_problems(20):
        plan = s2.plan(problem, problem.initial)
        state = problem.initial
        for action in plan:
            state = BW.apply(state, action)
        assert BW.goal_holds(state, problem.goal)
    assert s2.expansions > 0 and (kind == "bfs" or s2.evals > 0)


def test_bfs_is_optimal_against_independent_search():
    s2 = System2("bfs")
    for problem in bw_problems(25):
        assert len(s2.plan(problem, problem.initial)) == true_distance(problem, problem.initial)


def test_lazy_optimal_judge_agrees_with_exact_distances():
    s2 = System2("bfs")
    for problem in bw_problems(15):
        plan = s2.plan(problem, problem.initial)
        d0 = true_distance(problem, problem.initial)
        for action in BW.applicable_actions(problem.initial, problem.objects):
            d1 = true_distance(problem, BW.apply(problem.initial, action))
            assert bool(s2.optimal(action)) == (d1 == d0 - 1), action
        assert s2.optimal(plan[0])


def test_ehc_plan_may_be_longer_than_optimal_but_never_shorter():
    e, b = System2("ehc"), System2("bfs")
    for problem in bw_problems(20):
        assert len(e.plan(problem, problem.initial)) >= len(b.plan(problem, problem.initial))


def test_planner_replans_from_arbitrary_state_not_just_the_initial_one():
    s2 = System2("bfs")
    checked = 0
    for problem in bw_problems(10, n=4, seed=11):
        state = problem.initial
        while not BW.goal_holds(state, problem.goal):
            state = BW.apply(state, s2.plan(problem, state)[0])
            remaining = s2.plan(problem, state)
            assert remaining is not None and len(remaining) == true_distance(problem, state)
            checked += 1
    assert checked > 10


# ---- typing / second domain ---------------------------------------------------------------------
def test_typing_compiles_to_unary_predicates():
    pick = GRIPPER.operators["pick"]
    assert ("type:ball", ("?0",)) in pick["pre"] and ("type:gripper", ("?2",)) in pick["pre"]
    assert BW.operators["stack"]["pre"] == OLD_OPERATORS["stack"]["pre"]  # untyped: no type atoms


def test_gripper_is_planned_and_executed_through_the_same_layer():
    problem = load_problem(GRIPPER, ROOT / "domains" / "gripper" / "example_problem.pddl")
    for kind in ("bfs", "ehc"):
        plan = System2(kind).plan(problem, problem.initial)
        state = problem.initial
        for action in plan:
            state = GRIPPER.apply(state, action)
        assert GRIPPER.goal_holds(state, problem.goal)
    assert len(System2("bfs").plan(problem, problem.initial)) == true_distance(problem, problem.initial) == 9


def test_gripper_never_applies_wrongly_typed_actions():
    problem = load_problem(GRIPPER, ROOT / "domains" / "gripper" / "example_problem.pddl")
    for name, args in GRIPPER.applicable_actions(problem.initial, problem.objects):
        if name == "pick":
            assert args[0].startswith("ball") and args[2] in ("left", "right")


def test_contrast_learner_runs_on_a_typed_domain_it_was_never_written_for():
    problem = load_problem(GRIPPER, ROOT / "domains" / "gripper" / "example_problem.pddl")
    library = ContrastLibrary(GRIPPER.operators, GRIPPER.apply)
    s2 = System2("bfs")
    for _ in range(4):
        result = run_episode(problem, library, s2, update=True)
        assert result.goal_reached
    assert library.rules


def test_ehc_plans_have_no_repeated_states_after_loop_cutting():
    s2 = System2("ehc")
    for problem in bw_problems(25):
        state, seen = problem.initial, [problem.initial]
        for action in s2.plan(problem, problem.initial):
            state = BW.apply(state, action)
            assert state not in seen
            seen.append(state)
        assert BW.goal_holds(state, problem.goal)
