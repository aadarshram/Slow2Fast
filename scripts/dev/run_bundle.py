"""Base learner vs. the learning-time bundle on the standard domains (optionally Barman), lean metrics.

Bundle = outcome learning (dead ends, loops) + complexity-ordered discriminators + minimisation with pinned
cases + rule pruning + learning-time spot-checks. All of it happens while learning; System 1 itself stays reactive.
--ablate adds one leave-one-out variant per component (run it only after the bundle itself shows a difference).
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

from slow2fast import benchmark_problems as BP
from slow2fast import standard_problems as SP
from slow2fast.random_walks import WalkTraining
from slow2fast.contrast_induce import ContrastLibrary
from slow2fast.experiment import ensure_deterministic, evaluate
from slow2fast.pddl import PddlDomain
from slow2fast.system2 import System2

BUNDLE = dict(outcomes=True, order=True, minimize=True, prune=True, audit_rate=0.25)
OFF = dict(outcomes=False, order=False, minimize=False, prune=False, audit_rate=0.0)
CONFIGS = {"base": {}, "bundle": dict(BUNDLE)}
for part in BUNDLE:
    CONFIGS[f"bundle - {part}"] = {**BUNDLE, part: OFF[part]}
DOMAINS = list(SP.SPECS) + ["barman"]


def build(kind, seed, train, test, d):
    accept = lambda p: bool(System2("ehc", budget=3000).plan(p, p.initial))
    if kind == "barman":
        tr, te = BP.train_set(kind, d, seed, train, accept), BP.holdout_set(kind, d, seed, test, accept)
        templates = BP.train_set(kind, d, seed, 6, accept)
    else:
        tr, te = SP.train_set(kind, d, seed, train, accept), SP.holdout_set(kind, d, seed, test, accept)
        templates = SP.train_set(kind, d, seed, 6, accept)
    if WALK:  # random-walk curriculum built from a few example problems of the same generator
        tr = WalkTraining(d, templates, budget=train, seed=seed)
    return tr, te


DERIVE_STATIC = False  # set in main() before the worker pool forks
WALK = False


def _job(task):
    kind, s2kind, seed, train, test, cfg = task
    t0 = time.time()
    d = PddlDomain(ROOT / "domains" / kind / "domain.pddl", derive_static=DERIVE_STATIC)
    tr, te = build(kind, seed, train, test, d)
    out = evaluate(lambda: ContrastLibrary(d.operators, d.apply, derived=True, **CONFIGS[cfg]), s2kind, tr, te,
                   audit_results=False)
    lib = out.pop("library")
    out["stats"] = {k: lib.stats[k] for k in ("minimized", "pruned", "audits", "audit_wrong", "outcome_neg")}
    out["secs"] = time.time() - t0
    return out


def main():
    ensure_deterministic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", nargs="*", default=[d for d in DOMAINS if d not in ("barman", "logistics")],
                    help="logistics and barman are excluded by default: BFS and the audits make them very slow")
    ap.add_argument("--s2", choices=("bfs", "ehc"), default="bfs", help="spot-checks need bfs (exact judge)")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--train", type=int, default=20)
    ap.add_argument("--test", type=int, default=20)
    ap.add_argument("--ablate", action="store_true")
    ap.add_argument("--walk", action="store_true", help="train on an adaptive random-walk curriculum instead of the ordered list")
    ap.add_argument("--derive-static", action="store_true", help="add closure relations over directed static predicates")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    global DERIVE_STATIC, WALK
    DERIVE_STATIC, WALK = a.derive_static, a.walk
    cfgs = [c for c in CONFIGS if a.ablate or c in ("base", "bundle")]
    out_file = open(a.out, "w") if a.out else None

    def emit(text=""):
        print(text, flush=True)
        if out_file:
            out_file.write(text + "\n")
            out_file.flush()

    emit(f"System 2 = pyperplan {a.s2}; {a.seeds} seeds; train {a.train}, test {a.test} problems per domain; "
         f"learning-time bundle = {', '.join(BUNDLE)}")
    summary = {c: [] for c in cfgs}
    t0 = time.time()
    with ProcessPoolExecutor(a.jobs, mp_context=multiprocessing.get_context("fork")) as pool:
        for k in a.domains:
            tasks = [(k, a.s2, s, a.train, a.test, c) for c in cfgs for s in range(a.seeds)]
            res = dict(zip(tasks, pool.map(_job, tasks)))
            emit(f"\n== {k}")
            emit(f"{'config':24s} {'test S1':>8s} {'solved':>8s} {'S1 alone':>9s} {'rules':>6s} {'sec/job':>8s}  per-seed S1 share")
            for c in cfgs:
                rs = [res[(k, a.s2, s, a.train, a.test, c)] for s in range(a.seeds)]
                m = lambda key: statistics.mean(r[key] for r in rs)
                summary[c].append((m("test"), m("reach") / a.test, m("s1_alone") / a.test, m("rules")))
                emit(f"{c:24s} {m('test'):8.3f} {m('reach'):5.1f}/{a.test} {m('s1_alone'):6.1f}/{a.test} {m('rules'):6.1f} {m('secs'):8.1f}  "
                     + " ".join(f"{r['test']:.3f}" for r in rs))
            b = [res[(k, a.s2, s, a.train, a.test, "bundle")]["stats"] for s in range(a.seeds)]
            emit("   bundle counters (mean/seed): " + " ".join(f"{key}={statistics.mean(x[key] for x in b):.1f}" for key in b[0]))
    emit(f"\n== mean over {len(a.domains)} domains (total {time.time() - t0:.0f}s)")
    emit(f"{'config':24s} {'test S1':>8s} {'solved':>8s} {'S1 alone':>9s} {'rules':>6s}")
    for c in cfgs:
        cols = list(zip(*summary[c]))
        emit(f"{c:24s} {statistics.mean(cols[0]):8.3f} {statistics.mean(cols[1]):8.3f} {statistics.mean(cols[2]):9.3f} {statistics.mean(cols[3]):6.1f}")


if __name__ == "__main__":
    main()
