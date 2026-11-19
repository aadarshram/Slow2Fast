"""Gripper stage 3 across seeds and settings: curriculum + random tail, tested on a frozen random holdout
and on larger problems the learner never saw. One process per (setting, seed)."""

import argparse
import multiprocessing
import os
import random
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slow2fast import gripper_problems as GP
from slow2fast.contrast_induce import ContrastLibrary
from slow2fast.experiment import ensure_deterministic, evaluate, pure_system2_work
from slow2fast.pddl import PddlDomain

DOMAIN = PddlDomain(ROOT / "domains" / "gripper" / "domain.pddl")
BIG = dict(max_rooms=4, max_balls=5, max_grippers=3)


def lib(**kw):
    return lambda: ContrastLibrary(DOMAIN.operators, DOMAIN.apply, **kw)


CONFIGS = {
    "original settings": lib(derived=True, symmetry=False, full_cover=False),
    "+ symmetry": lib(derived=True, symmetry=True, full_cover=False),
    "+ symmetry + full cover": lib(derived=True),
    "+ symmetry + full cover + ties": lib(derived=True, ties=True),
    "  ablate: no sat/unsat": lib(derived=False, ties=True),
    "  ablate: no deferral link": lib(derived=True, ties=True, defer=False),
    "  ablate: no symmetry": lib(derived=True, ties=True, symmetry=False),
    "  ablate: no merge": lib(derived=True, ties=True, merge=False),
    "  ablate: no negated literals": lib(derived=True, ties=True, allow_neg=False),
}


def _job(task):
    name, kind, seed, ood = task
    train = GP.stage3_train(DOMAIN, seed, 100)
    test = GP.holdout(DOMAIN, seed, 100)
    out = evaluate(CONFIGS[name], kind, train, test)
    out.pop("library")
    if ood:
        big = GP.holdout(DOMAIN, seed + 500, ood, prefix="o", **BIG)
        library = None
        # same trained learner on larger problems: retrain deterministically, then test frozen
        from slow2fast.system2 import System2, run_episode

        factory = CONFIGS[name]
        lb, s2 = factory(), System2(kind)
        for p in train:
            run_episode(p, lb, s2, update=True)
        t2 = System2(kind)
        steps = s1 = solved = 0
        for p in big:
            r = run_episode(p, lb, t2, update=False)
            steps += len(r.steps)
            s1 += r.s1_ok
            solved += r.goal_reached
        out["ood"] = (s1 / max(1, steps), solved, len(big), t2.work, pure_system2_work(kind, big))
    return out


def main():
    ensure_deterministic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--s2", choices=("ehc", "bfs"), default="bfs")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--ood", type=int, default=0, help="also test on this many larger problems")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    a = ap.parse_args()
    seeds = list(range(a.seed_start, a.seed_start + a.seeds))
    names = [n for n in CONFIGS if not a.only or n.strip() in a.only]
    tasks = [(n, a.s2, s, a.ood) for n in names for s in seeds]
    with ProcessPoolExecutor(a.jobs, mp_context=multiprocessing.get_context("fork")) as pool:
        res = dict(zip(tasks, pool.map(_job, tasks)))
    base = [pure_system2_work(a.s2, GP.holdout(DOMAIN, s, 100)) for s in seeds]
    print(f"Gripper stage 3, System 2 = pyperplan {a.s2}; train = curriculum + 100 random; test = 100 frozen random")
    print(f"{'setting':34s} {'test':>6s} {'prec':>6s} {'rules':>6s} {'solved':>6s} {'cost%':>6s} {'len/opt':>7s}" + ("   OOD(big): S1share  solved  cost%" if a.ood else ""))
    for n in names:
        rs = [res[(n, a.s2, s, a.ood)] for s in seeds]
        avg = lambda k: statistics.mean(r[k] for r in rs)
        cost = statistics.mean(r["work"] / max(1, b) for r, b in zip(rs, base)) * 100
        line = f"{n:34s} {avg('test'):6.3f} {avg('prec'):6.3f} {avg('rules'):6.1f} {avg('reach'):6.1f} {cost:6.1f} {avg('overhead'):7.3f}"
        if a.ood:
            o = [r["ood"] for r in rs]
            line += f"   {statistics.mean(x[0] for x in o):17.3f} {statistics.mean(x[1] for x in o):4.1f}/{o[0][2]} {100 * statistics.mean(x[3] / max(1, x[4]) for x in o):7.1f}"
        print(line)
        print(f"{'':34s} per-seed test: " + " ".join(f"{r['test']:.3f}" for r in rs))


if __name__ == "__main__":
    main()
