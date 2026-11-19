"""Barman, Termes, Tidybot with the learner exactly as it is (no per-domain changes).

Per (domain, System 2, seed): train on the domain's curriculum plus a random tail, then test frozen on
random problems from the same distribution and (EHC only) on larger problems. All problems are screened with
System 2 at generation time (solvable, plan length and expansion budget), so every test problem is solvable.
"""

import argparse
import multiprocessing
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmc import benchmark_problems as BP
from cmc.contrast_induce import ContrastLibrary
from cmc.experiment import ensure_deterministic, evaluate, pure_system2_work
from cmc.pddl import PddlDomain
from cmc.system2 import System2, run_episode

KINDS = ("barman", "termes", "tidybot")
PLAN_CAP = {"barman": 30, "termes": 45, "tidybot": 30}
CONFIGS = {
    "strict": dict(derived=True),
    "ties": dict(derived=True, ties=True),
    "outcomes": dict(derived=True, outcomes=True),
    "outcomes+min": dict(derived=True, outcomes=True, minimize=True),
    "outcomes+order+min": dict(derived=True, outcomes=True, order=True, minimize=True),
}
_domains = {}


def domain(kind):
    if kind not in _domains:
        _domains[kind] = PddlDomain(ROOT / "domains" / kind / "domain.pddl")
    return _domains[kind]


def accept_for(kind):
    cap = PLAN_CAP[kind]

    def accept(problem):
        plan = System2("ehc", budget=4000).plan(problem, problem.initial)
        return plan is not None and 0 < len(plan) <= cap

    return accept


def sets(kind, seed, train_random, test_count, big_count):
    d, acc = domain(kind), accept_for(kind)
    train = BP.train_set(kind, d, seed, train_random, acc)
    test = BP.holdout_set(kind, d, seed, test_count, acc)
    big = BP.holdout_set(kind, d, seed, big_count, acc, big=True) if big_count else []
    return train, test, big


def _job(task):
    kind, s2kind, seed, cfg, train_random, test_count, big_count, with_rules = task
    d = domain(kind)
    train, test, big = sets(kind, seed, train_random, test_count, big_count if s2kind == "ehc" else 0)
    factory = lambda: ContrastLibrary(d.operators, d.apply, **CONFIGS[cfg])
    out = evaluate(factory, s2kind, train, test)
    out["pure"] = pure_system2_work(s2kind, test)
    out["n_train"] = len(train)
    lib = out.pop("library")
    if big:
        s2, t2, steps, s1, solved = System2(s2kind), System2(s2kind), 0, 0, 0
        for p in big:
            r = run_episode(p, lib, t2, update=False)
            steps += len(r.steps); s1 += r.s1_ok; solved += r.goal_reached
        out["ood"] = (s1 / max(1, steps), solved, len(big), t2.work, pure_system2_work(s2kind, big))
    if with_rules:
        out["rules_text"] = [
            f"r{i} {r.op}{r.params} conf={r.confirmations} defer={sorted(r.defer)} + "
            f"{[l for l in r.lits if l not in r.protected]}" for i, r in enumerate(lib.rules)
        ]
    return out


def main():
    ensure_deterministic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", nargs="*", default=list(KINDS))
    ap.add_argument("--s2", nargs="*", default=["bfs", "ehc"])
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--train-random", type=int, default=40)
    ap.add_argument("--test", type=int, default=30)
    ap.add_argument("--big", type=int, default=12)
    ap.add_argument("--rules", action="store_true")
    ap.add_argument("--configs", nargs="*", default=None, help="subset of: strict ties outcomes outcomes+min outcomes+order+min")
    ap.add_argument("--jobs", type=int, default=4, help="worker processes; each can use ~1 GB on Tidybot")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out_file = open(a.out, "w") if a.out else None

    def emit(text):
        print(text, flush=True)
        if out_file:
            out_file.write(text + "\n")
            out_file.flush()

    with ProcessPoolExecutor(a.jobs, mp_context=multiprocessing.get_context("fork")) as pool:
        for k in a.domains:
            for s in a.s2:
                cfgs = [c for c in CONFIGS if not (c == "ties" and s == "ehc") and (not a.configs or c in a.configs)]
                tasks = [(k, s, seed, c, a.train_random, a.test, a.big, a.rules and seed == 0)
                         for c in cfgs for seed in range(a.seeds)]
                res = dict(zip(tasks, pool.map(_job, tasks)))
                emit(f"\n== {k}, System 2 = pyperplan {s}: {a.seeds} seeds; train = curriculum + {a.train_random} random; "
                     f"test = {a.test} frozen random" + (f"; big = {a.big} larger" if s == "ehc" else ""))
                emit(f"{'learner':8s} {'test S1':>8s} {'prec':>6s} {'deadend':>7s} {'rules':>6s} {'solved':>7s} {'S2cost%':>8s} {'len/opt':>8s}"
                     + ("  | larger problems: S1 share  solved  cost%" if s == "ehc" else ""))
                for c in cfgs:
                    rs = [res[(k, s, seed, c, a.train_random, a.test, a.big, a.rules and seed == 0)] for seed in range(a.seeds)]
                    avg = lambda key: statistics.mean(r[key] for r in rs)
                    cost = statistics.mean(r["work"] / max(1, r["pure"]) for r in rs) * 100
                    line = (f"{c:8s} {avg('test'):8.3f} {avg('prec'):6.3f} {avg('dead_ends'):7.1f} {avg('rules'):6.1f} "
                            f"{avg('reach'):5.1f}/{rs[0]['tasks']} {cost:8.1f} {avg('overhead'):8.3f}")
                    if s == "ehc":
                        o = [r["ood"] for r in rs]
                        line += (f"  | {statistics.mean(x[0] for x in o):24.3f} {statistics.mean(x[1] for x in o):5.1f}/{o[0][2]} "
                                 f"{100 * statistics.mean(x[3] / max(1, x[4]) for x in o):6.1f}")
                    emit(line)
                    emit(f"{'':8s} per-seed test S1: " + " ".join(f"{r['test']:.3f}" for r in rs) + "   per-seed solved: "
                         + " ".join(f"{r['reach']}" for r in rs) + "   per-seed dead-ends: " + " ".join(f"{r['dead_ends']}" for r in rs)
                         + "   S2 calls (seed 0): " + " ".join(f"{k2}={v}" for k2, v in rs[0]["reasons"].items() if v))
                    if a.rules:
                        for text in rs[0].get("rules_text", []):
                            emit("    " + text[:230])


if __name__ == "__main__":
    main()
