"""Optional closure relations over directed static predicates (domain-independent, off by default)."""

import random
from pathlib import Path

from slow2fast import standard_problems as SP
from slow2fast.contrast_induce import ContrastLibrary
from slow2fast.pddl import PddlDomain, problem_text
from slow2fast.system2 import System2

ROOT = Path(__file__).resolve().parents[1]


def domain(name, derive):
    return PddlDomain(ROOT / "domains" / name / "domain.pddl", derive_static=derive)


def derived(problem):
    return {a for a in problem.initial if a[0].startswith(("closure:", "closure-inv:"))}


def test_static_relations_are_found_from_the_operators_alone():
    assert domain("blocksworld", False).static_relations == []  # every predicate is changed by some operator
    tidy = set(domain("tidybot", False).static_relations)
    assert {"leftof", "above", "leftof-rel", "above-rel"} <= tidy
    assert "base-pos" not in tidy and "holding" not in tidy


def test_a_directed_chain_gets_closure_and_inverse_closure():
    d = domain("spanner", True)
    p = SP.make_spanner(d, "s", random.Random(0), inner=2, nuts=1, extra_spanners=0)  # 4 locations in a line
    links = {a[1] for a in p.initial if a[0] == "link"}
    forward = {a[1] for a in p.initial if a[0] == "closure:link"}
    backward = {a[1] for a in p.initial if a[0] == "closure-inv:link"}
    assert len(links) == 3 and len(forward) == 6 and links <= forward  # every ordered pair along the corridor
    assert backward == {(y, x) for x, y in forward}


def test_relations_without_a_direction_or_a_chain_get_nothing():
    grid = SP.make_delivery(domain("delivery", True), "d", random.Random(0), 3, 3, 1)
    assert derived(grid) == set()  # adjacency is symmetric
    lift = SP.make_miconic(domain("miconic", True), "m", random.Random(0), 4, 2)
    names = {a[0] for a in derived(lift)}
    assert names == {"closure-inv:above"}  # origin/destin never chain; above is already closed, so only "below" is new


def test_off_by_default_and_the_state_is_otherwise_unchanged():
    off = SP.make_spanner(domain("spanner", False), "s", random.Random(0), 2, 1, 0)
    on = SP.make_spanner(domain("spanner", True), "s", random.Random(0), 2, 1, 0)
    assert derived(off) == set() and derived(on)
    assert on.initial - derived(on) == off.initial and on.goal == off.goal


def test_derived_atoms_are_never_written_into_problem_files():
    d = domain("spanner", True)
    p = SP.make_spanner(d, "s", random.Random(0), 2, 1, 0)
    assert "closure" not in problem_text(d, "x", p.object_types, p.initial, p.goal)


def test_planning_and_learning_still_work_with_the_extra_relations():
    d = domain("spanner", True)
    p = SP.make_spanner(d, "s", random.Random(1), 2, 1, 0)
    assert System2("bfs").plan(p, p.initial) is not None
    view = ContrastLibrary(d.operators, d.apply)._view(p.initial, p.goal)
    assert any(pred == "closure:link" for _src, pred, _args in view)  # rules can now use it as a condition
