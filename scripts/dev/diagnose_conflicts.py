"""Why does System 1 hand a step to System 2? Classifies every multi-match call on a frozen test set.

  tie                  all the competing proposals are equally good (the judge says so): no condition can separate them
  resolvable           some proposal is worse and a separating condition exists in the current vocabulary,
                       but the rule has not learned it yet
  missing vocabulary   some proposal is worse and no condition in the vocabulary separates it

Also counts the other reasons (silence, below threshold). Needs bfs as System 2 for the judge.
"""

import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slow2fast.contrast_induce import ContrastLibrary, Rule
from slow2fast.experiment import ensure_deterministic
from slow2fast.pddl import PddlDomain
from slow2fast.system2 import System2, run_episode
from scripts.run_bundle import build


def classify(lib, view, acts, plan, judge):
    acceptable = [a for a in acts if a == plan[0] or judge(a)]
    if len(acceptable) == len(acts):
        return "tie"
    for _i, rule, grounded in lib._ground_all(view):
        if rule.confirmations < lib.threshold:
            continue
        for act in grounded:
            if act in acceptable:
                continue
            tmp = Rule(rule.op, rule.params, list(rule.lits), rule.protected)
            tmp.pos, tmp.pinned, tmp.rid = list(rule.pos), dict(rule.pinned), rule.rid
            tmp.neg = list(rule.neg) + [(view, act)]
            if not tmp.pos or lib._best_cover(tmp, tmp.pos, [(view, act)]) is None:
                return "missing vocabulary"
    return "resolvable"


def main():
    ensure_deterministic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", nargs="*", default=["gripper", "ferry", "miconic", "spanner", "delivery"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--train", type=int, default=20)
    ap.add_argument("--test", type=int, default=20)
    a = ap.parse_args()
    for kind in a.domains:
        d = PddlDomain(ROOT / "domains" / kind / "domain.pddl")
        train, test = build(kind, a.seed, a.train, a.test, d)
        lib, s2 = ContrastLibrary(d.operators, d.apply, derived=True), System2("bfs")
        for p in train:
            run_episode(p, lib, s2, update=True)
        counts, by_op, steps, s2_calls = collections.Counter(), collections.defaultdict(collections.Counter), 0, 0
        for p in test:
            state, seen, judge = p.initial, {p.initial}, System2("bfs")
            for _ in range(8 * len(p.objects)):
                if d.goal_holds(state, p.goal):
                    break
                steps += 1
                prop = lib.propose(state, p.goal)
                if prop and d.apply(state, prop[1]) not in seen:
                    state = d.apply(state, prop[1])
                    seen.add(state)
                    continue
                reason, acts = lib.diagnose(state, p.goal)
                plan = judge.plan(p, state)
                if not plan:
                    break
                s2_calls += 1
                label = reason
                if reason == "multi_match":
                    label = classify(lib, lib._view(frozenset(state), frozenset(p.goal)), acts, plan, judge.optimal)
                counts[label] += 1
                by_op[label][plan[0][0]] += 1
                state = d.apply(state, plan[0])
                seen.add(state)
        print(f"\n== {kind}: {s2_calls} System 2 calls out of {steps} steps ({100 * s2_calls / max(1, steps):.0f}%)")
        for label, n in counts.most_common():
            print(f"   {n:4d}  {label:20s} " + " ".join(f"{op}:{c}" for op, c in by_op[label].most_common(4)))


if __name__ == "__main__":
    main()
