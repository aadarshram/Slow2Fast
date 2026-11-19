"""Wider sweep over the curriculum protocol used throughout the report: induce-only, the dedupe
variants, and the full mechanism with its ablations. System 2 is pyperplan (--s2 ehc: enforced
hill-climbing + hFF, --s2 bfs: breadth-first search). Problem generation is the only
blocksworld-specific step; problems reach the system as parsed PDDL.
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

from cmc.baselines import InduceAddDedupe, InduceOnly, InduceOnlyDedupe
from cmc.contrast_induce import ContrastLibrary
from cmc.domain import DOMAIN
from cmc.experiment import ensure_deterministic, evaluate, lessons_to_problems, pure_system2_work
from cmc.generate import test_holdout, train_curriculum
from cmc.induce import InducedLibrary


def contrast(**kw):
    return lambda: ContrastLibrary(DOMAIN.operators, DOMAIN.apply, **kw)


CONFIGS = {
    "induce-only": InduceOnly,
    "induce + add": InducedLibrary,
    "induce-only + dedupe": InduceOnlyDedupe,
    "add + dedupe": InduceAddDedupe,
    "contrast": contrast(),
    "contrast + sat/unsat": contrast(derived=True),
    "  ablate: spec after 1 clash": contrast(derived=True, spec_threshold=1),
    "  ablate: no negated literals": contrast(derived=True, allow_neg=False),
    "  ablate: no merge": contrast(derived=True, merge=False),
    "  ablate: no deferral link": contrast(derived=True, defer=False),
    "  ablate: no symmetry": contrast(derived=True, symmetry=False),
    "  + full cover": contrast(derived=True, full_cover=True),
    "  + ties": contrast(derived=True, ties=True),
    "  + ties + full cover": contrast(derived=True, ties=True, full_cover=True),
    "  + order (cheapest discriminator)": contrast(derived=True, order=True),
    "  + minimize": contrast(derived=True, minimize=True),
    "  + order + minimize": contrast(derived=True, order=True, minimize=True),
}

_problems = {}


def problems_for(seed, n):
    if (seed, n) not in _problems:
        train = lessons_to_problems(DOMAIN, train_curriculum(n=n, practice=2, seed=seed, random_count=100), f"tr{seed}")
        test = lessons_to_problems(DOMAIN, test_holdout(n=n, seed=seed, count=100), f"te{seed}")
        _problems[(seed, n)] = (train, test)
    return _problems[(seed, n)]


def _job(task):
    """One (config, seed) evaluation, run in a worker process. Results do not depend on scheduling."""
    name, kind, seed, n = task
    out = evaluate(CONFIGS[name], kind, *problems_for(seed, n))
    out.pop("library")
    return out


def main():
    ensure_deterministic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--s2", choices=("ehc", "bfs"), required=True)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--n", type=int, default=4)
    parser.add_argument("--only", nargs="*", default=None, help="config names to run (stripped)")
    parser.add_argument("--jobs", type=int, default=os.cpu_count(), help="worker processes (default: all cores)")
    args = parser.parse_args()
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    base = [pure_system2_work(args.s2, problems_for(s, args.n)[1]) for s in seeds]
    print(f"System 2 = pyperplan {args.s2}; pure-System-2 test work: {statistics.mean(base):.0f} (mean over {len(seeds)} seeds)")
    print(f"{'config':30s} {'train':>6s} {'test':>6s} {'prec':>6s} {'rules':>6s} {'reach':>6s} {'no_m':>5s} {'multi':>5s} {'below':>5s} {'loop':>5s} {'cost%':>6s} {'len/opt':>7s}")
    names = [n for n in CONFIGS if not args.only or n.strip() in args.only]
    tasks = [(name, args.s2, seed, args.n) for name in names for seed in seeds]
    with ProcessPoolExecutor(args.jobs, mp_context=multiprocessing.get_context("fork")) as pool:
        results = list(pool.map(_job, tasks))
    for name in names:
        runs = [results[tasks.index((name, args.s2, seed, args.n))] for seed in seeds]
        avg = lambda key: statistics.mean(r[key] for r in runs)
        rsn = lambda key: statistics.mean(r["reasons"].get(key, 0) for r in runs)
        cost = statistics.mean(r["work"] / max(1, b) for r, b in zip(runs, base)) * 100
        print(
            f"{name:30s} {avg('train'):6.3f} {avg('test'):6.3f} {avg('prec'):6.3f} {avg('rules'):6.1f} "
            f"{avg('reach'):6.1f} {rsn('no_match'):5.1f} {rsn('multi_match'):5.1f} {rsn('below_threshold'):5.1f} "
            f"{rsn('loop_cut'):5.1f} {cost:6.1f} {avg('overhead'):7.3f}",
            flush=True,
        )
        print(f"{'':30s} per-seed test: " + " ".join(f"{r['test']:.3f}" for r in runs), flush=True)


if __name__ == "__main__":
    main()
