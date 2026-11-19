"""Learning from the outcomes of System 1's own actions (dead ends and loops)."""

import random
from pathlib import Path

from cmc import benchmark_problems as BP  # noqa: F401  (keeps imports of the generators exercised)
from cmc import standard_problems as SP
from cmc.contrast_induce import ContrastLibrary, Rule
from cmc.pddl import PddlDomain
from cmc.system2 import System2, run_episode

ROOT = Path(__file__).resolve().parents[1]
SPANNER = PddlDomain(ROOT / "domains" / "spanner" / "domain.pddl")


def doomed_spanner():
    """Corridor shed - inner - gate, one spanner lying at the shed, one nut at the gate: the first walk step
    leaves the only spanner behind, so the goal becomes unreachable."""
    rng = random.Random(0)
    for _ in range(200):
        p = SP.make_spanner(SPANNER, "s", rng, inner=1, nuts=1, extra_spanners=0)
        man = next(a[0] for a in p.initial if a[0] == "at" and p.object_types[a[1][0]] == "man")
        shed = next(a[1][1] for a in p.initial if a[0] == "at" and p.object_types[a[1][0]] == "man")
        spanner = next(o for o, t in p.object_types.items() if t == "spanner")
        if ("at", (spanner, shed)) in p.initial:
            return p
    raise AssertionError("no suitable problem")


def lib_with_overgeneral_walk(**kw):
    lib = ContrastLibrary(SPANNER.operators, SPANNER.apply, outcomes=True, **kw)
    from cmc.contrast_induce import lifted_pre

    params = ("?a0", "?a1", "?a2")
    pre = lifted_pre(SPANNER.operators, "walk", params)
    rule = Rule("walk", params, pre, pre)
    rule.confirmations = 2  # practiced
    lib.rules.append(lib._register(rule))
    return lib


def test_a_dead_end_caused_by_system1_becomes_a_negative_of_the_rule_that_proposed_it():
    problem, lib = doomed_spanner(), lib_with_overgeneral_walk()
    result = run_episode(problem, lib, System2("bfs"), update=True)
    assert not result.goal_reached  # System 1 walked away from the spanner; System 2 cannot recover
    rule = lib.rules[0]
    assert lib.stats["outcome_neg"] == 1 and len(rule.neg) == 1
    view, action = rule.neg[0]
    assert action[0] == "walk"  # the very first step, not the last one, is blamed


def test_without_the_outcome_flag_nothing_is_recorded():
    problem = doomed_spanner()
    lib = lib_with_overgeneral_walk()
    lib.learns_outcomes = False
    run_episode(problem, lib, System2("bfs"), update=True)
    assert lib.stats["outcome_neg"] == 0 and lib.rules[0].neg == []


def test_frozen_test_runs_do_not_learn_from_outcomes():
    problem, lib = doomed_spanner(), lib_with_overgeneral_walk()
    run_episode(problem, lib, System2("bfs"), update=False)
    assert lib.stats["outcome_neg"] == 0


def test_blame_follows_rules_that_were_forked_since():
    lib = lib_with_overgeneral_walk()
    parent = lib.rules[0].rid
    lib._descendants[parent] = [10, 11]
    lib._descendants[10] = [12]
    assert lib._alive([parent]) == {parent, 10, 11, 12}


def test_system2_dead_end_test_is_exact_for_bfs():
    problem, s2 = doomed_spanner(), System2("bfs")
    assert not s2.is_dead(problem, problem.initial)
    first = next(a for a in SPANNER.applicable_actions(problem.initial, problem.objects) if a[0] == "walk")
    assert s2.is_dead(problem, SPANNER.apply(problem.initial, first))
