"""Quick score check on the standard generalized-planning domains with the learner as it is.

Lean by design: no exact-distance audit, no pure-planner baseline, no larger-problem sets. Reports System 1
share on a frozen random test set, how many test problems were solved, and the learned rule count.
"""

import argparse
import multiprocessing
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmc import standard_problems as SP
from cmc.random_walks import WalkTraining
from cmc.contrast_induce import ContrastLibrary
from cmc.experiment import ensure_deterministic, evaluate
from cmc.pddl import PddlDomain
from cmc.system2 import System2

KINDS = list(SP.SPECS)


DERIVE_STATIC = False  # set in main() before the worker pool forks
WALK = False


def _job(task):
    kind, s2kind, seed, train, test, ties, flags = task
    flags = dict(flags)
    t0 = time.time()
    d = PddlDomain(ROOT / "domains" / kind / "domain.pddl", derive_static=DERIVE_STATIC)
    # System 2 must be able to solve every problem (it is the teacher and the fallback): screen with a budgeted EHC
    accept = lambda p: bool(System2("ehc", budget=3000).plan(p, p.initial))
    stats = {}
    tr, te = SP.train_set(kind, d, seed, train, accept, stats), SP.holdout_set(kind, d, seed, test, accept, stats)
    if WALK:  # random-walk curriculum built from a few example problems of the same generator
        tr = WalkTraining(d, SP.train_set(kind, d, seed, 6, accept, stats), budget=train, seed=seed)
    out = evaluate(lambda: ContrastLibrary(d.operators, d.apply, derived=True, ties=ties, **flags), s2kind, tr, te,
                   audit_results=False)
    out.pop("library")
    out["rejected"] = stats.get("rejected", 0)
    out["secs"] = time.time() - t0
    return out


def main():
    ensure_deterministic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", nargs="*", default=KINDS)
    ap.add_argument("--s2", choices=("ehc", "bfs"), default="ehc")
    ap.add_argument("--ties", action="store_true", help="tolerate equally acceptable proposals (needs --s2 bfs)")
    ap.add_argument("--order", action="store_true", help="cheapest discriminating condition first")
    ap.add_argument("--minimize", action="store_true", help="drop conditions no remembered bad case needs")
    ap.add_argument("--outcomes", action="store_true", help="learn from dead ends and loops of System 1's own actions")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--train", type=int, default=30)
    ap.add_argument("--test", type=int, default=30)
    ap.add_argument("--walk", action="store_true", help="train on an adaptive random-walk curriculum instead of the ordered list")
    ap.add_argument("--derive-static", action="store_true", help="add closure relations over directed static predicates")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    global DERIVE_STATIC, WALK
    DERIVE_STATIC, WALK = a.derive_static, a.walk
    flags = dict(order=a.order, minimize=a.minimize, outcomes=a.outcomes)
    tasks = [(k, a.s2, s, a.train, a.test, a.ties, tuple(sorted(flags.items()))) for k in a.domains for s in range(a.seeds)]
    t0 = time.time()
    with ProcessPoolExecutor(a.jobs, mp_context=multiprocessing.get_context("fork")) as pool:
        res = dict(zip(tasks, pool.map(_job, tasks)))
    on = [n for n, v in flags.items() if v]
    print(f"System 2 = pyperplan {a.s2}{' + ties' if a.ties else ''}{' + ' + ' + '.join(on) if on else ''}; {a.seeds} seeds; train {a.train} problems "
          f"(small to large), test {a.test} frozen random; total {time.time() - t0:.0f}s")
    print(f"{'domain':10s} {'test S1':>8s} {'solved':>8s} {'rules':>6s} {'sec/job':>8s} {'rejected':>9s}   per-seed S1 share")
    for k in a.domains:
        rs = [res[(k, a.s2, s, a.train, a.test, a.ties, tuple(sorted(flags.items())))] for s in range(a.seeds)]
        print(f"{k:10s} {statistics.mean(r['test'] for r in rs):8.3f} {statistics.mean(r['reach'] for r in rs):5.1f}/{a.test} "
              f"{statistics.mean(r['rules'] for r in rs):6.1f} {statistics.mean(r['secs'] for r in rs):8.1f} {statistics.mean(r['rejected'] for r in rs):9.1f}   "
              + " ".join(f"{r['test']:.3f}" for r in rs))


if __name__ == "__main__":
    main()
