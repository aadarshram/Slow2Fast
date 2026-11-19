"""Pruning, learning-time spot-checks, the System-1-only runner and the bundle switch."""

from pathlib import Path

from cmc import standard_problems as SP  # noqa: F401
from cmc.contrast_induce import ContrastLibrary, Rule, lifted_pre
from cmc.pddl import PddlDomain
from cmc.system2 import System2, run_episode, run_s1_only
from tests.test_outcomes import SPANNER, doomed_spanner, lib_with_overgeneral_walk


def walk_rule(lib, confirmations=2, extra=()):
    params = ("?a0", "?a1", "?a2")
    pre = lifted_pre(SPANNER.operators, "walk", params)
    rule = Rule("walk", params, pre + list(extra), pre)
    rule.confirmations = confirmations
    lib.rules.append(lib._register(rule))
    return rule


def fresh(**kw):
    return ContrastLibrary(SPANNER.operators, SPANNER.apply, **kw)


def test_bundle_switches_the_learning_time_mechanisms_on():
    lib = fresh(bundle=True)
    assert lib.learns_outcomes and lib.order and lib.minimize and lib.prune_flag and lib.audit_rate == 0.25
    plain = fresh()
    assert not (plain.learns_outcomes or plain.order or plain.minimize or plain.prune_flag) and plain.audit_rate == 0


def test_pruning_merges_identical_rules_and_repoints_links():
    lib = fresh(prune=True)
    a, b = walk_rule(lib, 3), walk_rule(lib, 4)
    other = walk_rule(lib, 2, extra=[("-", "s", "at", ("?a0", "?a2"))])
    other.defer.add(b.rid)
    lib._prune()
    assert len(lib.rules) == 2 and a in lib.rules and b not in lib.rules
    assert a.confirmations == 7
    assert other.defer == {a.rid}  # the link now points at the survivor
    assert lib._alive([b.rid]) >= {b.rid, a.rid}


def test_pruning_forgets_stale_unpracticed_rules_only():
    lib = fresh(prune=True, prune_age=5)
    stale = walk_rule(lib, 1, extra=[("-", "s", "at", ("?a0", "?a2"))])
    practiced = walk_rule(lib, 5)
    lib.lesson = 100
    lib._prune()
    assert stale not in lib.rules and practiced in lib.rules


def test_pruning_is_off_by_default():
    lib = fresh()
    a, b = walk_rule(lib, 3), walk_rule(lib, 4)
    lib.lesson = 1000
    lib._prune()
    assert a in lib.rules and b in lib.rules


def test_a_spot_check_catches_a_worse_action_and_system_2_rescues_the_episode():
    problem = doomed_spanner()
    lib = lib_with_overgeneral_walk()
    lib.audit_rate = 1.0  # check every proposal
    result = run_episode(problem, lib, System2("bfs"), update=True)
    assert lib.stats["audits"] >= 1 and lib.stats["audit_wrong"] >= 1
    assert result.goal_reached  # without the check this problem is unrecoverable (see test_outcomes)
    assert len(lib.rules[0].neg) >= 1  # the wrong proposal became a negative of the rule


def test_no_spot_check_without_an_exact_system_2():
    problem = doomed_spanner()
    lib = lib_with_overgeneral_walk()
    lib.audit_rate = 1.0
    run_episode(problem, lib, System2("ehc"), update=True)
    assert lib.stats["audits"] == 0


def test_s1_alone_succeeds_only_if_it_never_has_to_refuse():
    problem = doomed_spanner()
    assert not run_s1_only(problem, fresh())  # no rules: refuses at once
    assert not run_s1_only(problem, lib_with_overgeneral_walk())  # walks away from the spanner, cannot finish
